#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/se.prismasuecia.prismadesk.plist"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/data"

chmod +x "$PROJECT_DIR/scripts/start_prisma_desk.sh"
chmod +x "$PROJECT_DIR/scripts/open_prisma_desk.command"

sed "s#__PROJECT_DIR__#$PROJECT_DIR#g" "$PROJECT_DIR/launchd/se.prismasuecia.prismadesk.plist.template" > "$PLIST"

launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

echo "Prisma Desk autostart installerad."
echo "Server: http://127.0.0.1:5050/"
echo "Logg: $PROJECT_DIR/logs/prisma-desk.out.log"
echo "Fel:  $PROJECT_DIR/logs/prisma-desk.err.log"
