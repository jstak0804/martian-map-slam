# 해커톤 중 원격 Claude Code로 데이터 다루기

휴대폰이나 다른 컴퓨터에서 이 WSL 세션의 Claude Code에 접속해 진행할 때 쓰는 방법입니다. 채팅에 아래 예시 문장을 그대로 보내면 됩니다. 명령은 Claude가 `code/` 폴더에서 실행합니다.

## 0. 공식 자료가 올라왔는지 확인
> "챌린지 자료 올라왔는지 확인해줘"

```bash
python -m hackathon.challenge_watch              # Resources 탭 글과 링크, 지난번과 달라진 점
python -m hackathon.challenge_watch --download   # 자료로 보이는 링크를 받아서 풀고 접수까지
```

- **어떻게 읽나:** 챌린지 페이지의 Resources 탭은 화면이 뜬 뒤 Space Apps API에서 불러옵니다. 이 도구가 같은 요청을 직접 보냅니다.
- **기록:** `outputs/hackathon/challenge/`에 시각별로 남습니다.
- **2026-11-13 확인 결과:** "Resources will be available on Friday, November 13."

## 1. 링크로 받기 (가장 간단)
> "이 링크들 받아서 돌려줘: https://... https://..."

```bash
python -m hackathon.fetch <링크> [<링크> ...]          # ../data/hackathon_2026 에 받고 풀고 intake까지
python -m hackathon.fetch --list <폴더 목록 링크> --pattern '\.csv$'   # PDS 같은 폴더 목록에서 파일만 보기
python -m hackathon.fetch --crawl <폴더 목록 링크> --pattern '\.IMG$'  # 골라서 받기
```

처리할 수 있는 링크는 다음과 같습니다.
- **일반 파일:** 끊기면 이어받습니다.
- **Google Drive 파일 공유 링크**
- **Dropbox 링크**
- **GitHub 파일·릴리스**
- **폴더 목록 페이지:** PDS 같은 Apache 목록

받은 파일은 `sources.json`에 링크, 크기, SHA-256으로 기록됩니다.

## 2. 팀원이 가진 파일을 넘길 때

| 방법 | 맞는 경우 | 하는 일 |
|---|---|---|
| **Google Drive 파일 링크** | 대부분 (크기 제한 사실상 없음) | 파일 공유를 "링크가 있는 모든 사용자"로 바꾸고 링크를 채팅에 붙여 넣기. `fetch`가 받음 |
| **Google Drive 커넥터** | 작은 파일(수 MB 이하 CSV·문서), 폴더 안 파일 찾기 | "Drive의 ○○ 폴더에 있는 CSV 받아줘". Claude가 Drive 검색 후 내용을 받아 저장. 큰 파일은 위의 링크 방식으로 |
| **GitHub 릴리스** (`jstak0804/martian-map-slam`) | 수백 MB~2 GB 파일 | GitHub 웹 → Releases → Draft a new release에 파일 첨부 → 릴리스 링크를 채팅에. **공개 저장소라 누구나 받을 수 있으니 공개 자료만** |
| **채팅에 첨부** | 사진·스크린샷 | 그대로 첨부 |

## 3. 계정이 필요한 자료 (NASA Earthdata 등)
- **비밀번호나 토큰은 채팅에 쓰지 마세요.** 대화 기록에 남습니다.
- **해커톤 전에 이 컴퓨터에서 직접 넣어 두세요:**
  1. https://urs.earthdata.nasa.gov 에서 토큰을 만듭니다.
  2. `~/.bashrc`에 `export EARTHDATA_TOKEN=...`을 추가합니다.
  3. 그러면 `fetch`가 Earthdata 주소에 자동으로 붙여 씁니다.
- **원격으로만 넣어야 한다면:** 프롬프트에 `!`로 시작하는 명령(예: `! nano ~/.bashrc`)을 쓰면 직접 실행되지만, 출력이 대화에 남을 수 있습니다.

## 4. 받은 뒤
> "받은 자료로 학습·보정 돌리고 보고서 보여줘"

```bash
.venv/bin/python -m hackathon.run_all --drop ../data/hackathon_2026 --name hackathon_2026
```

- **결과:** `outputs/hackathon/hackathon_2026/report.md`. Claude가 요약하고 그림은 파일로 보냅니다.
- **새 지형(DEM)이 있으면:** `sites.py`에 항목을 더하고 `python build_site_data.py <id> && python build_demo_html.py`를 실행하면 데모에 지형이 추가됩니다. 같은 지형으로 SLAM 시뮬레이션도 `python slam_site_exploration.py <id>`로 돌릴 수 있습니다.

## 5. 결과를 원격에서 받기
- **파일:** "보고서랑 그림 보내줘". Claude가 파일을 직접 보내고, 휴대폰에서 받을 수 있습니다(HTML, PNG, mp4, zip).
- **데모 링크:** 공유 페이지(claude.ai 아티팩트)를 갱신합니다. 팀원에게는 페이지의 Share 메뉴로 공유하세요.
- **코드와 결과:** "GitHub에 올려줘". 배포 키로 `jstak0804/martian-map-slam`에 push합니다.

## 6. 오래 걸리는 작업
- **백그라운드 실행:** 대용량 다운로드나 학습은 Claude가 백그라운드로 돌리고, 끝나면 알림을 받아 이어서 진행합니다. 채팅을 닫아도 이 컴퓨터가 켜져 있으면 계속 돕니다.
- **컴퓨터 상태:** 이 컴퓨터(WSL)가 잠자기에 들어가면 멈춥니다. 해커톤 동안에는 절전 모드를 꺼 두세요.
