from __future__ import annotations

import json
import subprocess
import unittest

from tracepixel.agent import (
    AGENT_OBSERVATION_SCHEMA_V1,
    AGENT_PROVIDER_REQUEST_SCHEMA_V1,
    CODEX_CLI_MODEL_V1,
    CODEX_CLI_REASONING_EFFORT_V1,
    CodexCliProvider,
    CodexCliProviderError,
)
from tracepixel.model import ART_INTENT_SCHEMA_V1
from tracepixel.qa import QA_FINDINGS_SCHEMA_V1


def _request():
    return {
        "schema": AGENT_PROVIDER_REQUEST_SCHEMA_V1,
        "instruction": "Make one bounded edit.",
        "observation": {
            "schema": AGENT_OBSERVATION_SCHEMA_V1,
            "intent": {
                "schema": ART_INTENT_SCHEMA_V1,
                "asset_class": "icon",
                "canvas": {"width": 2, "height": 2},
                "composition": {
                    "occupied_bounds": None,
                    "facing": None,
                    "symmetry": None,
                    "light_direction": None,
                    "palette_budget": None,
                },
            },
            "current": {"stage": None, "revision": 0},
            "qa": {
                "schema": QA_FINDINGS_SCHEMA_V1,
                "findings": [
                    {
                        "rule": "structural.non_empty",
                        "category": "structural",
                        "severity": "error",
                    }
                ],
            },
            "preview": None,
            "recent": [],
        },
    }


class _FakeRunner:
    def __init__(
        self,
        *,
        auth: str = "Logged in using ChatGPT",
        version: str = "codex-cli 0.144.6",
    ) -> None:
        self.auth = auth
        self.version = version
        self.commands: list[list[str]] = []
        self.prompt: str | None = None

    def __call__(self, command, **kwargs):
        args = list(command)
        self.commands.append(args)
        if args[-1:] == ["--version"]:
            return subprocess.CompletedProcess(args, 0, stdout=self.version + "\n", stderr="")
        if args[-2:] == ["login", "status"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr=self.auth + "\n")
        self.prompt = kwargs.get("input")
        output_index = args.index("--output-last-message") + 1
        proposal = {
            "schema": "tracepixel.agent-provider-proposal.v1",
            "kind": "pixel_program",
            "payload": {
                "schema": "tracepixel.pixel-program.v1",
                "canvas": {"width": 2, "height": 2},
                "operations": [
                    {"op": "set_pixels", "pixels": [[0, 0, 255, 0, 0, 255]]}
                ],
            },
        }
        with open(args[output_index], "w", encoding="utf-8") as handle:
            json.dump(proposal, handle)
        stdout = "\n".join(
            (
                json.dumps({"type": "turn.started"}),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 123,
                            "cached_input_tokens": 20,
                            "output_tokens": 45,
                            "reasoning_output_tokens": 10,
                        },
                    }
                ),
            )
        )
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")


class CodexCliProviderTests(unittest.TestCase):
    def test_windows_npm_cmd_shim_uses_comspec_wrapper_without_double_quoting(self) -> None:
        executable = r"C:\Program Files\OpenAI\codex.cmd"
        arguments = ["exec", "--json"]

        command = CodexCliProvider._command(executable, arguments)

        self.assertEqual(command[1:4], ["/d", "/s", "/c"])
        self.assertEqual(command[4], subprocess.list2cmdline([executable, *arguments]))
        self.assertEqual(command[4], '"C:\\Program Files\\OpenAI\\codex.cmd" exec --json')
        self.assertFalse(command[4].startswith('""'))
        self.assertFalse(command[4].endswith('""'))

    def test_environment_requires_pinned_version_and_chatgpt_auth(self) -> None:
        runner = _FakeRunner()
        provider = CodexCliProvider(_run=runner, _which=lambda _: "/fake/codex")

        environment = provider.environment()

        self.assertEqual(environment.auth_mode, "chatgpt")
        self.assertEqual(environment.model, CODEX_CLI_MODEL_V1)
        self.assertEqual(environment.reasoning_effort, CODEX_CLI_REASONING_EFFORT_V1)
        self.assertEqual(environment.version, "codex-cli 0.144.6")

    def test_environment_refuses_codex_older_than_pinned_minimum(self) -> None:
        provider = CodexCliProvider(
            _run=_FakeRunner(version="codex-cli 0.143.9"),
            _which=lambda _: "/fake/codex",
        )

        with self.assertRaises(CodexCliProviderError) as context:
            provider.environment()

        self.assertEqual(context.exception.code, "codex_version_too_old")

    def test_environment_refuses_api_key_billing(self) -> None:
        provider = CodexCliProvider(
            _run=_FakeRunner(auth="Logged in using an API key - sk-proj-***"),
            _which=lambda _: "/fake/codex",
        )

        with self.assertRaises(CodexCliProviderError) as context:
            provider.environment()

        self.assertEqual(context.exception.code, "api_key_auth_not_authorized")

    def test_propose_uses_ephemeral_read_only_structured_headless_exec(self) -> None:
        runner = _FakeRunner()
        provider = CodexCliProvider(_run=runner, _which=lambda _: "/fake/codex")

        proposal = provider.propose(_request())

        self.assertEqual(proposal["kind"], "pixel_program")
        command = runner.commands[-1]
        self.assertEqual(command[:2], ["/fake/codex", "exec"])
        self.assertIn("--ephemeral", command)
        self.assertIn("--json", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertEqual(command[command.index("--model") + 1], CODEX_CLI_MODEL_V1)
        self.assertIn('model_reasoning_effort="low"', command)
        self.assertIn("--output-schema", command)
        self.assertTrue(runner.prompt and "TRACEPIXEL_REQUEST=" in runner.prompt)
        self.assertTrue(
            runner.prompt and "do not inspect the filesystem" in runner.prompt.lower()
        )

        usage = provider.last_usage()
        self.assertIsNotNone(usage)
        assert usage is not None
        self.assertEqual(usage.input_tokens, 123)
        self.assertEqual(usage.output_tokens, 45)
        self.assertIsNone(usage.api_cost_usd_micros)
        records = provider.call_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].proposal, proposal)

    def test_missing_codex_is_a_stable_adapter_error(self) -> None:
        provider = CodexCliProvider(_which=lambda _: None)

        with self.assertRaises(CodexCliProviderError) as context:
            provider.environment()

        self.assertEqual(context.exception.code, "codex_not_found")


if __name__ == "__main__":
    unittest.main()
