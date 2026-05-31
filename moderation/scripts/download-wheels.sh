#!/usr/bin/env sh
# Скачивает Linux-колёса на хосте (обход SSL/таймаутов PyPI внутри docker build).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WHEELS="$ROOT/docker/wheels"
mkdir -p "$WHEELS"
rm -f "$WHEELS"/*.whl "$WHEELS"/*.tar.gz

echo "Downloading wheels for Linux (Python 3.11) into $WHEELS ..."
python -m pip download \
  -r "$ROOT/requirements.txt" \
  -d "$WHEELS" \
  --platform manylinux2014_x86_64 \
  --python-version 3.11 \
  --implementation cp \
  --abi cp311 \
  --only-binary :all: \
  ${PIP_INDEX_URL:+-i "$PIP_INDEX_URL"}

if ! ls "$WHEELS"/*.whl >/dev/null 2>&1; then
  echo "No .whl files downloaded. Check internet/VPN or set PIP_INDEX_URL." >&2
  exit 1
fi
echo "Done. Rebuild: docker compose build moderation"
