from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
import re
from typing import Mapping, Sequence, cast

from tracepixel.benchmark import B0_FREEZE_COMMIT
from evidence.b0_s0.review import (
    DEFAULT_PREREGISTRATION,
    DEFAULT_RESULTS_ROOT,
    DEFAULT_REVIEW_ROOT,
    OWNER_REVIEW_SCHEMA_V1,
    ReviewApp,
)

MOBILE_REVIEW_SCHEMA_V1 = "tracepixel.b0-mobile-owner-review-package.v1"
_DIMENSIONS = ("recognizability", "readability_at_native_1x", "style_coherence")
_KO_TASKS = {
    "B0-T0-01": "16x16 투명 캔버스 중앙에 청록색 4방향 다이아몬드 문양을 만드세요. 사방에 최소 3픽셀의 투명 여백을 두고, 보이는 색은 최대 3개, 전체 형태는 가로·세로 완전 대칭, 보이는 영역은 하나로 연결되고 고립된 픽셀이 없어야 합니다.",
    "B0-T1-01": "16x16 투명 캔버스에 코르크가 달린 작은 빨간 체력 물약병을 만드세요. 중앙에 배치하고 사방 최소 2픽셀 여백, 보이는 색 최대 6개, 전체 형태 세로 대칭, 하나의 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B0-T1-02": "16x16 투명 캔버스에 오른쪽을 향한 금색 열쇠를 만드세요. 사방 최소 1픽셀 여백, 보이는 색 최대 5개, 하나의 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B0-T2-01": "16x16 투명 캔버스에 정면을 향한 파란 방패를 만드세요. 중앙 배치, 사방 최소 2픽셀 여백, 보이는 색 최대 6개, 전체 형태 세로 대칭, 하나의 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B0-T2-02": "16x16 투명 캔버스에 따뜻한 노란빛과 어두운 프레임을 가진 작은 랜턴을 만드세요. 사방 최소 1픽셀 여백, 보이는 색 최대 7개, 하나의 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B0-T3-01": "16x16 투명 캔버스에 금속 띠가 보이는 정면의 나무통을 만드세요. 중앙 배치, 사방 최소 1픽셀 여백, 보이는 색 최대 8개, 전체 형태 세로 대칭, 하나의 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B0-T3-02": "16x16 투명 캔버스에 갈색 줄기와 초록 수관을 가진 작은 소나무를 만드세요. 사방 최소 1픽셀 여백, 보이는 색 최대 7개, 하나의 연결된 형태, 고립 픽셀 없음 조건입니다.",
}


