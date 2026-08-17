from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import html
import json
from pathlib import Path
from typing import Mapping, Sequence, cast

from tracepixel.benchmark.b1_harness import B1_FREEZE_COMMIT, B1_SCORED_METHOD_IDS

MOBILE_REVIEW_SCHEMA_V1 = "tracepixel.b1-mobile-owner-review-package.v1"
OWNER_REVIEW_SCHEMA_V1 = "tracepixel.b1-owner-review.v1"
DIMENSIONS = ("recognizability", "readability_at_native_1x", "style_coherence")
DEFAULT_PREREGISTRATION = Path("evidence/b1/preregistration.v1.json")
DEFAULT_RESULTS_ROOT = Path("evidence/b1/results")
DEFAULT_REVIEW_ROOT = Path("evidence/b1/review")

_KO_TASKS = {
    "B1-T0-01": "16×16 투명 캔버스 중앙에 보라색 플러스 모양 룬을 만드세요. 사방에 최소 4픽셀의 투명 여백을 두고, 보이는 색은 최대 2개, 전체 형태는 가로·세로 완전 대칭, 하나로 연결되고 고립된 픽셀이 없어야 합니다.",
    "B1-T1-01": "16×16 투명 캔버스에 왼쪽을 향한 작은 은색 단검을 만드세요. 사방 최소 1픽셀 여백, 보이는 색 최대 5개, 하나로 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B1-T1-02": "16×16 투명 캔버스에 오른쪽 위로 기울어진 작은 초록 잎 아이콘을 만드세요. 사방 최소 2픽셀 여백, 보이는 색 최대 5개, 하나로 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B1-T2-01": "16×16 투명 캔버스에 어두운 바이저가 있는 정면 철제 투구를 만드세요. 중앙 배치, 사방 최소 1픽셀 여백, 보이는 색 최대 7개, 전체 형태 세로 대칭, 하나로 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B1-T2-02": "16×16 투명 캔버스에 어두운 교차 장작 위로 따뜻한 주황 불꽃이 올라오는 작은 모닥불을 만드세요. 사방 최소 1픽셀 여백, 보이는 색 최대 7개, 하나로 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B1-T3-01": "16×16 투명 캔버스에 금색 잠금장치가 있는 정면의 닫힌 보물상자를 만드세요. 중앙 배치, 사방 최소 1픽셀 여백, 보이는 색 최대 8개, 전체 형태 세로 대칭, 하나로 연결된 형태, 고립 픽셀 없음 조건입니다.",
    "B1-T3-02": "16×16 투명 캔버스에 옅은 줄기와 빨간 갓을 가진 작은 버섯을 만드세요. 중앙 배치, 사방 최소 1픽셀 여백, 보이는 색 최대 7개, 전체 형태 세로 대칭, 하나로 연결된 형태, 고립 픽셀 없음 조건입니다.",
}


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"{path} must contain an object")
    return cast(dict[str, object], value)


