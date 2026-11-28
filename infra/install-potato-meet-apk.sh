#!/usr/bin/env bash
# Atomically install a Potato Meet release APK into the shared releases dir.
# Invoked over SSH from .github/workflows/potato-meet-release.yml.
# Does not touch Docker, FastAPI, DB, Qwen, Caddy, or assetlinks.json.
set -euo pipefail

RELEASES_DIR="${RELEASES_DIR:-/home/linuxuser/conditional-ok-releases}"
DEST="${RELEASES_DIR}/app-release.apk"
INCOMING="${1:?usage: install-potato-meet-apk.sh /path/to/incoming.apk}"
EXPECTED_SHA256="${2:?usage: install-potato-meet-apk.sh <apk> <sha256hex>}"
LOCK_FILE="${RELEASES_DIR}/.potato-meet-apk.lock"

umask 022
mkdir -p "$RELEASES_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Another Potato Meet APK install is in progress; refusing." >&2
  exit 1
fi

if [[ ! -f "$INCOMING" ]]; then
  echo "Incoming APK missing: $INCOMING" >&2
  exit 1
fi

SIZE="$(wc -c <"$INCOMING" | tr -d ' ')"
if [[ "$SIZE" -lt 1000000 ]]; then
  echo "Incoming APK too small (${SIZE} bytes); refusing." >&2
  exit 1
fi

ACTUAL_SHA="$(sha256sum "$INCOMING" | awk '{print $1}')"
if [[ "$ACTUAL_SHA" != "$EXPECTED_SHA256" ]]; then
  echo "SHA-256 mismatch for incoming APK." >&2
  echo "expected=$EXPECTED_SHA256" >&2
  echo "actual=$ACTUAL_SHA" >&2
  exit 1
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP=""
if [[ -f "$DEST" ]]; then
  BACKUP="${DEST}.bak.${STAMP}"
  cp -a "$DEST" "$BACKUP"
fi

STAGE="${DEST}.new.${STAMP}"
cp -a "$INCOMING" "$STAGE"
chmod 644 "$STAGE"
mv -f "$STAGE" "$DEST"
chmod 644 "$DEST"

# Confirm installed file matches the signed artifact.
INSTALLED_SHA="$(sha256sum "$DEST" | awk '{print $1}')"
if [[ "$INSTALLED_SHA" != "$EXPECTED_SHA256" ]]; then
  echo "Post-replace SHA-256 mismatch; attempting restore." >&2
  if [[ -n "$BACKUP" && -f "$BACKUP" ]]; then
    mv -f "$BACKUP" "$DEST"
  fi
  exit 1
fi

echo "Installed Potato Meet APK -> ${DEST} (${SIZE} bytes)"
if [[ -n "$BACKUP" ]]; then
  echo "Previous APK backed up at ${BACKUP}"
fi
