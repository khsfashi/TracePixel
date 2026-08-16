# P6-V5 모바일 검토 요약

실제 trusted artifact에는 `index.html`(영문), `index.ko.html`(한글), `manifest.json`이 포함됩니다.

한글 페이지는 UI와 설명을 번역하지만 stage 식별자, ArtIntent JSON 키, 원본 QA/Agent 증거 내부 문자열은 증거 의미를 바꾸지 않기 위해 원문을 유지할 수 있습니다.

`separate-reference`가 표시되면 단계 이미지는 최종 결과의 실제 중간 과정이 아닙니다. 현재 frozen P5-A5 최종 결과가 이 경우이며, 별도 P3 stage workflow 참고 자료와 시각적으로 다른 것이 정상입니다.

`bundle-stage-artifacts`가 표시되는 경우에만 contact sheet의 모든 stage가 최종 preview bundle의 source path와 SHA-256에 정확히 연결되어 있습니다.

Android에서 `content://` 방식으로 HTML을 열었을 때 상대 링크가 동작하지 않으면 압축 해제 폴더에서 `index.ko.html` 또는 `index.html`을 직접 열면 됩니다. 두 페이지 모두 JavaScript와 외부 리소스 없이 독립적으로 렌더링됩니다.
