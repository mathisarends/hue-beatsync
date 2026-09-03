#!/usr/bin/env sh
# Runs the hue-beatsync server natively on this machine.
#
# Audio capture needs the host's sound stack, which a Linux container cannot
# reach - see server/README.md. Works from Git Bash, WSL and Linux;
# scripts/serve.ps1 is the PowerShell equivalent.
set -eu

port=8765
bind_host=127.0.0.1
reload=

usage() {
    cat <<'USAGE'
Usage: scripts/serve.sh [-p PORT] [-b HOST] [-r]

  -p, --port PORT   port to listen on (default 8765)
  -b, --bind HOST   address to bind (default 127.0.0.1)
  -r, --reload      restart on source changes
USAGE
}

while [ $# -gt 0 ]; do
    case "$1" in
        -p | --port) port=$2; shift 2 ;;
        -b | --bind) bind_host=$2; shift 2 ;;
        -r | --reload) reload=--reload; shift ;;
        --help) usage; exit 0 ;;
        *) echo "serve.sh: unknown argument '$1'" >&2; usage >&2; exit 2 ;;
    esac
done

if ! command -v uv > /dev/null 2>&1; then
    echo "serve.sh: uv is not on PATH. See https://docs.astral.sh/uv/" >&2
    exit 1
fi

cd "$(dirname "$0")/.."

# A checkout on /mnt/c is shared with Windows, where .venv holds Windows
# binaries. Syncing from WSL would overwrite it (and vice versa), so the two
# get separate environments.
if [ -r /proc/version ] && grep -qi microsoft /proc/version; then
    UV_PROJECT_ENVIRONMENT=${UV_PROJECT_ENVIRONMENT:-.venv-wsl}
    export UV_PROJECT_ENVIRONMENT
fi

# --inexact: the workspace shares one .venv, and a plain sync would
# prune everything outside this package - the dev tools included.
uv sync --frozen --inexact --package hue-beatsync-server

echo "hue-beatsync server on http://$bind_host:$port (docs at /docs)"
exec uv run --package hue-beatsync-server \
    uvicorn server.main:app --host "$bind_host" --port "$port" $reload
