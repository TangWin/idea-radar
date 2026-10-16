#!/usr/bin/env bash
# Rebuild Idea Radar from /workspace/idea-mining-* and push to GitHub Pages.
set -euo pipefail
cd "$(dirname "$0")"
python3 build.py
git add -A
if git diff --cached --quiet; then echo "No changes; nothing to publish."; exit 0; fi
git commit -q -m "Update digests $(date +%F)"
git push -q origin main
echo "Published: https://tangwin.github.io/idea-radar/"
