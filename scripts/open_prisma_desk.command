#!/bin/zsh

URL="${PRISMA_DESK_URL:-http://127.0.0.1:5050/}"

open -a "Safari" "$URL" || open "$URL"
