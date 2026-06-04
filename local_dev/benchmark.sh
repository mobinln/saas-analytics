#!/usr/bin/env bash
set -euo pipefail

URL="${URL:-http://localhost:8080/event}"
THREADS="${THREADS:-4}"
CONNECTIONS="${CONNECTIONS:-1000}"
DURATION="${DURATION:-30s}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LUA="${SCRIPT_DIR}/post.lua"

if ! command -v wrk >/dev/null 2>&1; then
    echo "error: wrk is not installed" >&2
    exit 1
fi

if [[ ! -f "$LUA" ]]; then
    echo "error: post.lua not found at $LUA" >&2
    exit 1
fi

echo "benchmarking $URL"
echo "threads=$THREADS connections=$CONNECTIONS duration=$DURATION"
echo

exec wrk -t"$THREADS" -c"$CONNECTIONS" -d"$DURATION" --latency -s "$LUA" "$URL"
