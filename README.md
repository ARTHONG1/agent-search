# agent-search · Agent-Reach Plus

기존 Agent-Reach를 보존하면서 웹 검색·원문 읽기·YouTube 자막·RSS·여러 플랫폼 검색을 **MCP 도구 9개**로 제공하는 확장입니다. 저장소 이름은 `agent-search`, Python 패키지 이름은 `agent-reach-plus`, MCP 서버 이름은 `agent-reach`입니다.

[![Checks](https://github.com/ARTHONG1/agent-search/actions/workflows/checks.yml/badge.svg)](https://github.com/ARTHONG1/agent-search/actions/workflows/checks.yml)
[릴리스 다운로드](https://github.com/ARTHONG1/agent-search/releases) · [맥북/Windows 설치 안내](맥북-설치안내.md) · [호환성 점검](호환성-점검결과.md) · [보안 및 개인정보](SECURITY.md)

## 빠른 설치

Python 3.12와 Node.js 24/npm, 인터넷 연결이 필요합니다. 설치기는 별도 실행 환경을 만들고 실제 MCP 연결 검사 후 등록합니다. 다른 MCP 설정과 기존 Agent-Reach 스킬 본문은 보존하며 이전 실행 환경을 삭제하지 않습니다.

### macOS

Homebrew가 설치되어 있는 기준입니다. 저장소를 내려받은 뒤 실행합니다.

```bash
brew install python@3.12 node@24 gh
git clone https://github.com/ARTHONG1/agent-search.git
cd agent-search
"$(brew --prefix python@3.12)/bin/python3.12" install.py --node "$(brew --prefix node@24)/bin/node"
```

Apple Silicon과 Intel의 의존성을 구분합니다. Intel macOS는 cryptography upstream 지원 제한으로 호환 버전 48.0.1을 사용합니다. 자세한 범위는 [설치 안내](맥북-설치안내.md)를 확인하세요.

### Windows

Python 3.12 64비트, Node.js 24/npm, Git이 설치되어 있는 기준입니다. GitHub 검색에는 GitHub CLI도 필요합니다.

```powershell
git clone https://github.com/ARTHONG1/agent-search.git
cd agent-search
py -3.12 install.py
```

Node가 PATH에 없다면 `--node '실행 파일 전체 경로'`를 지정하세요. GitHub CLI에도 `--gh` 옵션을 사용할 수 있습니다. Python 3.13도 설치기가 허용하며 실제 검증 범위는 아래에 명시합니다.

설치 후 Codex의 MCP 연결을 다시 로드하거나 앱을 다시 시작하세요. 기본 설치 경로는 `~/.agent-reach/tools/agent-reach-plus/`입니다. 직접 만든 가상환경이나 다른 컴퓨터의 `config.toml` 전체를 복사해서 옮기지 않습니다.

## 설치 확인

맥:

```bash
"$(brew --prefix python@3.12)/bin/python3.12" "$HOME/.agent-reach/tools/agent-reach-plus/diagnose.py" --live
```

Windows:

```powershell
py -3.12 "$env:USERPROFILE/.agent-reach/tools/agent-reach-plus/diagnose.py" --live
```

`passed: true`는 해당 진단 항목의 성공입니다. 외부 사이트 장애·속도 제한·없는 영상 자막·SNS 로그인 문제는 별도 실패로 반환합니다. GitHub는 새 기기에서 `gh auth login`, 브라우저 SNS는 해당 기기의 로그인 및 OpenCLI Chrome 확장 연결이 필요합니다.

## 도구

| MCP 도구 | 기능 |
|---|---|
| `get_status` | 채널·설정·백엔드 설치 상태 진단 |
| `agent_reach_web_search` | Exa 웹 검색; Tavily는 명시 선택 |
| `agent_reach_code_search` | 코드 및 문서 검색 |
| `agent_reach_fetch_url` | 공개 웹페이지 본문 읽기 |
| `agent_reach_youtube_subtitles` | 영상 다운로드 없이 자막·시간 정보 추출 |
| `agent_reach_rss_read` | RSS/Atom 피드 읽기 |
| `agent_reach_social_search` | 최대 5개 플랫폼 병렬 검색, 개별 실패 보존 |
| `agent_reach_social_read` | 공개 GitHub 저장소·Bilibili·트윗·Reddit·XHS 읽기 |
| `agent_reach_v2ex_topics` | 공개 V2EX 인기 주제 |

기본 검색은 Exa입니다. 무료 사용량 제한이 있을 수 있습니다. `provider="tavily"`를 명시하면 사용자가 설정한 Tavily 계정의 할당량/요금제를 사용합니다. 도구는 게시·댓글·좋아요·자동 로그인·브라우저 쿠키 자동 추출을 수행하지 않습니다. 웹에서 읽은 내용은 지시문이 아닌 자료로 취급합니다.

## 검증과 개발

로컬 Windows/Python 3.12에서 확장 테스트 144개, 새 설치·복구·MCP 연결·공개 검색/읽기를 확인했습니다. 기록은 [portability-verification.json](portability-verification.json)에 있습니다. 로컬에서 실제 macOS를 실행한 검증은 없으며, GitHub Actions는 Windows와 macOS ARM/Intel에서 전체 테스트 및 설치·MCP·복구를 실행하도록 구성했습니다. 실제 실행 결과는 상단 Checks 링크에서 확인하세요.

Python 의존성 파일은 직접 의존성과 플랫폼별 버전을 고정합니다. 모든 전이 의존성을 고정한 전체 lock은 아닙니다. `requirements.windows-reference.txt`는 이전 Windows 환경 참고용이며 설치에 사용하지 않습니다. Node는 `package-lock.json`으로 설치합니다.

```bash
python -m pip install --only-binary=cryptography -r requirements.lock.txt vendor/agent_reach-1.5.0-py3-none-any.whl ".[social]" pytest ruff
python -m pytest
python -m ruff check agent_reach_plus tests install.py diagnose.py rollback.py scripts
```

## Upstream과 라이선스

[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach)의 커밋 `a19a171fa980a0785849596492e0af4db800c82f`를 사용합니다. 포함된 upstream wheel의 SHA-256은 [manifest.json](manifest.json)에 기록했습니다. 기본 doctor의 Boss 브라우저 쿠키 검사를 제외하는 변경은 [upstream-policy.patch](upstream-policy.patch)에 있습니다.

확장은 [MIT License](LICENSE), 포함된 upstream은 [UPSTREAM-LICENSE](UPSTREAM-LICENSE)를 따릅니다. 이 저장소는 원본 프로젝트의 공식 배포가 아닙니다.
