from __future__ import annotations

import argparse
import hashlib
import html
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
from typing import Mapping, Sequence, cast
import webbrowser

from tracepixel.benchmark import (
    B0_FREEZE_COMMIT,
    attempt_relative_path,
    blind_review_key,
    build_b0_schedule,
    load_b0_preregistration,
)

DEFAULT_PREREGISTRATION = Path("evidence/b0/preregistration.v1.json")
DEFAULT_RESULTS_ROOT = Path("evidence/b0/results")
DEFAULT_REVIEW_ROOT = Path("evidence/b0/review")
BLIND_REVIEW_SCHEMA_V1 = "tracepixel.b0-blind-review-package.v1"
OWNER_REVIEW_SCHEMA_V1 = "tracepixel.b0-owner-review.v1"
OWNER_REVIEW_SUMMARY_SCHEMA_V1 = "tracepixel.b0-owner-review-summary.v1"
_DIMENSIONS = ("recognizability", "readability_at_native_1x", "style_coherence")
_REQUIRED = ("provider-request.json", "provider-response.json", "proposal-or-failure.json", "deterministic-qa.json", "telemetry.json")
_COMPLETED = ("final.rgba", "final.png", "preview-8x.png")


class ReviewContractError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewContractError(f"cannot load JSON object {path}: {exc}") from exc
    if type(value) is not dict:
        raise ReviewContractError(f"expected JSON object: {path}")
    return cast(dict[str, object], value)


def _write_exclusive(path: Path, payload: Mapping[str, object]) -> None:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ReviewContractError(f"refusing to overwrite sealed owner review evidence: {path}") from exc


def _mapping(preregistration: Mapping[str, object], preregistration_sha256: str) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    schedule = build_b0_schedule(preregistration, preregistration_sha256=preregistration_sha256)
    identities = [cast(dict[str, object], item) for item in cast(list[object], schedule["attempts"])]
    by_review_id: dict[str, dict[str, object]] = {}
    for identity in identities:
        key = blind_review_key(cast(object, identity))
        if key in by_review_id:
            raise ReviewContractError(f"duplicate blind review key: {key}")
        by_review_id[key] = identity
    return by_review_id, identities


def _verify_artifact(directory: Path, name: str, metadata: Mapping[str, object]) -> None:
    path = directory / name
    if not path.is_file():
        raise ReviewContractError(f"retained artifact missing: {path}")
    data = path.read_bytes()
    if metadata.get("bytes") != len(data) or metadata.get("sha256") != _sha256(data):
        raise ReviewContractError(f"retained artifact hash/size mismatch: {path}")


