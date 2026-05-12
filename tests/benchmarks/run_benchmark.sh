#!/bin/bash
# cli-hub A/B Benchmark — with vs without cli-hub
# Model: DeepSeek V4 Pro (via cc-proxy on localhost:8088)
# Usage: bash run_benchmark.sh

set -e
export ANTHROPIC_BASE_URL="http://localhost:8088"
export ANTHROPIC_API_KEY="not-needed"
MODEL="deepseek-v4-pro"
TIMEOUT=120

BENCHMARK_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$BENCHMARK_DIR/results"
mkdir -p "$RESULTS"

echo "=========================================="
echo "  cli-hub A/B Benchmark — V4 Pro"
echo "=========================================="
echo ""

# ── test cases ──────────────────────────────────────────────────
tests=(
  "U1_mmx_image:用mmx生成一张猫的图片，告诉我用什么命令"
  "U2_mmx_search:用mmx搜索deepseek api pricing相关信息"
  "U3_mmx_quota:查看mmx的API额度还剩多少"
  "U4_mmx_text:用mmx生成一段关于AI agent的简短介绍"
  "U5_mmx_speech:用mmx列出可用的语音合成声音"
  "U6_opencli_list:用opencli列出所有可用的网站适配器"
  "U7_opencli_browse:用opencli在浏览器里打开github.com"
  "U8_opencli_site:用opencli抓取bilibili热门视频"
)

# ── helper ──────────────────────────────────────────────────────
run_tests() {
  local ROUND="$1"
  local OUT="$RESULTS/$ROUND"
  mkdir -p "$OUT"

  cd /tmp
  echo "=== Round: $ROUND ==="
  for test in "${tests[@]}"; do
    local id="${test%%:*}"
    local prompt="${test#*:}"
    echo -n "  $id ... "
    timeout "$TIMEOUT" claude -p "$prompt" --model "$MODEL" > "$OUT/${id}.txt" 2>&1 || true
    echo "$(wc -c < "$OUT/${id}.txt") bytes"
  done
  echo "  Done ($(ls "$OUT" | wc -l) files)"
  echo ""
}

# ── ROUND 1: WITH cli-hub ───────────────────────────────────────
echo ">>> Installing cli-hub (OpenClaw + Claude)"
mkdir -p ~/.agents/skills/cli-hub ~/.claude/skills/cli-hub
rm -rf ~/.openclaw/cli-registry ~/.claude/cli-registry
mkdir -p ~/.openclaw/cli-registry ~/.claude/cli-registry

cp "$BENCHMARK_DIR/../../SKILL.md" ~/.agents/skills/cli-hub/
cp "$BENCHMARK_DIR/../../SKILL.md" ~/.claude/skills/cli-hub/
cp -r "$BENCHMARK_DIR/../../scripts" ~/.agents/skills/cli-hub/
cp -r "$BENCHMARK_DIR/../../scripts" ~/.claude/skills/cli-hub/
cp -r "$BENCHMARK_DIR/../../references" ~/.agents/skills/cli-hub/ 2>/dev/null || true
cp -r "$BENCHMARK_DIR/../../references" ~/.claude/skills/cli-hub/ 2>/dev/null || true

echo ">>> Running discover"
cd ~/.agents/skills/cli-hub
python3 scripts/cli-registry.py discover 2>&1 | tail -3
echo "  Registry: $(ls ~/.openclaw/cli-registry/*.json 2>/dev/null | wc -l) tools"
cp ~/.openclaw/cli-registry/*.json ~/.claude/cli-registry/ 2>/dev/null || true
cp ~/.openclaw/cli-registry/.keywords.json ~/.claude/cli-registry/ 2>/dev/null || true
echo "  Claude: $(ls ~/.claude/cli-registry/*.json 2>/dev/null | wc -l) tools"

echo ""
echo ">>> Round 1: WITH cli-hub"
run_tests "with-clihub"

# ── ROUND 2: WITHOUT cli-hub ────────────────────────────────────
echo ">>> Removing cli-hub"
rm -rf ~/.agents/skills/cli-hub ~/.openclaw/cli-registry
rm -rf ~/.claude/skills/cli-hub ~/.claude/cli-registry
mkdir -p ~/.claude/skills
echo "  Registry: $(ls ~/.openclaw/cli-registry/*.json 2>/dev/null | wc -l) tools"

echo ""
echo ">>> Round 2: WITHOUT cli-hub"
run_tests "without-clihub"

# ── SUMMARY ─────────────────────────────────────────────────────
echo "=========================================="
echo "  Results saved to: $RESULTS"
echo "=========================================="
echo ""
echo "File sizes:"
printf "%-25s %10s %10s\n" "Test" "WITH" "WITHOUT"
echo "-----------------------------------------------"
for test in "${tests[@]}"; do
  id="${test%%:*}"
  w="$RESULTS/with-clihub/${id}.txt"
  o="$RESULTS/without-clihub/${id}.txt"
  ws=$(wc -c < "$w" 2>/dev/null || echo 0)
  os=$(wc -c < "$o" 2>/dev/null || echo 0)
  printf "%-25s %10d %10d\n" "$id" "$ws" "$os"
done
echo ""
echo "Done."
