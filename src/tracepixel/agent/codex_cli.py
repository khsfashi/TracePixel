from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast

from .provider import (
    AGENT_PROVIDER_PROPOSAL_SCHEMA_V1,
    AgentProviderProposalV1,
    AgentProviderRequestV1,
    validate_agent_provider_request,
)
from .telemetry import AgentProviderUsage

CODEX_CLI_MODEL_V1 = "gpt-5.6-sol"
CODEX_CLI_REASONING_EFFORT_V1 = "low"
CODEX_CLI_MIN_VERSION_V1 = (0, 144, 0)
CODEX_CLI_TIMEOUT_SECONDS_V1 = 180

_CODEX_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema", "kind", "payload"],
    "properties": {
        "schema": {"const": AGENT_PROVIDER_PROPOSAL_SCHEMA_V1},
        "kind": {"const": "pixel_program"},
        "payload": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema", "canvas", "operations"],
            "properties": {
                "schema": {"const": "tracepixel.pixel-program.v1"},
                "canvas": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["width", "height"],
                    "properties": {
                        "width": {"type": "integer"},
                        "height": {"type": "integer"},
                    },
                },
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["op", "pixels"],
                        "properties": {
                            "op": {"const": "set_pixels"},
                            "pixels": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "minItems": 6,
                                    "maxItems": 6,
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


class CodexCliProviderError(RuntimeError):
    """Stable local-adapter failure; never converted into raster or QA authority."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{message} [{code}]")


@dataclass(frozen=True, slots=True)
class CodexCliEnvironment:
    executable: str
    version: str
    auth_mode: str
    model: str
    reasoning_effort: str


@dataclass(frozen=True, slots=True)
class CodexCliCallRecord:
    proposal: AgentProviderProposalV1
    input_tokens: int | None
    output_tokens: int | None


_Run = Callable[..., subprocess.CompletedProcess[str]]
_Which = Callable[[str], str | None]


class CodexCliProvider:
    """Owner-triggered P5-A5 adapter around ``codex exec``.

    The adapter intentionally delegates authentication/network transport to an already
    installed Codex CLI. TracePixel sends only the bounded provider request, asks for one
    schema-constrained PixelProgram proposal, then returns candidate JSON to the existing
    provider-neutral validation/execution path.
    """

    def __init__(
        self,
        *,
        executable: str = "codex",
        model: str = CODEX_CLI_MODEL_V1,
        reasoning_effort: str = CODEX_CLI_REASONING_EFFORT_V1,
        timeout_seconds: int = CODEX_CLI_TIMEOUT_SECONDS_V1,
        _run: _Run = subprocess.run,
        _which: _Which = shutil.which,
    ) -> None:
        if not executable.strip():
            raise ValueError("executable must not be blank")
        if not model.strip():
            raise ValueError("model must not be blank")
        if reasoning_effort not in ("none", "low", "medium", "high", "xhigh", "max"):
            raise ValueError("reasoning_effort is unsupported")
        if type(timeout_seconds) is not int or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive integer")
        self._executable_name = executable
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds
        self._run = _run
        self._which = _which
        self._last_usage: AgentProviderUsage | None = None
        self._records: list[CodexCliCallRecord] = []
        self._environment: CodexCliEnvironment | None = None

    def _resolve_executable(self) -> str:
        resolved = self._which(self._executable_name)
        if resolved is None:
            raise CodexCliProviderError(
                "codex_not_found",
                f"cannot find {self._executable_name!r} on PATH",
            )
        return resolved

    @staticmethod
    def _command(executable: str, arguments: list[str]) -> list[str]:
        # npm installs command shims as .cmd on Windows. Launch those explicitly through
        # COMSPEC while retaining shell=False for all other executable forms.
        if Path(executable).suffix.lower() in (".cmd", ".bat"):
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            command_line = subprocess.list2cmdline([executable, *arguments])
            return [comspec, "/d", "/s", "/c", f'"{command_line}"']
        return [executable, *arguments]

    def _run_metadata(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        executable = self._resolve_executable()
        try:
            result = self._run(
                self._command(executable, arguments),
                capture_output=True,
                text=True,
                timeout=min(self.timeout_seconds, 30),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CodexCliProviderError("codex_metadata_timeout", str(exc)) from exc
        except OSError as exc:
            raise CodexCliProviderError("codex_launch_failed", str(exc)) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise CodexCliProviderError(
                "codex_metadata_failed",
                detail[-2000:] or f"Codex exited with {result.returncode}",
            )
        return result

    @staticmethod
    def _parse_version(text: str) -> tuple[int, int, int]:
        tokens = text.strip().split()
        version_text = tokens[-1] if tokens else ""
        parts = version_text.split(".")
        if len(parts) < 3 or any(not part.isdigit() for part in parts[:3]):
            raise CodexCliProviderError(
                "unsupported_codex_version",
                f"cannot parse Codex CLI version from {text.strip()!r}",
            )
        return int(parts[0]), int(parts[1]), int(parts[2])

    def environment(self) -> CodexCliEnvironment:
        if self._environment is not None:
            return self._environment
        version_result = self._run_metadata(["--version"])
        version_text = (version_result.stdout or version_result.stderr).strip()
        parsed = self._parse_version(version_text)
        if parsed < CODEX_CLI_MIN_VERSION_V1:
            minimum = ".".join(str(value) for value in CODEX_CLI_MIN_VERSION_V1)
            raise CodexCliProviderError(
                "codex_version_too_old",
                f"P5-A5 requires Codex CLI >= {minimum}; got {version_text!r}",
            )

        auth_result = self._run_metadata(["login", "status"])
        auth_text = "\n".join(
            part.strip() for part in (auth_result.stdout, auth_result.stderr) if part.strip()
        )
        if "Logged in using ChatGPT" not in auth_text:
            if "Logged in using an API key" in auth_text:
                code = "api_key_auth_not_authorized"
                message = (
                    "P5-A5 G3 authorizes the existing ChatGPT/Codex plan boundary only; "
                    "API-key billed execution is not authorized"
                )
            else:
                code = "chatgpt_login_required"
                message = "Codex CLI must report 'Logged in using ChatGPT' before the real smoke"
            raise CodexCliProviderError(code, message)

        self._environment = CodexCliEnvironment(
            executable=self._resolve_executable(),
            version=version_text,
            auth_mode="chatgpt",
            model=self.model,
            reasoning_effort=self.reasoning_effort,
        )
        return self._environment

    @staticmethod
    def _prompt(request: AgentProviderRequestV1) -> str:
        request_json = json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return (
            "Act only as the TracePixel provider proposal boundary. "
            "Do not inspect the filesystem, do not run shell commands, and do not explain your answer. "
            "Return exactly one schema-constrained pixel_program proposal for the request below. "
            "The proposal is candidate data only; TracePixel will validate budgets, execute pixels, and run QA. "
            "Use only set_pixels operations and match the requested canvas exactly.\n"
            f"TRACEPIXEL_REQUEST={request_json}"
        )

    @staticmethod
    def _usage_from_jsonl(stdout: str) -> AgentProviderUsage | None:
        last_usage: AgentProviderUsage | None = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if type(event) is not dict or event.get("type") != "turn.completed":
                continue
            usage = event.get("usage")
            if type(usage) is not dict:
                continue
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if type(input_tokens) is not int or input_tokens < 0:
                input_tokens = None
            if type(output_tokens) is not int or output_tokens < 0:
                output_tokens = None
            last_usage = AgentProviderUsage(
                input_tokens=cast(int | None, input_tokens),
                output_tokens=cast(int | None, output_tokens),
                api_cost_usd_micros=None,
            )
        return last_usage

    def propose(self, request: AgentProviderRequestV1, /) -> AgentProviderProposalV1:
        validate_agent_provider_request(request)
        self.environment()
        executable = self._resolve_executable()
        self._last_usage = None

        with tempfile.TemporaryDirectory(prefix="tracepixel-codex-") as temporary:
            directory = Path(temporary)
            schema_path = directory / "proposal.schema.json"
            output_path = directory / "proposal.json"
            schema_path.write_text(
                json.dumps(_CODEX_OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            command = self._command(
                executable,
                [
                    "exec",
                    "--ephemeral",
                    "--json",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--model",
                    self.model,
                    "--config",
                    f'model_reasoning_effort="{self.reasoning_effort}"',
                    "--output-schema",
                    str(schema_path),
                    "--output-last-message",
                    str(output_path),
                    "-",
                ],
            )
            try:
                result = self._run(
                    command,
                    input=self._prompt(request),
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise CodexCliProviderError("codex_timeout", str(exc)) from exc
            except OSError as exc:
                raise CodexCliProviderError("codex_launch_failed", str(exc)) from exc

            if result.returncode != 0:
                detail = (result.stderr or result.stdout).strip()
                raise CodexCliProviderError(
                    "codex_exec_failed",
                    detail[-4000:] or f"Codex exited with {result.returncode}",
                )
            try:
                raw = output_path.read_text(encoding="utf-8")
            except OSError as exc:
                raise CodexCliProviderError("codex_output_missing", str(exc)) from exc
            try:
                proposal = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CodexCliProviderError("codex_output_invalid_json", str(exc)) from exc
            if type(proposal) is not dict:
                raise CodexCliProviderError(
                    "codex_output_invalid_type",
                    "Codex final output must be a JSON object",
                )

            self._last_usage = self._usage_from_jsonl(result.stdout)
            typed = cast(AgentProviderProposalV1, proposal)
            usage = self._last_usage
            self._records.append(
                CodexCliCallRecord(
                    proposal=copy.deepcopy(typed),
                    input_tokens=None if usage is None else usage.input_tokens,
                    output_tokens=None if usage is None else usage.output_tokens,
                )
            )
            return typed

    def last_usage(self, /) -> AgentProviderUsage | None:
        return self._last_usage

    def call_records(self) -> tuple[CodexCliCallRecord, ...]:
        return tuple(self._records)
