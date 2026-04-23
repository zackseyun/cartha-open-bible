#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
CONCURRENCY="${PHASE10_CONCURRENCY:-10}"

mkdir -p /tmp/cob-pilot/sirach_24 /tmp/cob-pilot/prayer_of_manasseh

cd "$ROOT"

"$PYTHON" tools/phase10_stacked_pilot.py \
  --book sirach \
  --chapter 24 \
  --concurrency "$CONCURRENCY" \
  --out /tmp/cob-pilot/sirach_24

"$PYTHON" tools/phase10_stacked_pilot.py \
  --book prayer_of_manasseh \
  --chapter 1 \
  --concurrency "$CONCURRENCY" \
  --out /tmp/cob-pilot/prayer_of_manasseh

"$PYTHON" tools/phase10_generate_comparison.py \
  --pilot /tmp/cob-pilot/sirach_24 \
  --baseline v31 \
  --out /tmp/cob-pilot/sirach_24_comparison.md

"$PYTHON" tools/phase10_generate_comparison.py \
  --pilot /tmp/cob-pilot/prayer_of_manasseh \
  --baseline v3_author_intent \
  --out /tmp/cob-pilot/prayer_of_manasseh_comparison.md

printf '\nPhase 10 pilot outputs:\n'
printf '  - concurrency=%s\n' "$CONCURRENCY"
printf '  - /tmp/cob-pilot/sirach_24\n'
printf '  - /tmp/cob-pilot/prayer_of_manasseh\n'
printf '  - /tmp/cob-pilot/sirach_24_comparison.md\n'
printf '  - /tmp/cob-pilot/prayer_of_manasseh_comparison.md\n'