def _data_uri(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _task_texts(preregistration: Mapping[str, object]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in cast(list[object], preregistration["tasks"]):
        task = cast(dict[str, object], raw)
        out[cast(str, task["id"])] = cast(str, task["visible_text"])
    return out


def _review_data(app: ReviewApp) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw in cast(list[object], app.review_manifest["entries"]):
        entry = cast(dict[str, object], raw)
        review_id = cast(str, entry["review_id"])
        rows.append({
            "review_id": review_id,
            "task_id": entry["task_id"],
            "trial_index": entry["trial_index"],
            "order": entry["order"],
            "native": _data_uri(app.image(review_id, "native")),
            "preview": _data_uri(app.image(review_id, "preview")),
        })
    return rows


def _page(app: ReviewApp, *, language: str) -> bytes:
    if language not in {"ko", "en"}:
        raise ValueError(language)
    canonical = _task_texts(app.preregistration)
    rows = _review_data(app)
    labels = {
        "ko": {
            "title": "TracePixel B0 블라인드 모바일 평가",
            "notice": "방법 이름은 의도적으로 숨겨져 있습니다. 28개 결과를 모두 평가한 뒤 JSON을 저장하거나 공유하세요. 이 페이지는 네트워크 연결 없이 동작합니다.",
            "native": "원본 1배 (16×16)", "preview": "8배 확대 확인",
            "recognizability": "인식 가능성", "readability_at_native_1x": "원본 1배 크기 가독성", "style_coherence": "스타일 일관성",
            "reject": "사람 기준 탈락", "save": "평가 JSON 저장", "share": "평가 JSON 공유", "copy": "JSON 복사",
            "missing": "아직 선택하지 않은 점수가 있습니다.", "ready": "모든 평가가 완료되었습니다.", "copied": "JSON을 복사했습니다.",
            "canonical": "원문 조건", "artifact": "결과", "progress": "진행",
        },
        "en": {
            "title": "TracePixel B0 blind mobile review",
            "notice": "Method names are intentionally hidden. Rate all 28 outputs, then save or share the JSON. This page works offline.",
            "native": "Native 1x (16×16)", "preview": "8x inspection",
            "recognizability": "Recognizability", "readability_at_native_1x": "Readability at native 1x", "style_coherence": "Style coherence",
            "reject": "Human rejection", "save": "Save review JSON", "share": "Share review JSON", "copy": "Copy JSON",
            "missing": "Some ratings are still missing.", "ready": "All ratings are complete.", "copied": "JSON copied.",
            "canonical": "Canonical prompt", "artifact": "Artifact", "progress": "Progress",
        },
    }[language]
    task_groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        task_groups.setdefault(cast(str, row["task_id"]), []).append(row)
    sections: list[str] = []
    for task_id in sorted(task_groups):
        if language == "ko":
            task_text = f'<p class="task-ko">{html.escape(_KO_TASKS[task_id])}</p><details><summary>{labels["canonical"]}</summary><p>{html.escape(canonical[task_id])}</p></details>'
        else:
            task_text = f'<p>{html.escape(canonical[task_id])}</p>'
        cards: list[str] = []
        for row in sorted(task_groups[task_id], key=lambda x: cast(int, x["order"])):
            rid = cast(str, row["review_id"])
            controls: list[str] = []
            for dim in _DIMENSIONS:
                radios = "".join(f'<label class="score"><input type="radio" name="{rid}:{dim}" value="{n}"><span>{n}</span></label>' for n in range(1, 6))
                controls.append(f'<fieldset><legend>{labels[dim]}</legend><div class="scores">{radios}</div></fieldset>')
            cards.append(
                f'<article class="card" data-review-id="{rid}" data-task-id="{html.escape(task_id)}" data-trial-index="{row["trial_index"]}" data-order="{row["order"]}">'
                f'<h3>{labels["artifact"]} {row["order"]}</h3>'
                f'<div class="images"><div><small>{labels["native"]}</small><div class="native"><img src="{row["native"]}" width="16" height="16"></div></div>'
                f'<div><small>{labels["preview"]}</small><br><img class="preview" src="{row["preview"]}" width="128" height="128"></div></div>'
                + "".join(controls)
                + f'<label class="reject"><input type="checkbox" class="reject-box"> {labels["reject"]}</label></article>'
            )
        sections.append(f'<section><h2>{html.escape(task_id)}</h2>{task_text}<div class="grid">{"".join(cards)}</div></section>')

    boot = {
        "schema": OWNER_REVIEW_SCHEMA_V1,
        "freeze_commit": B0_FREEZE_COMMIT,
        "review_manifest_sha256": app.manifest_sha,
        "evaluator_role": "repository owner",
        "dimensions": list(_DIMENSIONS),
        "storage_key": f"tracepixel-b0-review-{app.manifest_sha}",
        "labels": {k: labels[k] for k in ("missing", "ready", "copied", "progress")},
    }
    boot_json = json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    companion = "index.html" if language == "ko" else "index.ko.html"
    companion_label = "English" if language == "ko" else "한국어"
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="dark"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>{labels["title"]}</title><style>:root{{color-scheme:dark}}*{{box-sizing:border-box}}body{{font-family:system-ui,sans-serif;margin:0;background:#151515;color:#eee}}main{{max-width:900px;margin:auto;padding:18px}}a{{color:#9cc8ff}}.top{{position:sticky;top:0;z-index:5;background:#151515ee;backdrop-filter:blur(8px);padding:12px 0;border-bottom:1px solid #444}}.notice,.card{{background:#202020;border:1px solid #444;border-radius:14px;padding:14px}}.notice{{line-height:1.55}}section{{margin-top:28px}}.task-ko{{font-size:1.05rem;line-height:1.6}}details{{color:#bbb}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}}.images{{display:flex;gap:28px;align-items:end;margin:8px 0 14px}}.native{{width:72px;height:72px;display:flex;align-items:center;justify-content:center;background:#2b2b2b;border-radius:8px}}.native img,.preview{{image-rendering:pixelated}}fieldset{{border:1px solid #444;border-radius:10px;margin:12px 0;padding:10px}}legend{{padding:0 6px}}.scores{{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}}.score input{{position:absolute;opacity:0}}.score span{{display:block;text-align:center;padding:10px 0;border:1px solid #555;border-radius:9px;background:#2b2b2b}}.score input:checked+span{{outline:2px solid #9cc8ff;background:#333}}.reject{{display:block;margin-top:8px}}.actions{{position:sticky;bottom:0;background:#151515f3;border-top:1px solid #444;padding:12px 0;display:grid;grid-template-columns:1fr 1fr;gap:8px}}button{{min-height:46px;border-radius:10px;border:1px solid #666;background:#2b2b2b;color:#eee;font:inherit}}#status{{grid-column:1/-1;color:#bbb}}@media(max-width:520px){{main{{padding:12px}}.grid{{grid-template-columns:1fr}}.images{{justify-content:center}}}}</style></head><body><main><div class="top"><h1>{labels["title"]}</h1><a href="{companion}">{companion_label}</a> · <b id="progress">{labels["progress"]}: 0/28</b></div><div class="notice">{labels["notice"]}</div>{''.join(sections)}<div class="actions"><button id="save">{labels["save"]}</button><button id="share">{labels["share"]}</button><button id="copy">{labels["copy"]}</button><span id="status"></span></div></main><script id="boot" type="application/json">{boot_json}</script><script>(()=>{{const B=JSON.parse(document.getElementById('boot').textContent),D=B.dimensions,S=document.getElementById('status'),P=document.getElementById('progress'),cards=[...document.querySelectorAll('.card')];function collect(requireAll=true){{const ratings=[],missing=[];for(const c of cards){{const r={{review_id:c.dataset.reviewId,task_id:c.dataset.taskId,trial_index:Number(c.dataset.trialIndex),order:Number(c.dataset.order),human_rejection:c.querySelector('.reject-box').checked}};for(const d of D){{const x=c.querySelector(`input[name="${{c.dataset.reviewId}}:${{d}}"]:checked`);if(!x)missing.push(`${{c.dataset.reviewId}}:${{d}}`);else r[d]=Number(x.value)}}ratings.push(r)}}if(requireAll&&missing.length)throw Error(B.labels.missing);return {{ratings,missing}}}}function payload(){{const x=collect(true);return {{schema:B.schema,freeze_commit:B.freeze_commit,review_manifest_sha256:B.review_manifest_sha256,evaluator_role:B.evaluator_role,dimensions:D,ratings:x.ratings}}}}function text(){{return JSON.stringify(payload())+'\\n'}}function update(){{const x=collect(false),done=x.ratings.filter(r=>D.every(d=>Number.isInteger(r[d]))).length;P.textContent=`${{B.labels.progress}}: ${{done}}/${{cards.length}}`;try{{localStorage.setItem(B.storage_key,JSON.stringify(x.ratings))}}catch(e){{}}}}function restore(){{try{{const xs=JSON.parse(localStorage.getItem(B.storage_key)||'[]');for(const r of xs){{const c=cards.find(x=>x.dataset.reviewId===r.review_id);if(!c)continue;for(const d of D){{const q=c.querySelector(`input[name="${{r.review_id}}:${{d}}"] [value="${{r[d]}}"]`);if(q)q.checked=true}}c.querySelector('.reject-box').checked=!!r.human_rejection}}}}catch(e){{}}update()}}function blob(){{return new Blob([text()],{{type:'application/json'}})}}document.body.addEventListener('change',update);document.getElementById('save').onclick=()=>{{try{{const u=URL.createObjectURL(blob()),a=document.createElement('a');a.href=u;a.download='owner-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);S.textContent=B.labels.ready}}catch(e){{S.textContent=e.message}}}};document.getElementById('share').onclick=async()=>{{try{{const f=new File([text()],'owner-review.json',{{type:'application/json'}});if(navigator.canShare&&navigator.canShare({{files:[f]}}))await navigator.share({{files:[f],title:'TracePixel B0 owner review'}});else throw Error('Share unavailable; use save or copy.')}}catch(e){{S.textContent=e.message}}}};document.getElementById('copy').onclick=async()=>{{try{{await navigator.clipboard.writeText(text());S.textContent=B.labels.copied}}catch(e){{const t=document.createElement('textarea');t.value=text();document.body.appendChild(t);t.select();document.execCommand('copy');t.remove();S.textContent=B.labels.copied}}}};restore()}})();</script></body></html>'''.encode("utf-8")


def build_mobile_package(output: Path, *, source_sha: str) -> dict[str, object]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("source_sha must be exactly 40 lowercase hex characters")
    app = ReviewApp(DEFAULT_PREREGISTRATION, DEFAULT_RESULTS_ROOT, DEFAULT_REVIEW_ROOT)
    output.mkdir(parents=True, exist_ok=False)
    ko = _page(app, language="ko")
    en = _page(app, language="en")
    (output / "index.ko.html").write_bytes(ko)
    (output / "index.html").write_bytes(en)
    manifest = {
        "schema": MOBILE_REVIEW_SCHEMA_V1,
        "source_sha": source_sha,
        "freeze_commit": B0_FREEZE_COMMIT,
        "review_manifest_sha256": app.manifest_sha,
        "default_language": "ko",
        "entry_count": len(cast(list[object], app.review_manifest["entries"])),
        "method_labels_exposed": False,
        "files": ["index.ko.html", "index.html", "manifest.json"],
        "output_contract": OWNER_REVIEW_SCHEMA_V1,
        "provider_calls": 0,
        "vlm_calls": 0,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for page in (ko, en):
        if b"tracepixel-staged-v1" in page or b"raw-pixel-program-v1" in page:
            raise RuntimeError("mobile blind review page leaked method identity")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the offline mobile B0 owner blind-review package")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args(argv)
    manifest = build_mobile_package(args.output, source_sha=args.source_sha)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
