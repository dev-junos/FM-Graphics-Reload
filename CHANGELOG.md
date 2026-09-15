# Changelog / 변경 내역

## 1.0.0 — 2026-09-15

- Fix partial skin preparation failing with `Could not identify skin script: ParsedAds`: retain the installed MonoScript catalog alongside startup backups for metadata lookup.
- Validate and protect catalog files before copying. Unchanged catalog bundles are not added to live replacements; their hashes participate in prepared-cache identity.
- 부분 스킨 준비 시 공통 스크립트 정보가 빠져 `스킨의 스크립트 정보를 확인하지 못했습니다: ParsedAds`로 중단되던 문제를 수정했습니다.
- 기존 실행의 부분 백업에도 확인된 스크립트 정보를 보충하며, 바뀌지 않은 정보 파일은 게임 화면 교체 대상에 추가하지 않습니다. 게임 연결 모듈은 동일합니다.

- First public release with a standalone Windows EXE and MIT source.
- English is the default language. Existing language preferences are preserved.
- Smaller donation button at the bottom right.
- Includes the 0.22 fix: closing without changes no longer repeats the pending-installation notice. Pending work is preserved.
- Graphics refresh, skin folder/ZIP imports, toggles, priority ordering and multi-selection.
- Korean/English UI, DPI scaling and multiple icon resolutions.
- Native game bridge unchanged from 0.17–0.22.

- 단일 Windows EXE와 MIT 소스를 제공하는 첫 공개 버전입니다.
- 기본 언어는 영어이며 기존 사용자의 언어 선택은 유지합니다.
- 오른쪽 아래 후원 버튼의 크기를 줄였습니다.
- 변경 없이 닫을 때 확인창이 반복되지 않는 0.22 수정을 포함하며, 설치 파일 반영 대기 작업은 유지합니다.
- 그래픽 새로고침, 스킨 폴더·ZIP 등록, 토글, 우선순위와 다중 선택을 지원합니다.
- 한국어·영어 UI, 고배율 표시와 여러 해상도의 아이콘을 제공합니다.
- 게임 연결 모듈은 0.17~0.22와 같습니다.