def _data_uri(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _task_texts(preregistration: Mapping[str, object]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in cast(list[object], preregistration["tasks"]):
        task = cast(dict[str, object], raw)
        out[cast(str, task["id"])] = cast(str, task["visible_text"])
    return out


def _source_png(results_root: Path, entry: Mapping[str, object]) -> bytes:
    task_id = cast(str, entry["task_id"])
    trial_index = cast(int, entry["trial_index"])
    review_id = cast(str, entry["review_id"])
    matches: list[Path] = []
    for method_id in B1_SCORED_METHOD_IDS:
        candidate_id = sha256(f"{task_id}|{trial_index}|{method_id}".encode("utf-8")).hexdigest()
        if candidate_id == review_id:
            matches.append(
                results_root
                / B1_FREEZE_COMMIT
                / method_id
                / task_id
                / f"trial-{trial_index:02d}"
                / "final.png"
            )
    if len(matches) != 1 or not matches[0].is_file():
        raise ValueError(f"cannot resolve blind source for {review_id}")
    return matches[0].read_bytes()


def _review_rows(results_root: Path, review_root: Path) -> tuple[dict[str, object], str, list[dict[str, object]]]:
    manifest_path = review_root / B1_FREEZE_COMMIT / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = cast(dict[str, object], json.loads(manifest_bytes))
    if manifest.get("schema") != "tracepixel.b1-blind-review-package.v1":
        raise ValueError("unexpected B1 review manifest schema")
    if manifest.get("freeze_commit") != B1_FREEZE_COMMIT or manifest.get("method_labels_exposed") is not False:
        raise ValueError("B1 review manifest is not frozen and blind")
    if tuple(cast(list[str], manifest.get("dimensions"))) != DIMENSIONS:
        raise ValueError("B1 review dimensions drifted")

    rows: list[dict[str, object]] = []
    entries = cast(list[object], manifest["entries"])
    if len(entries) != 28:
        raise ValueError("B1 mobile review requires exactly 28 blind entries")
    for raw in entries:
        entry = cast(dict[str, object], raw)
        preview_path = review_root / B1_FREEZE_COMMIT / cast(str, entry["preview"])
        native_png = _source_png(results_root, entry)
        rows.append({
            "review_id": entry["review_id"],
            "task_id": entry["task_id"],
            "trial_index": entry["trial_index"],
            "order": entry["order"],
            "native": _data_uri(native_png),
            "preview": _data_uri(preview_path.read_bytes()),
        })
    return manifest, sha256(manifest_bytes).hexdigest(), rows


def _page(
    preregistration: Mapping[str, object],
    manifest_sha: str,
    rows: Sequence[Mapping[str, object]],
    *,
    language: str,
) -> bytes:
    if language not in {"ko", "en"}:
        raise ValueError(language)
    canonical = _task_texts(preregistration)
    labels = {
        "ko": {
            "title": "TracePixel B1 블라인드 모바일 평가",
            "notice": "방법 이름은 숨겨져 있습니다. 28개 결과를 모두 1~5점으로 평가하세요. 편집은 하지 말고 보이는 결과만 판단합니다. 입력은 이 기기에 자동 저장됩니다.",
            "native": "원본 1배 (16×16)", "preview": "8배 확대",
            "recognizability": "무엇인지 알아보기 쉬운가", "readability_at_native_1x": "원본 1배에서도 잘 읽히는가", "style_coherence": "픽셀 스타일이 일관적인가",
            "reject": "사람 기준 탈락", "save": "평가 JSON 저장", "share": "평가 JSON 공유", "copy": "JSON 복사", "next": "다음 미평가",
            "missing": "아직 선택하지 않은 점수가 있습니다.", "ready": "28개 평가가 모두 완료되었습니다.", "copied": "JSON을 복사했습니다.",
            "canonical": "영문 원문 조건", "artifact": "결과", "progress": "진행", "low": "1 낮음", "high": "5 높음",
        },
        "en": {
            "title": "TracePixel B1 blind mobile review",
            "notice": "Method names are hidden. Rate all 28 outputs from 1 to 5. Do not edit the artifacts; judge only what is visible. Progress is saved on this device.",
            "native": "Native 1x (16×16)", "preview": "8x inspection",
            "recognizability": "Recognizability", "readability_at_native_1x": "Readability at native 1x", "style_coherence": "Style coherence",
            "reject": "Human rejection", "save": "Save review JSON", "share": "Share review JSON", "copy": "Copy JSON", "next": "Next unrated",
            "missing": "Some ratings are still missing.", "ready": "All 28 ratings are complete.", "copied": "JSON copied.",
            "canonical": "Canonical prompt", "artifact": "Artifact", "progress": "Progress", "low": "1 low", "high": "5 high",
        },
    }[language]

    grouped: dict[str, list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(cast(str, row["task_id"]), []).append(row)

    sections: list[str] = []
    for task_id in sorted(grouped):
        if language == "ko":
            task_text = (
                f'<p class="task-ko">{html.escape(_KO_TASKS[task_id])}</p>'
                f'<details><summary>{labels["canonical"]}</summary><p>{html.escape(canonical[task_id])}</p></details>'
            )
        else:
            task_text = f'<p class="task-ko">{html.escape(canonical[task_id])}</p>'
        cards: list[str] = []
        for row in sorted(grouped[task_id], key=lambda x: cast(int, x["order"])):
            rid = cast(str, row["review_id"])
            controls: list[str] = []
            for dim in DIMENSIONS:
                radios = "".join(
                    f'<label class="score"><input type="radio" name="{rid}:{dim}" value="{n}"><span>{n}</span></label>'
                    for n in range(1, 6)
                )
                controls.append(
                    f'<fieldset><legend>{labels[dim]}</legend><div class="hint"><span>{labels["low"]}</span><span>{labels["high"]}</span></div><div class="scores">{radios}</div></fieldset>'
                )
            cards.append(
                f'<article class="card" data-review-id="{rid}" data-task-id="{html.escape(task_id)}" '
                f'data-trial-index="{row["trial_index"]}" data-order="{row["order"]}">'
                f'<h3>{labels["artifact"]} {row["order"]}</h3>'
                f'<div class="images"><div><small>{labels["native"]}</small><div class="native"><img src="{row["native"]}" width="16" height="16" alt=""></div></div>'
                f'<div><small>{labels["preview"]}</small><div><img class="preview" src="{row["preview"]}" width="128" height="128" alt=""></div></div></div>'
                + "".join(controls)
                + f'<label class="reject"><input type="checkbox" class="reject-box"> {labels["reject"]}</label></article>'
            )
        sections.append(f'<section><h2>{html.escape(task_id)}</h2>{task_text}<div class="grid">{"".join(cards)}</div></section>')

    boot = {
        "schema": OWNER_REVIEW_SCHEMA_V1,
        "freeze_commit": B1_FREEZE_COMMIT,
        "review_manifest_sha256": manifest_sha,
        "evaluator_role": "repository owner",
        "dimensions": list(DIMENSIONS),
        "storage_key": f"tracepixel-b1-review-{manifest_sha}",
        "labels": {k: labels[k] for k in ("missing", "ready", "copied", "progress")},
    }
    boot_json = json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    companion = "index.en.html" if language == "ko" else "index.html"
    companion_label = "English" if language == "ko" else "한국어"

    page = f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="color-scheme" content="dark"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>{labels["title"]}</title><style>
:root{{color-scheme:dark}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#151515;color:#eee}}main{{max-width:900px;margin:auto;padding:12px 12px 116px}}a{{color:#9cc8ff}}.top{{position:sticky;top:0;z-index:5;background:#151515f2;backdrop-filter:blur(8px);padding:10px 0;border-bottom:1px solid #444}}h1{{font-size:1.35rem;margin:2px 0 6px}}h2{{margin-bottom:8px}}.notice,.card{{background:#202020;border:1px solid #444;border-radius:14px;padding:14px}}.notice{{line-height:1.55;margin-top:12px}}section{{margin-top:28px}}.task-ko{{font-size:1.02rem;line-height:1.6;margin-top:4px}}details{{color:#bbb;margin-bottom:12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}}.card{{scroll-margin-top:94px}}.images{{display:flex;gap:28px;align-items:end;justify-content:center;margin:8px 0 14px}}.native{{width:72px;height:72px;display:flex;align-items:center;justify-content:center;background:#2b2b2b;border-radius:8px;margin-top:8px}}.native img,.preview{{image-rendering:pixelated;image-rendering:crisp-edges}}.preview{{margin-top:8px;border-radius:8px}}fieldset{{border:1px solid #444;border-radius:10px;margin:12px 0;padding:10px}}legend{{padding:0 6px;line-height:1.35}}.hint{{display:flex;justify-content:space-between;color:#999;font-size:.75rem;margin-bottom:5px}}.scores{{display:grid;grid-template-columns:repeat(5,1fr);gap:7px}}.score input{{position:absolute;opacity:0;pointer-events:none}}.score span{{display:block;text-align:center;padding:11px 0;border:1px solid #555;border-radius:9px;background:#2b2b2b;font-weight:700}}.score input:checked+span{{outline:2px solid #9cc8ff;background:#394654}}.reject{{display:block;margin-top:10px;padding:8px 0}}.actions{{position:fixed;left:0;right:0;bottom:0;z-index:6;background:#151515f4;border-top:1px solid #444;padding:8px max(10px,env(safe-area-inset-right)) calc(8px + env(safe-area-inset-bottom)) max(10px,env(safe-area-inset-left));display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}}button{{min-height:44px;border-radius:10px;border:1px solid #666;background:#2b2b2b;color:#eee;font:inherit;font-size:.82rem;padding:5px}}#status{{position:fixed;left:12px;right:12px;bottom:72px;z-index:7;text-align:center;color:#ddd;background:#202020ee;border-radius:8px;padding:6px;pointer-events:none;opacity:0;transition:opacity .2s}}#status.show{{opacity:1}}@media(max-width:520px){{main{{padding-left:10px;padding-right:10px}}.grid{{grid-template-columns:1fr}}.images{{gap:22px}}fieldset{{padding:9px 7px}}.actions{{grid-template-columns:repeat(2,1fr)}}#status{{bottom:118px}}}}
</style></head><body><main><div class="top"><h1>{labels["title"]}</h1><a href="{companion}">{companion_label}</a> · <b id="progress">{labels["progress"]}: 0/28</b></div><div class="notice">{labels["notice"]}</div>{''.join(sections)}</main><div class="actions"><button id="next">{labels["next"]}</button><button id="save">{labels["save"]}</button><button id="share">{labels["share"]}</button><button id="copy">{labels["copy"]}</button></div><span id="status"></span><script id="boot" type="application/json">{boot_json}</script><script>
(()=>{{const B=JSON.parse(document.getElementById('boot').textContent),D=B.dimensions,S=document.getElementById('status'),P=document.getElementById('progress'),cards=[...document.querySelectorAll('.card')];let timer;function toast(t){{S.textContent=t;S.classList.add('show');clearTimeout(timer);timer=setTimeout(()=>S.classList.remove('show'),1800)}}function collect(requireAll=true){{const ratings=[],missing=[];for(const c of cards){{const r={{review_id:c.dataset.reviewId,task_id:c.dataset.taskId,trial_index:Number(c.dataset.trialIndex),order:Number(c.dataset.order),human_rejection:c.querySelector('.reject-box').checked}};for(const d of D){{const x=c.querySelector('input[name="'+c.dataset.reviewId+':'+d+'"]:checked');if(!x)missing.push(c.dataset.reviewId+':'+d);else r[d]=Number(x.value)}}ratings.push(r)}}if(requireAll&&missing.length)throw Error(B.labels.missing);return {{ratings,missing}}}}function payload(){{return {{schema:B.schema,freeze_commit:B.freeze_commit,review_manifest_sha256:B.review_manifest_sha256,evaluator_role:B.evaluator_role,dimensions:D,ratings:collect(true).ratings}}}}function text(){{return JSON.stringify(payload())+'\\n'}}function update(){{const x=collect(false),done=x.ratings.filter(r=>D.every(d=>Number.isInteger(r[d]))).length;P.textContent=B.labels.progress+': '+done+'/'+cards.length;try{{localStorage.setItem(B.storage_key,JSON.stringify(x.ratings))}}catch(e){{}}}}function restore(){{try{{const xs=JSON.parse(localStorage.getItem(B.storage_key)||'[]');for(const r of xs){{const c=cards.find(x=>x.dataset.reviewId===r.review_id);if(!c)continue;for(const d of D){{const q=c.querySelector('input[name="'+r.review_id+':'+d+'"][value="'+r[d]+'"]');if(q)q.checked=true}}c.querySelector('.reject-box').checked=!!r.human_rejection}}}}catch(e){{}}update()}}function blob(){{return new Blob([text()],{{type:'application/json'}})}}async function copyText(v){{if(navigator.clipboard&&window.isSecureContext){{await navigator.clipboard.writeText(v);return}}const t=document.createElement('textarea');t.value=v;t.style.position='fixed';t.style.opacity='0';document.body.appendChild(t);t.focus();t.select();document.execCommand('copy');t.remove()}}document.body.addEventListener('change',update);document.getElementById('next').onclick=()=>{{const c=cards.find(c=>D.some(d=>!c.querySelector('input[name="'+c.dataset.reviewId+':'+d+'"]:checked')));if(c)c.scrollIntoView({{behavior:'smooth',block:'start'}});else toast(B.labels.ready)}};document.getElementById('save').onclick=()=>{{try{{const u=URL.createObjectURL(blob()),a=document.createElement('a');a.href=u;a.download='tracepixel-b1-owner-review.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);toast(B.labels.ready)}}catch(e){{toast(e.message)}}}};document.getElementById('copy').onclick=async()=>{{try{{await copyText(text());toast(B.labels.copied)}}catch(e){{toast(e.message)}}}};document.getElementById('share').onclick=async()=>{{try{{const file=new File([text()],'tracepixel-b1-owner-review.json',{{type:'application/json'}});if(navigator.share&&navigator.canShare&&navigator.canShare({{files:[file]}}))await navigator.share({{files:[file],title:'TracePixel B1 owner review'}});else{{await copyText(text());toast(B.labels.copied)}}}}catch(e){{if(e.name!=='AbortError')toast(e.message)}}}};restore()}})();
</script></body></html>'''
    banned = tuple(B1_SCORED_METHOD_IDS)
    if any(token in page for token in banned):
        raise ValueError("method label leaked into mobile review page")
    return page.encode("utf-8")


def build_package(
    output: Path,
    *,
    preregistration_path: Path = DEFAULT_PREREGISTRATION,
    results_root: Path = DEFAULT_RESULTS_ROOT,
    review_root: Path = DEFAULT_REVIEW_ROOT,
    source_sha: str = "unknown",
) -> dict[str, object]:
    preregistration = _load_json(preregistration_path)
    manifest, manifest_sha, rows = _review_rows(results_root, review_root)
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_bytes(_page(preregistration, manifest_sha, rows, language="ko"))
    (output / "index.en.html").write_bytes(_page(preregistration, manifest_sha, rows, language="en"))
    package = {
        "schema": MOBILE_REVIEW_SCHEMA_V1,
        "freeze_commit": B1_FREEZE_COMMIT,
        "source_sha": source_sha,
        "review_manifest_sha256": manifest_sha,
        "entry_count": len(rows),
        "method_labels_exposed": False,
        "offline": True,
        "files": ["index.html", "index.en.html"],
        "review_schema": OWNER_REVIEW_SCHEMA_V1,
        "manifest_schema": manifest["schema"],
    }
    (output / "package.json").write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return package


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the B1 owner-only blind mobile review package")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", default="unknown")
    args = parser.parse_args(argv)
    print(json.dumps(build_package(args.output, source_sha=args.source_sha), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
