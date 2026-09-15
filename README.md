# FM Graphics Reload

**Free FM26 graphics refresh and skin management for Windows.**  
**Windows용 무료 FM26 그래픽 새로고침·스킨 관리 프로그램입니다.**

by **JunHo** · **MIT License**

[Download / 다운로드](https://github.com/dev-junos/FM-Graphics-Reload/releases/latest) · [User guide / 사용 안내](사용%20안내.md) · [Changelog / 변경 내역](CHANGELOG.md)

## English

FM Graphics Reload refreshes player faces, logos and other graphics, and manages partial skin/theme packs from one compact window. It is an independent utility for Football Manager 26.

### Getting started

1. Download the **EXE from the [latest release](https://github.com/dev-junos/FM-Graphics-Reload/releases/latest)** and run it. No separate Python installation is required.
2. Check the graphics folder and game installation folder. Select them manually if automatic detection cannot find them.
3. Drop a skin folder or ZIP into the app, or use `+` to add it. Skin subfolders are discovered separately and copied into the app's local storage.
4. Toggle skins and drag to change priority. Higher entries win file conflicts. Ctrl multi-selection and bulk removal are supported.
5. While FM is running, click **Check game connection** and use the bottom buttons when the game is idle.

| Button | Action |
|---|---|
| Refresh | Refresh faces, logos and other graphics |
| Apply skins | Update the live screen with the selected skins/themes |
| Apply all | Run graphics refresh and skin application together |

English is the default for new settings. Existing language preferences are preserved; use the selector at the top right to switch to Korean.

### Saved selections and installed files

- **FM closed:** selection changes are written to the installation with backups. Turning a skin off restores the next enabled provider or the backed-up file.
- **FM running:** selections are saved; use the apply buttons to update the live screen. Installation writes wait until FM exits while this app remains open.
- Closing the app keeps pending work. Reopen it with FM closed to retry installation writes. Closing without changes does not repeat the pending-installation notice.
- Settings, imported skins, backups and caches are stored in `%LOCALAPPDATA%\FM Graphics Reload`.

### Maintenance menu

Open **▾ next to Delete** to use these tools.

| Tool | What it does and when to use it |
|---|---|
| Reset skin baseline | With FM closed, adopts the files currently in the game installation folder as the new baseline and switches all skin selections OFF. Use this after manually replacing installed skin files. Installed files stay as they are; imported skins and previous backups are kept. This does not restore the game's original skin. |
| Clear cache | With FM closed, deletes this app's temporary skin preparation cache and previous live-refresh session data. Use it to rebuild prepared files when troubleshooting. Installed files, imported skins and recovery backups are kept. The next skin application may take longer while files are prepared again. This clears the app's cache, not FM's own cache. |
| Retry pending file save | Appears only when installation changes are waiting to be saved. After closing FM, use it to retry writing the current skin selections and priority order to the game installation folder, for example after resolving a file-access error. While FM is running, installation writes remain queued; this does not refresh the live game screen. |

### Compatibility

Windows x64 and the supported **FM26 26.3.2** build are required. Game files are checked against the hashes in `runtime/profile.json` before connection. New, missing or changed-since-start bundles are blocked during live application; close FM to install new bundles. Compatibility with every skin is not guaranteed. Repeated application of different large skins can reach the retained-resource limit.

If the app reports that the loaded game connection module is incompatible, restart FM and check the connection again. Korean/English GUI initialization and automated close-behavior checks were verified; repeated live skin swaps and clean-PC execution/builds have not all been verified.

## 한국어

FM Graphics Reload는 선수 페이스·로고 등 그래픽 새로고침과 부분 스킨·테마 관리를 한 화면에서 지원합니다. Football Manager 26을 위한 독립적인 유틸리티입니다.

### 시작하기

1. **[최신 릴리스](https://github.com/dev-junos/FM-Graphics-Reload/releases/latest)의 EXE 파일**을 다운로드해 실행합니다. Python 설치가 필요 없는 단일 EXE입니다.
2. 처음 실행하면 영어로 표시됩니다. 오른쪽 위 언어 선택에서 **한국어**로 바꿀 수 있으며, 기존 사용자의 언어 설정은 유지합니다.
3. 페이스·로고 폴더와 게임 설치 폴더를 확인합니다. 자동으로 찾지 못하면 직접 선택합니다.
4. 스킨 폴더·ZIP을 끌어 놓거나 `+`로 등록합니다. 하위 폴더의 스킨도 찾아 각각 등록하고 프로그램 저장 폴더로 복사합니다.
5. 토글로 스킨을 켜고 드래그·화살표로 우선순위를 정합니다. 목록 위쪽이 우선하며 Ctrl 다중 선택과 일괄 삭제를 지원합니다.
6. 게임 실행 중에는 **게임 연결 확인** 후 게임이 대기 상태일 때 아래 적용 버튼을 사용합니다.

| 버튼 | 기능 |
|---|---|
| 새로고침 | 페이스·로고 등 그래픽 새로고침 |
| 스킨 적용 | 선택한 스킨·테마로 현재 게임 화면 갱신 |
| 전체 적용 | 그래픽 새로고침과 스킨 적용을 함께 실행 |

### 저장과 적용

- **FM 종료 상태:** 선택 변경을 설치 파일에 반영하고 변경 전 파일을 백업합니다. 스킨을 끄면 다음 우선순위의 스킨이나 백업 파일로 되돌립니다.
- **FM 실행 상태:** 선택을 저장하고 적용 버튼으로 화면을 갱신합니다. 설치 파일은 FM 종료 후 이 프로그램이 열려 있을 때 자동 반영합니다.
- 프로그램을 닫아도 반영 대기 작업은 유지됩니다. FM이 꺼진 상태에서 다시 실행하면 반영을 재시도합니다. 시작 후 변경 없이 닫으면 확인창이 반복되지 않습니다.
- 설정·등록한 스킨·백업·캐시는 `%LOCALAPPDATA%\FM Graphics Reload`에 보관합니다.

### 초기화와 저장 재시도

**삭제 버튼 옆 ▾ 메뉴**에서 사용할 수 있습니다.

| 기능 | 동작과 사용 시점 |
|---|---|
| 스킨 기준 초기화 | FM을 종료한 상태에서 현재 게임 설치 폴더의 파일을 새 기준으로 삼고 모든 스킨 선택을 OFF로 바꿉니다. 사용자가 설치 파일을 직접 교체한 뒤 그 상태를 기준으로 관리하려 할 때 사용합니다. 설치 파일은 그대로 두며, 등록 스킨과 이전 백업은 보관합니다. 게임의 순정 스킨으로 복원하는 기능은 아닙니다. |
| 캐시 초기화 | FM을 종료한 상태에서 이 프로그램의 임시 스킨 준비 파일과 이전 실행의 화면 갱신 자료를 삭제합니다. 준비 파일을 다시 만들어 문제를 확인할 때 사용합니다. 설치 파일·등록 스킨·복원용 백업은 유지되며, 다음 스킨 적용은 파일을 다시 준비하느라 더 오래 걸릴 수 있습니다. FM 자체 캐시를 지우는 기능은 아닙니다. |
| 대기 중인 설치 파일 저장 재시도 | 설치 파일에 반영할 작업이 대기 중일 때만 표시됩니다. FM을 종료한 뒤 현재 스킨 선택과 우선순위를 설치 폴더에 다시 저장합니다. 파일 접근 오류 등을 해결한 뒤 수동으로 재시도할 때 사용합니다. FM이 실행 중이면 설치 파일 저장은 계속 대기하며, 게임 화면을 새로고침하는 기능은 아닙니다. |

### 지원 환경과 제한

Windows x64와 지원 대상 **FM26 26.3.2** 빌드가 필요합니다. 게임 연결 전 `runtime/profile.json`의 해시와 대조합니다. 게임 실행 중에는 누락·신규·게임 시작 후 변경된 번들을 차단하며, 새 번들은 FM 종료 후 설치해야 합니다. 모든 스킨의 내부 자원 호환성을 보장하지 않습니다. 서로 다른 대형 스킨을 반복 적용하면 메모리 보관 한도에 도달할 수 있습니다.

이미 연결된 게임 모듈과 호환되지 않는다는 안내가 나오면 FM을 재시작한 뒤 게임 연결을 다시 확인하세요. 한글·영문 GUI 초기화와 종료 동작 자동 검사를 수행했으며, 실제 게임의 반복 스킨 교체 및 다른 PC에서의 실행·재빌드를 모두 검증한 것은 아닙니다.

## Optional support / 선택적 후원

All features are free. Use **Support development** at the bottom right for the QR code or Ko-fi page. Donations are optional.

모든 기능은 무료이며 후원은 선택입니다. 오른쪽 아래 **후원하기**에서 QR 또는 Ko-fi 후원 페이지를 열 수 있습니다.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Y7I7271PYH)

## Build from source / 소스 빌드

Use Windows x64, CPython 3.12 x64 with Tcl/Tk, and Zig 0.16.0. MinHook source and licenses are included.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build.ps1 -Python .\.venv\Scripts\python.exe -Zig C:\Tools\zig\zig.exe -OutputFolder dist
```

The built EXE is saved in `dist/`; its filename includes the version defined in `app/version.py`. Set `-Zig` to your installed Zig executable. The first build must compile the native DLL; use `-SkipNative` only when reusing an existing build of that DLL.

빌드한 EXE는 `dist/`에 생성되며, 파일 이름에는 `app/version.py`에 정의된 버전이 붙습니다.

`-Zig`에는 설치한 Zig 실행 파일 경로를 지정하세요. 최초 빌드는 DLL을 생성해야 하므로 `-SkipNative` 없이 실행하며, 기존 DLL을 재사용할 때만 해당 옵션을 사용합니다.

Builds check Tcl/Tk startup and the packaged GUI resources. `--self-test --output result.json` checks the EXE's Korean/English UI and donation window with an isolated temporary library. `python packaging/source_archive.py` creates a source-only release ZIP.

| Path | Contents / 내용 |
|---|---|
| `app/` | UI, skin management, backups, refresh / 화면·스킨 관리·백업·새로고침 |
| `native/` | Native bridge source / 게임 연결 DLL 소스 |
| `runtime/profile.json` | Supported game hashes / 지원 게임 식별 해시 |
| `assets/` | Icons and donation QR / 아이콘·후원 QR |
| `packaging/` | EXE build and source packaging / 실행파일·소스 패키징 |
| `tests/` | Automated checks / 자동 검사 |
| `vendor/minhook/` | MinHook source and license / MinHook 소스·라이선스 |

## License / 라이선스

Project code is [MIT](LICENSE). Third-party components retain their own licenses; see [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) and the included license files. Game files, third-party skins, user settings, logs and backups are not distributed. Unused UnityPy audio conversion is disabled; the FMOD audio SDK is not bundled.

프로젝트 코드는 [MIT](LICENSE)로 공개합니다. 외부 구성 요소의 라이선스와 고지문을 함께 제공합니다. 게임 원본·타인의 스킨·사용자 설정·로그·백업은 배포하지 않으며 FMOD 오디오 SDK도 포함하지 않습니다.

Football Manager and its assets belong to their respective rights holders. This is an independent utility by JunHo, not an official product.

Football Manager 및 관련 게임 자산은 해당 권리자의 자산입니다. JunHo가 제작한 독립적인 유틸리티이며 공식 제품이 아닙니다.
