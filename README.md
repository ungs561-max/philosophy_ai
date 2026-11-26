# 철학자의 서재 · Streamlit 배포판

기존 Node 미리보기의 HTML, CSS, 일러스트와 대화 화면을 Streamlit Custom Component v2로 옮겼습니다. 글을 입력하는 동안에는 브라우저에서 인물만 바뀝니다. 메시지를 보내면 Streamlit이 Dify에 요청하고 브라우저는 응답 조각을 받아 그림과 답변을 갱신합니다. 브라우저의 현재 탭에서 새로고침해도 대화 기록이 남습니다. Node 미리보기의 기록과 과거 Streamlit 세션은 각 실행 환경의 기록입니다.

Windows에서 Python 3.12와 Streamlit 1.67.0으로 확인했습니다. 운영 또는 테스트 브랜치를 병합하기 전에 별도 Community Cloud 주소에서 Linux 빌드와 실제 Dify 응답을 확인하세요.

## Windows에서 실행

Python 3.12를 사용할 수 있는 PowerShell에서 이 폴더를 열고 아래를 순서대로 실행합니다. 탐색기 주소창에 `powershell`을 입력하면 이 폴더에서 바로 열립니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

브라우저에서 [로컬 서재](http://localhost:8501)를 엽니다. 우측 상단 **테스트 모드**를 누르면 비밀 키 없이 네 철학자와 상담·공부를 시험할 수 있습니다. 실행을 종료하려면 PowerShell에서 Ctrl+C를 누릅니다.

실제 응답을 로컬에서 확인하려면 다음 명령으로 비밀 설정 파일을 만든 뒤, 해당하는 줄의 따옴표 사이에 실제 키를 입력하고 서버를 다시 실행합니다.

```powershell
Copy-Item -LiteralPath '.streamlit/secrets.example.toml' -Destination '.streamlit/secrets.toml'
notepad .streamlit/secrets.toml
```

## GitHub의 검증용 브랜치에 올리기

1. GitHub Desktop에서 저장소 쓰기 권한이 있는 계정으로 로그인합니다. **File → Clone repository → URL**을 선택합니다. URL에 `https://github.com/ungs561-max/philosophy_ai.git`을 입력하고, 작업 폴더와 다른 새 복제 위치를 고른 뒤 **Clone**을 누릅니다.
2. **Current Branch**에서 `main`을 선택하고 **Fetch origin**을 누릅니다. 새 변경 사항이 있으면 **Pull origin**을 누릅니다. 이 시점의 운영 코드 보관이 필요하면 **Branch → New Branch**에서 `backup-before-streamlit-library`를 만들고 **Publish branch**로 보관한 뒤 `main`으로 돌아옵니다.
3. `main`에서 **Branch → New Branch**를 눌러 `streamlit-library-preview`를 만듭니다. **Repository → Show in Explorer**로 복제한 저장소를 엽니다. 이 배포판 폴더의 내용물을 복제한 저장소의 최상위에 붙여넣습니다. `streamlit_app.py`가 최상위에 있어야 합니다. 로컬에서 만들었을 수 있는 `.venv`, `__pycache__`, `.streamlit/secrets.toml`은 복사 대상에서 제외합니다. 기존 저장소에 별도 `.gitignore` 규칙이 있으면 두 파일의 규칙을 합칩니다.
4. GitHub Desktop의 **Changes**에서 파일 목록을 확인합니다. 특히 비밀 설정 파일이 목록에 없는지 확인합니다. Summary에 `철학자의 서재 Streamlit 화면 전환`을 입력하고 **Commit to streamlit-library-preview → Publish branch**를 누릅니다.
5. [Streamlit Community Cloud](https://share.streamlit.io/)에서 **Create app → Deploy a public app from GitHub**를 선택합니다. 저장소에 `ungs561-max/philosophy_ai`, Branch에 `streamlit-library-preview`, Main file path에 `streamlit_app.py`를 입력하고 운영 주소와 다른 테스트 주소를 지정합니다. 에픽테토스 실응답 테스트가 필요하면 **Advanced settings → Secrets**에 해당 키 두 개만 설정하고 **Deploy**합니다.
6. 테스트 주소에서 네 인물의 그림, 테스트 대화, 에픽테토스 상담·공부 실제 응답, 모바일 입력을 확인합니다. Community Cloud의 **Manage app** 로그에서도 오류 여부를 확인합니다.

## 기존 서비스 주소에 적용

1. [운영 앱](https://philosophyai-gbne5qs6zn8y43ah5pulpq.streamlit.app/)의 소스 버튼 기준으로 저장소는 `ungs561-max/philosophy_ai`, 브랜치는 `main`, 실행 파일은 `streamlit_app.py`입니다. 운영 계정으로 Cloud 관리 화면에서 이 세 값을 확인합니다.
2. 별도 테스트 주소에서 검증이 끝나면 GitHub Desktop의 **Create Pull Request**를 누릅니다. GitHub에서 **base: main**, **compare: streamlit-library-preview**를 확인하고 **Create pull request**를 누릅니다. 검토를 마치면 **Squash and merge → Confirm squash and merge**를 선택합니다.
3. 기존 앱은 같은 저장소·브랜치·실행 파일을 계속 쓰므로 기존 주소에서 새 빌드를 확인합니다. **Manage app**에서 배포 로그를 확인하고 기존 Secrets로 에픽테토스 상담과 공부를 각각 시험합니다. 필요할 때만 Cloud 앱 메뉴에서 **Reboot**를 선택합니다. 기존 운영 앱을 삭제하거나 새로 만들 필요가 없습니다.

## Streamlit Secrets에 키 추가

운영 앱의 Cloud 목록에서 해당 앱의 **⋮ → Settings → Secrets**를 엽니다. 이미 설정된 값을 유지하면서 준비된 이름만 추가한 뒤 **Save changes**를 누릅니다. 값 형식은 `키이름 = "발급받은 값"`입니다. 이 예시의 빈 값으로 기존 키를 덮어쓰지 마세요.

| 철학자 | 상담 | 공부 |
| --- | --- | --- |
| 에픽테토스 | `DIFY_COUNSEL_KEY` | `DIFY_STUDY_KEY` |
| 노자 | `DIFY_LAOZI_COUNSEL_KEY` | `DIFY_LAOZI_STUDY_KEY` |
| 애덤 스미스 | `DIFY_SMITH_COUNSEL_KEY` | `DIFY_SMITH_STUDY_KEY` |
| 알베르 카뮈 | `DIFY_CAMUS_COUNSEL_KEY` | `DIFY_CAMUS_STUDY_KEY` |

키는 해당 철학자·모드의 Dify 채팅 앱에서 발급한 키를 입력합니다. 기존 Dify Cloud 채팅 API, 빈 `inputs`, 카드의 `query` 형식을 사용합니다. 키가 없는 모드는 **연결 준비 중**으로 표시됩니다. 공용 테스트 응답은 Dify 호출 없이 생성됩니다.

## 문제가 생겼을 때 복구

GitHub에서 반영한 PR을 열고 **Revert → Create pull request → Merge pull request** 순서로 되돌립니다. 그 다음 기존 Streamlit 주소의 빌드와 기본 화면을 확인합니다. **Revert** 버튼이 없으면 GitHub Desktop에서 **Current Branch → main → Fetch origin → Pull origin**을 누르고, 복구용 브랜치를 만든 뒤 **History**에서 해당 squash 커밋을 우클릭해 **Revert changes in commit**을 선택합니다. 이 브랜치를 게시하고 `main`으로 PR을 만들어 병합합니다. 기존 운영 Secrets는 그대로 두면 됩니다.

[Community Cloud 배포 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) · [Secrets 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) · [재시작 안내](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app)
