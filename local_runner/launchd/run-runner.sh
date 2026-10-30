#!/bin/sh
# launchd가 러너를 띄울 때 쓰는 래퍼. 환경 파일·실행 도구가 없으면 종료 코드 0으로
# 조용히 끝나, KeepAlive(SuccessfulExit=false)가 크래시 루프를 만들지 않게 한다.
set -eu

ENV_FILE="$HOME/.takulife-runner.env"
# 저장소 위치는 이 스크립트 위치(local_runner/launchd/) 기준으로 계산한다.
REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

if [ ! -f "$ENV_FILE" ]; then
  echo "러너 환경 파일이 없어 시작하지 않는다: $ENV_FILE"
  exit 0
fi
# 토큰이 들어 있으므로 소유자만 읽고 쓰는 600이 아니면 시작하지 않는다.
# BSD(macOS) stat이 실패하면 GNU stat으로 — 계약 테스트가 Linux CI에서도 돌게 한다.
if [ "$(stat -f %Lp "$ENV_FILE" 2>/dev/null || stat -c %a "$ENV_FILE")" != "600" ]; then
  echo "러너 환경 파일 권한이 600이 아니어서 시작하지 않는다: $ENV_FILE"
  exit 0
fi

set -a
. "$ENV_FILE"
set +a

# launchd는 셸 프로필을 읽지 않으므로 claude·uv가 있는 경로를 직접 지정한다.
# env 파일의 TAKULIFE_RUNNER_PATH_PREPEND(예: nvm으로 설치한 claude의 bin 경로)를 맨 앞에 붙인다.
PATH="${TAKULIFE_RUNNER_PATH_PREPEND:+${TAKULIFE_RUNNER_PATH_PREPEND}:}$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

if ! command -v claude >/dev/null 2>&1; then
  echo "claude 실행 파일을 PATH에서 찾지 못해 시작하지 않는다"
  exit 0
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv 실행 파일을 PATH에서 찾지 못해 시작하지 않는다"
  exit 0
fi

cd "$REPO_DIR"
exec uv run --frozen python -m local_runner.runner
