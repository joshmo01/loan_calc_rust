#!/usr/bin/env bash
cd "$(dirname "$0")"
./start-chat.sh
echo ""
echo "Server stopped. Press Enter to close."
read -r _