def validate_review_package(
    preregistration: Mapping[str, object], preregistration_sha256: str, results_root: Path, review_root: Path
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    by_review_id, identities = _mapping(preregistration, preregistration_sha256)
    manifests: dict[str, dict[str, object]] = {}
    for identity in identities:
        attempt_id = cast(str, identity["attempt_id"])
        directory = results_root / attempt_relative_path(cast(object, identity))
        manifest = _load_object(directory / "attempt-manifest.json")
        if manifest.get("identity") != identity or manifest.get("provider_invoked") is not True:
            raise ReviewContractError(f"invalid retained scored attempt: {attempt_id}")
        artifacts = manifest.get("artifacts")
        if type(artifacts) is not dict:
            raise ReviewContractError(f"invalid artifact index: {attempt_id}")
        index = cast(dict[str, object], artifacts)
        required = list(_REQUIRED) + (list(_COMPLETED) if manifest.get("completion") is True else [])
        for name in required:
            metadata = index.get(name)
            if type(metadata) is not dict:
                raise ReviewContractError(f"missing required artifact metadata: {attempt_id}/{name}")
        for name, raw_metadata in index.items():
            if type(name) is not str or type(raw_metadata) is not dict:
                raise ReviewContractError(f"invalid artifact metadata entry: {attempt_id}")
            _verify_artifact(directory, name, cast(dict[str, object], raw_metadata))
        manifests[attempt_id] = manifest

    package_root = review_root / B0_FREEZE_COMMIT
    review_manifest = _load_object(package_root / "manifest.json")
    if review_manifest.get("schema") != BLIND_REVIEW_SCHEMA_V1 or review_manifest.get("freeze_commit") != B0_FREEZE_COMMIT:
        raise ReviewContractError("blind review package identity mismatch")
    if review_manifest.get("method_labels_exposed") is not False:
        raise ReviewContractError("blind review package exposes method labels")
    if review_manifest.get("dimensions") != list(_DIMENSIONS) or review_manifest.get("scale") != "integer 1-5":
        raise ReviewContractError("blind review rating contract mismatch")
    raw_entries = review_manifest.get("entries")
    if type(raw_entries) is not list or any(type(item) is not dict for item in raw_entries):
        raise ReviewContractError("blind review entries are invalid")
    entries = [cast(dict[str, object], item) for item in raw_entries]
    completed = {
        review_id: identity
        for review_id, identity in by_review_id.items()
        if manifests[cast(str, identity["attempt_id"])].get("completion") is True
    }
    if len(entries) != len(completed):
        raise ReviewContractError(f"blind review count mismatch: entries={len(entries)}, completed={len(completed)}")

    seen: set[str] = set()
    grouped: dict[str, list[dict[str, object]]] = {}
    for entry in entries:
        review_id = entry.get("review_id")
        if type(review_id) is not str or review_id not in completed or review_id in seen or "method_id" in entry:
            raise ReviewContractError("blind review entry identity/leak mismatch")
        seen.add(review_id)
        identity = completed[review_id]
        if entry.get("task_id") != identity.get("task_id") or entry.get("trial_index") != identity.get("trial_index"):
            raise ReviewContractError(f"blind review identity facts mismatch: {review_id}")
        order = entry.get("order")
        preview = entry.get("preview")
        if type(order) is not int or order < 1 or type(preview) is not str:
            raise ReviewContractError(f"invalid blind review order/preview: {review_id}")
        destination = package_root / preview
        source = results_root / attempt_relative_path(cast(object, identity)) / "preview-8x.png"
        if not destination.is_file() or not source.is_file() or destination.read_bytes() != source.read_bytes():
            raise ReviewContractError(f"blind preview differs from retained scored output: {review_id}")
        grouped.setdefault(cast(str, identity["task_id"]), []).append(entry)
    for task_id, task_entries in grouped.items():
        ordered = sorted(task_entries, key=lambda item: cast(int, item["order"]))
        if [item["order"] for item in ordered] != list(range(1, len(ordered) + 1)):
            raise ReviewContractError(f"non-contiguous blind order: {task_id}")
        if [item["review_id"] for item in ordered] != sorted(cast(str, item["review_id"]) for item in ordered):
            raise ReviewContractError(f"blind order differs from frozen SHA-256 order: {task_id}")
    return review_manifest, by_review_id, manifests


def _contains_method_id(value: object) -> bool:
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        return "method_id" in mapping or any(_contains_method_id(item) for item in mapping.values())
    if type(value) is list:
        return any(_contains_method_id(item) for item in cast(list[object], value))
    return False


def validate_owner_review(payload: Mapping[str, object], review_manifest: Mapping[str, object], manifest_sha256: str) -> list[dict[str, object]]:
    if payload.get("schema") != OWNER_REVIEW_SCHEMA_V1 or payload.get("freeze_commit") != B0_FREEZE_COMMIT:
        raise ReviewContractError("owner review identity mismatch")
    if payload.get("review_manifest_sha256") != manifest_sha256 or payload.get("evaluator_role") != "repository owner":
        raise ReviewContractError("owner review evaluator/manifest binding mismatch")
    if payload.get("dimensions") != list(_DIMENSIONS) or _contains_method_id(payload):
        raise ReviewContractError("owner review rating contract or blindness mismatch")
    raw_ratings = payload.get("ratings")
    raw_entries = review_manifest.get("entries")
    if type(raw_ratings) is not list or type(raw_entries) is not list or len(raw_ratings) != len(raw_entries):
        raise ReviewContractError("owner review must rate every blind entry exactly once")
    ratings: list[dict[str, object]] = []
    for raw_rating, raw_entry in zip(raw_ratings, raw_entries, strict=True):
        if type(raw_rating) is not dict or type(raw_entry) is not dict:
            raise ReviewContractError("owner review contains invalid rating object")
        rating = cast(dict[str, object], raw_rating)
        entry = cast(dict[str, object], raw_entry)
        for field in ("review_id", "task_id", "trial_index", "order"):
            if rating.get(field) != entry.get(field):
                raise ReviewContractError(f"owner review order/identity mismatch: {field}")
        for dimension in _DIMENSIONS:
            score = rating.get(dimension)
            if type(score) is not int or not 1 <= score <= 5:
                raise ReviewContractError(f"{dimension} must be an integer 1-5")
        if type(rating.get("human_rejection")) is not bool:
            raise ReviewContractError("human_rejection must be an explicit boolean")
        ratings.append(rating)
    return ratings


def owner_review_summary(ratings: Sequence[Mapping[str, object]], by_review_id: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for rating in ratings:
        identity = by_review_id.get(cast(str, rating["review_id"]))
        if identity is None:
            raise ReviewContractError("cannot unblind unknown review_id")
        grouped.setdefault(cast(str, identity["method_id"]), []).append(rating)
    methods = []
    for method_id in sorted(grouped):
        selected = grouped[method_id]
        methods.append({
            "method_id": method_id,
            "rated_artifacts": len(selected),
            "human_rejection_count": sum(item.get("human_rejection") is True for item in selected),
            "mean": {dimension: sum(cast(int, item[dimension]) for item in selected) / len(selected) for dimension in _DIMENSIONS},
        })
    return {
        "schema": OWNER_REVIEW_SUMMARY_SCHEMA_V1,
        "freeze_commit": B0_FREEZE_COMMIT,
        "rating_count": len(ratings),
        "methods": methods,
        "claim_boundary": "human perception only; deterministic correctness remains separate; no composite winner",
    }


def _task_texts(preregistration: Mapping[str, object]) -> dict[str, str]:
    output: dict[str, str] = {}
    for raw_task in cast(list[object], preregistration["tasks"]):
        task = cast(dict[str, object], raw_task)
        output[cast(str, task["id"])] = cast(str, task["visible_text"])
    return output


def _page(review_manifest: Mapping[str, object], task_texts: Mapping[str, str]) -> bytes:
    grouped: dict[str, list[dict[str, object]]] = {}
    for raw_entry in cast(list[object], review_manifest["entries"]):
        entry = cast(dict[str, object], raw_entry)
        grouped.setdefault(cast(str, entry["task_id"]), []).append(entry)
    sections: list[str] = []
    for task_id in sorted(grouped):
        cards: list[str] = []
        for entry in sorted(grouped[task_id], key=lambda item: cast(int, item["order"])):
            review_id = cast(str, entry["review_id"])
            controls = []
            for dimension, label in (("recognizability", "Recognizability"), ("readability_at_native_1x", "Readability at native 1x"), ("style_coherence", "Style coherence")):
                radios = "".join(f'<label><input type="radio" name="{review_id}:{dimension}" value="{n}"> {n}</label>' for n in range(1, 6))
                controls.append(f'<fieldset><legend>{label}</legend><div class="scores">{radios}</div></fieldset>')
            cards.append(f'''<article class="card" data-review-id="{review_id}" data-task-id="{html.escape(task_id)}" data-trial-index="{entry["trial_index"]}" data-order="{entry["order"]}"><h3>Artifact {entry["order"]}</h3><div class="images"><div><small>Native 1x</small><div class="native"><img src="/image/{review_id}/native" width="16" height="16"></div></div><div><small>8x inspection</small><br><img class="preview" src="/image/{review_id}/preview" width="128" height="128"></div></div>{''.join(controls)}<label><input type="checkbox" class="reject"> Human rejection</label></article>''')
        sections.append(f'<section><h2>{html.escape(task_id)}</h2><p>{html.escape(task_texts[task_id])}</p><div class="grid">{"".join(cards)}</div></section>')
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TracePixel B0 blind owner review</title><style>:root{{color-scheme:dark}}body{{font-family:system-ui;max-width:1100px;margin:auto;padding:24px;background:#151515;color:#eee}}.notice,.card{{background:#202020;border:1px solid #444;border-radius:12px;padding:14px}}section{{margin-top:32px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}.images{{display:flex;align-items:end;gap:24px;min-height:160px}}.native{{width:64px;height:64px;display:flex;align-items:center;justify-content:center;background:#2b2b2b}}.native img,.preview{{image-rendering:pixelated}}fieldset{{margin:12px 0;border:1px solid #444}}.scores{{display:flex;justify-content:space-between}}.actions{{position:sticky;bottom:0;background:#151515;padding:16px 0;border-top:1px solid #444}}button{{padding:12px 18px;font:inherit}}.error{{color:#ff9b9b}}.ok{{color:#9cffaa}}</style></head><body><h1>TracePixel B0 blind owner review</h1><div class="notice"><b>Method names are intentionally hidden.</b> Rate every artifact once. Native 1x is the exact 16×16 output; 8x is inspection only. Saving seals the review and overwrite is refused.</div>{''.join(sections)}<div class="actions"><button id="save">Seal owner review</button> <span id="status"></span></div><script>const ds=['recognizability','readability_at_native_1x','style_coherence'],b=document.getElementById('save'),s=document.getElementById('status');b.onclick=async()=>{{const ratings=[],missing=[];for(const c of document.querySelectorAll('.card')){{const r={{review_id:c.dataset.reviewId,task_id:c.dataset.taskId,trial_index:Number(c.dataset.trialIndex),order:Number(c.dataset.order),human_rejection:c.querySelector('.reject').checked}};for(const d of ds){{const x=c.querySelector(`input[name="${{c.dataset.reviewId}}:${{d}}"]:checked`);if(!x)missing.push(1);else r[d]=Number(x.value)}}ratings.push(r)}}if(missing.length){{s.className='error';s.textContent=`Missing ${{missing.length}} rating(s).`;return}}b.disabled=true;s.textContent='Saving…';try{{const x=await fetch('/submit',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ratings}})}}),j=await x.json();if(!x.ok)throw Error(j.error);s.className='ok';s.textContent=`Saved ${{j.path}}. You can close this tab.`}}catch(e){{b.disabled=false;s.className='error';s.textContent=String(e)}}}};</script></body></html>'''.encode("utf-8")


class ReviewApp:
    def __init__(self, preregistration_path: Path, results_root: Path, review_root: Path) -> None:
        self.preregistration, prereg_sha = load_b0_preregistration(preregistration_path)
        self.review_manifest, self.by_review_id, self.manifests = validate_review_package(self.preregistration, prereg_sha, results_root, review_root)
        self.results_root = results_root
        self.package_root = review_root / B0_FREEZE_COMMIT
        self.manifest_sha = _sha256((self.package_root / "manifest.json").read_bytes())
        self.owner_path = self.package_root / "owner-review.json"
        self.summary_path = self.package_root / "owner-review-summary.json"
        self.page = _page(self.review_manifest, _task_texts(self.preregistration))
        self.entries = {cast(str, cast(dict[str, object], item)["review_id"]): cast(dict[str, object], item) for item in cast(list[object], self.review_manifest["entries"])}

    def image(self, review_id: str, kind: str) -> bytes:
        entry, identity = self.entries.get(review_id), self.by_review_id.get(review_id)
        if entry is None or identity is None:
            raise ReviewContractError("unknown blind review image")
        if kind == "preview":
            return (self.package_root / cast(str, entry["preview"])).read_bytes()
        if kind == "native":
            return (self.results_root / attempt_relative_path(cast(object, identity)) / "final.png").read_bytes()
        raise ReviewContractError("unknown image kind")

    def validate_existing(self) -> dict[str, object] | None:
        if not self.owner_path.exists():
            return None
        payload = _load_object(self.owner_path)
        ratings = validate_owner_review(payload, self.review_manifest, self.manifest_sha)
        summary = owner_review_summary(ratings, self.by_review_id)
        if not self.summary_path.exists():
            _write_exclusive(self.summary_path, summary)
        elif _load_object(self.summary_path) != summary:
            raise ReviewContractError("owner review summary differs from sealed ratings")
        return summary

    def seal(self, client: Mapping[str, object]) -> dict[str, object]:
        if self.owner_path.exists():
            raise ReviewContractError(f"owner review already sealed: {self.owner_path}")
        payload: dict[str, object] = {"schema": OWNER_REVIEW_SCHEMA_V1, "freeze_commit": B0_FREEZE_COMMIT, "review_manifest_sha256": self.manifest_sha, "evaluator_role": "repository owner", "dimensions": list(_DIMENSIONS), "ratings": client.get("ratings")}
        ratings = validate_owner_review(payload, self.review_manifest, self.manifest_sha)
        _write_exclusive(self.owner_path, payload)
        summary = owner_review_summary(ratings, self.by_review_id)
        _write_exclusive(self.summary_path, summary)
        return {"path": str(self.owner_path), "summary_path": str(self.summary_path), "rating_count": len(ratings)}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address: tuple[str, int], app: ReviewApp) -> None:
        super().__init__(address, Handler)
        self.app = app


class Handler(BaseHTTPRequestHandler):
    server: Server
    def log_message(self, format: str, *args: object) -> None:
        return
    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers(); self.wfile.write(body)
    def do_GET(self) -> None:
        if self.path == "/":
            self._send(HTTPStatus.OK, "text/html; charset=utf-8", self.server.app.page); return
        parts = self.path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "image" and parts[2] in {"native", "preview"}:
            try: body = self.server.app.image(parts[1], parts[2])
            except (OSError, ReviewContractError): self.send_error(HTTPStatus.NOT_FOUND); return
            self._send(HTTPStatus.OK, "image/png", body); return
        self.send_error(HTTPStatus.NOT_FOUND)
    def do_POST(self) -> None:
        if self.path != "/submit": self.send_error(HTTPStatus.NOT_FOUND); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 256000: raise ReviewContractError("invalid review payload length")
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if type(value) is not dict: raise ReviewContractError("review submission must be an object")
            result = self.server.app.seal(cast(dict[str, object], value)); body = json.dumps(result, sort_keys=True).encode()
            self._send(HTTPStatus.OK, "application/json", body); threading.Thread(target=self.server.shutdown, daemon=True).start()
        except (ReviewContractError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._send(HTTPStatus.BAD_REQUEST, "application/json", json.dumps({"error": str(exc)}).encode())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and record the frozen B0 blind owner review")
    parser.add_argument("--preregistration", type=Path, default=DEFAULT_PREREGISTRATION)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--validate-package-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        app = ReviewApp(args.preregistration, args.results_root, args.review_root)
        existing = app.validate_existing()
        if args.validate_package_only:
            print(json.dumps({"freeze_commit": B0_FREEZE_COMMIT, "retained_attempt_count": len(app.manifests), "blind_review_entry_count": len(cast(list[object], app.review_manifest["entries"])), "owner_review": "valid" if existing is not None else "absent"}, sort_keys=True)); return 0
        if existing is not None:
            print(f"B0 owner review is already sealed and valid: {app.owner_path}"); print(json.dumps(existing, sort_keys=True)); return 0
        server = Server(("127.0.0.1", args.port), app); url = f"http://127.0.0.1:{server.server_port}/"
        print(f"B0 blind owner review: {url}")
        print("Loopback-only; saving seals the review and stops the server. Ctrl+C stops without saving.")
        if not args.no_browser: webbrowser.open(url)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
        return 0
    except ReviewContractError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
