#!/usr/bin/env bash
# Sync .agents/skills/security-audit with github.com/cloudflare/security-audit-skill.
# Review the result with `git diff .agents/skills/security-audit` before committing.
set -euo pipefail

REPO=https://github.com/cloudflare/security-audit-skill
DEST="$(cd "$(dirname "$0")" && pwd)/skills/security-audit"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone --quiet --depth 1 "$REPO" "$TMP/src"
NEW="$(git -C "$TMP/src" rev-parse HEAD)"
OLD="$(cat "$DEST/.upstream-sha" 2>/dev/null || echo none)"

if [ "$NEW" = "$OLD" ]; then
  echo "security-audit already at $NEW"
  exit 0
fi

rm -rf "$DEST"
cp -R "$TMP/src/skills/security-audit" "$DEST"
echo "$NEW" > "$DEST/.upstream-sha"
echo "security-audit updated $OLD -> $NEW"
echo "Changes: $REPO/compare/$OLD...$NEW"
