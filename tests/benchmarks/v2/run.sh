#!/bin/bash
# ════════════════════════════════════════════════════════════════
#  cli-hub Comprehensive A/B Benchmark — V2
#  Model: DeepSeek V4 Pro (via proxy on localhost:8088)
# ════════════════════════════════════════════════════════════════
set -euo pipefail

export ANTHROPIC_BASE_URL="http://localhost:8088"
export ANTHROPIC_API_KEY="not-needed"
MODEL="deepseek-v4-pro"
TIMEOUT=120

BENCHMARK_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$BENCHMARK_DIR/results"
PROJECT_DIR="$(cd "$BENCHMARK_DIR/../../.." && pwd)"
CLI_HUB_SRC="$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
info() { echo "ℹ️  $1"; }

# ── Test Cases ─────────────────────────────────────────────────
declare -A TEST_PROMPTS
TEST_NAMES=(
  "A1_mmx_image"
  "A2_mmx_search"
  "A3_mmx_quota"
  "A4_mmx_text"
  "A5_mmx_speech"
  "A6_opencli_list"
  "A7_opencli_browse"
  "A8_opencli_bilibili"
)

TEST_PROMPTS["A1_mmx_image"]="用 mmx 生成一张猫的图片，告诉我用什么命令"
TEST_PROMPTS["A2_mmx_search"]="用 mmx 搜索 deepseek api pricing 相关信息"
TEST_PROMPTS["A3_mmx_quota"]="查看 mmx 的 API 额度还剩多少"
TEST_PROMPTS["A4_mmx_text"]="用 mmx 生成一段关于 AI agent 的简短介绍"
TEST_PROMPTS["A5_mmx_speech"]="用 mmx 列出可用的语音合成声音"
TEST_PROMPTS["A6_opencli_list"]="用 opencli 列出所有可用的网站适配器"
TEST_PROMPTS["A7_opencli_browse"]="用 opencli 在浏览器里打开 github.com"
TEST_PROMPTS["A8_opencli_bilibili"]="用 opencli 抓取 bilibili 热门视频"

# ── Helpers ─────────────────────────────────────────────────────
run_single_test() {
  local test_id="$1"
  local prompt="$2"
  local out_dir="$3"
  local out_file="$out_dir/${test_id}.txt"

  echo -n "    ${test_id} ... "
  cd /tmp
  timeout "$TIMEOUT" claude -p "$prompt" --model "$MODEL" > "$out_file" 2>&1 || true
  local sz
  sz=$(wc -c < "$out_file" 2>/dev/null || echo 0)
  echo "${sz} bytes"
}

run_test_batch() {
  local round="$1"
  local out_dir="$RESULTS/$round"
  mkdir -p "$out_dir"

  echo ""
  echo "──────────────────────────────────────────"
  echo "  Round: $round"
  echo "──────────────────────────────────────────"
  for tid in "${TEST_NAMES[@]}"; do
    run_single_test "$tid" "${TEST_PROMPTS[$tid]}" "$out_dir"
  done
  echo "  Done — $(ls "$out_dir" | wc -l) files"
}

# ════════════════════════════════════════════════════════════════
#  GATE 0: Pre-flight Checks
# ════════════════════════════════════════════════════════════════
echo "╔══════════════════════════════════════════╗"
echo "║  cli-hub Benchmark V2 — Pre-flight      ║"
echo "╚══════════════════════════════════════════╝"
echo ""

info "Checking proxy at $ANTHROPIC_BASE_URL ..."
PROXY_RESP=$(curl -s -X POST "$ANTHROPIC_BASE_URL/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{"model":"'"$MODEL"'","messages":[{"role":"user","content":"say hi"}],"max_tokens":5}' 2>&1)
if echo "$PROXY_RESP" | grep -q '"type":"message"'; then
  pass "Proxy is alive — JSON response received"
else
  fail "Proxy check failed! Response: $PROXY_RESP"
fi

info "Checking claude binary ..."
if which claude >/dev/null 2>&1; then
  CLAUDE_VER=$(claude --version 2>/dev/null || echo "unknown")
  pass "Claude found: $CLAUDE_VER"
else
  fail "claude not found in PATH"
fi

info "Checking cli-hub source at $CLI_HUB_SRC ..."
if [ -f "$CLI_HUB_SRC/SKILL.md" ] && [ -f "$CLI_HUB_SRC/scripts/cli-registry.py" ]; then
  pass "cli-hub source OK"
else
  fail "cli-hub source missing SKILL.md or scripts/cli-registry.py"
fi

# ════════════════════════════════════════════════════════════════
#  PHASE 1: Install + Register
# ════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Phase 1: Install + Register            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. Fresh install — remove existing, copy from project
info "Removing existing cli-hub installations ..."
rm -rf ~/.agents/skills/cli-hub
rm -rf ~/.claude/skills/cli-hub
rm -rf ~/.openclaw/cli-registry
rm -rf ~/.claude/cli-registry
pass "Old installations removed"

info "Installing cli-hub from project to ~/.agents/skills/ ..."
mkdir -p ~/.agents/skills/cli-hub
cp "$CLI_HUB_SRC/SKILL.md" ~/.agents/skills/cli-hub/
cp -r "$CLI_HUB_SRC/scripts" ~/.agents/skills/cli-hub/
cp -r "$CLI_HUB_SRC/references" ~/.agents/skills/cli-hub/ 2>/dev/null || true
pass "Installed to ~/.agents/skills/cli-hub"

info "Installing cli-hub from project to ~/.claude/skills/ ..."
mkdir -p ~/.claude/skills/cli-hub
cp "$CLI_HUB_SRC/SKILL.md" ~/.claude/skills/cli-hub/
cp -r "$CLI_HUB_SRC/scripts" ~/.claude/skills/cli-hub/
cp -r "$CLI_HUB_SRC/references" ~/.claude/skills/cli-hub/ 2>/dev/null || true
pass "Installed to ~/.claude/skills/cli-hub"

# 2. Run discover (known binaries only, no PATH scan to avoid hangs)
info "Running discover ..."
mkdir -p ~/.openclaw/cli-registry
cd ~/.agents/skills/cli-hub
python3 scripts/cli-registry.py discover 2>&1
echo ""

# 2b. Register kimi manually (not in known list, --scan hangs on other binaries)
info "Registering kimi manually ..."
python3 scripts/cli-registry.py register kimi --desc "Kimi AI CLI" 2>&1 || true
echo ""
REG_COUNT=$(ls ~/.openclaw/cli-registry/*.json 2>/dev/null | grep -v keywords | wc -l)
info "Registry now has $REG_COUNT tools"

# ── GATE 1a: VERIFY lookups ─────────────────────────────────────
echo ""
info "── Verification: Lookup mmx ──"
MMX_LOOKUP=$(python3 scripts/cli-registry.py lookup mmx 2>&1)
if echo "$MMX_LOOKUP" | grep -q "MiniMax multimodal AI toolkit"; then
  pass "mmx → 'MiniMax multimodal AI toolkit'"
else
  fail "mmx lookup failed! Got: $(echo "$MMX_LOOKUP" | head -3)"
fi

info "── Verification: Lookup opencli ──"
OPENCLI_LOOKUP=$(python3 scripts/cli-registry.py lookup opencli 2>&1)
if echo "$OPENCLI_LOOKUP" | grep -q "OpenClaw CLI"; then
  pass "opencli → 'OpenClaw CLI'"
else
  fail "opencli lookup failed! Got: $(echo "$OPENCLI_LOOKUP" | head -3)"
fi

info "── Verification: Lookup kimi ──"
# kimi was registered manually above; verify it
KIMI_LOOKUP=$(python3 scripts/cli-registry.py lookup kimi 2>&1 || true)
if echo "$KIMI_LOOKUP" | grep -q "Kimi AI CLI"; then
  pass "kimi → 'Kimi AI CLI'"
else
  fail "kimi lookup failed! Got: $(echo "$KIMI_LOOKUP" | head -3)"
fi

# 6. Sync registry to Claude path
info "Syncing registry to Claude path ..."
mkdir -p ~/.claude/cli-registry
cp ~/.openclaw/cli-registry/*.json ~/.claude/cli-registry/ 2>/dev/null || true
CLAUDE_REG_COUNT=$(ls ~/.claude/cli-registry/*.json 2>/dev/null | grep -v keywords | wc -l)
info "Claude registry: $CLAUDE_REG_COUNT tools"

pass "Phase 1 OK — $REG_COUNT tools registered"

# ════════════════════════════════════════════════════════════════
#  PHASE 2: WITH cli-hub Tests
# ════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Phase 2: WITH cli-hub Tests            ║"
echo "╚══════════════════════════════════════════╝"

run_test_batch "with-clihub"

# ── GATE 2: Verify outputs ──────────────────────────────────────
echo ""
info "── Verification: WITH cli-hub outputs ──"
WITH_COUNT=$(ls "$RESULTS/with-clihub/"*.txt 2>/dev/null | wc -l)
if [ "$WITH_COUNT" -eq 8 ]; then
  pass "with-clihub has exactly 8 output files"
else
  fail "with-clihub has $WITH_COUNT files (expected 8)"
fi

MIN_SIZE=15
SMALL_FILES=0
for f in "$RESULTS/with-clihub/"*.txt; do
  sz=$(wc -c < "$f" 2>/dev/null || echo 0)
  if [ "$sz" -lt "$MIN_SIZE" ]; then
    warn "Small file: $(basename $f) = ${sz} bytes"
    SMALL_FILES=$((SMALL_FILES + 1))
  fi
done
if [ "$SMALL_FILES" -eq 0 ]; then
  pass "All with-clihub files > ${MIN_SIZE} bytes"
else
  warn "$SMALL_FILES files < ${MIN_SIZE} bytes in with-clihub"
fi

# ════════════════════════════════════════════════════════════════
#  PHASE 3: Remove cli-hub
# ════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Phase 3: Remove cli-hub                ║"
echo "╚══════════════════════════════════════════╝"
echo ""

info "Removing all cli-hub and registry files ..."
rm -rf ~/.agents/skills/cli-hub
rm -rf ~/.claude/skills/cli-hub
rm -rf ~/.openclaw/cli-registry
rm -rf ~/.claude/cli-registry
mkdir -p ~/.claude/skills

# ── GATE 3: Verify removal ──────────────────────────────────────
info "── Verification: cli-hub removed ──"

if ls ~/.claude/skills/cli-hub 2>/dev/null; then
  fail "~/.claude/skills/cli-hub STILL EXISTS!"
else
  pass "~/.claude/skills/cli-hub → not found (removed)"
fi

if ls ~/.claude/cli-registry 2>/dev/null; then
  fail "~/.claude/cli-registry STILL EXISTS!"
else
  pass "~/.claude/cli-registry → not found (removed)"
fi

pass "Phase 3 OK — cli-hub fully removed"

# ════════════════════════════════════════════════════════════════
#  PHASE 4: WITHOUT cli-hub Tests
# ════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Phase 4: WITHOUT cli-hub Tests         ║"
echo "╚══════════════════════════════════════════╝"

run_test_batch "without-clihub"

# ── GATE 4: Verify outputs ──────────────────────────────────────
echo ""
info "── Verification: WITHOUT cli-hub outputs ──"
WITHOUT_COUNT=$(ls "$RESULTS/without-clihub/"*.txt 2>/dev/null | wc -l)
if [ "$WITHOUT_COUNT" -eq 8 ]; then
  pass "without-clihub has exactly 8 output files"
else
  fail "without-clihub has $WITHOUT_COUNT files (expected 8)"
fi

SMALL_FILES=0
for f in "$RESULTS/without-clihub/"*.txt; do
  sz=$(wc -c < "$f" 2>/dev/null || echo 0)
  if [ "$sz" -lt "$MIN_SIZE" ]; then
    warn "Small file: $(basename $f) = ${sz} bytes"
    SMALL_FILES=$((SMALL_FILES + 1))
  fi
done
if [ "$SMALL_FILES" -eq 0 ]; then
  pass "All without-clihub files > ${MIN_SIZE} bytes"
else
  warn "$SMALL_FILES files < ${MIN_SIZE} bytes in without-clihub"
fi

# ════════════════════════════════════════════════════════════════
#  PHASE 5: Compare & Generate SUMMARY.md
# ════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Phase 5: Generate Comparison Report    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

SUMMARY="$BENCHMARK_DIR/SUMMARY.md"

cat > "$SUMMARY" << 'HEADER'
# cli-hub A/B Benchmark — V2 Summary

**Model:** DeepSeek V4 Pro  
**Date:** __DATE__
**Timeout:** 120s per test  
**Tests:** 8 prompts × 2 conditions (with/without cli-hub)

---

## 📊 Comparison Table

| # | Test | Prompt | WITH (bytes) | WITHOUT (bytes) | Δ | With Tool ID? | Without Tool ID? | Hallucinations (with) | Hallucinations (wo) |
|---|------|--------|-------------|----------------|---|---|---|---|---|---|
HEADER

# Replace date placeholder
SUMMARY_DATE=$(date '+%Y-%m-%d %H:%M:%S')
sed -i "s/__DATE__/$SUMMARY_DATE/" "$SUMMARY"

# Analyze each test pair
for tid in "${TEST_NAMES[@]}"; do
  PROMPT_SHORT="${TEST_PROMPTS[$tid]}"
  PROMPT_SHORT="${PROMPT_SHORT:0:45}..."
  
  WITH_FILE="$RESULTS/with-clihub/${tid}.txt"
  WITHOUT_FILE="$RESULTS/without-clihub/${tid}.txt"
  
  WSZ=$(wc -c < "$WITH_FILE" 2>/dev/null || echo 0)
  OSZ=$(wc -c < "$WITHOUT_FILE" 2>/dev/null || echo 0)
  
  # Calculate delta percentage
  if [ "$OSZ" -gt 0 ]; then
    DELTA_PCT=$(( (WSZ - OSZ) * 100 / OSZ ))
  else
    DELTA_PCT="N/A"
  fi
  
  # Detect tool identification: search for keywords in output
  WITH_TOOL="❌"
  WITHOUT_TOOL="❌"
  
  # Check with-clihub for tool identification
  if [ -f "$WITH_FILE" ]; then
    WITH_TEXT=$(cat "$WITH_FILE" 2>/dev/null || echo "")
    # Look for command suggestions, tool references
    if echo "$WITH_TEXT" | grep -qiE "(mmx|opencli|kimi)\s+(image|search|quota|text|speech|adapter|list|plugin|browser|open|fetch|抓取|生成|搜索)"; then
      WITH_TOOL="✅"
    fi
  fi
  
  # Check without-clihub for tool identification
  if [ -f "$WITHOUT_FILE" ]; then
    WITHOUT_TEXT=$(cat "$WITHOUT_FILE" 2>/dev/null || echo "")
    if echo "$WITHOUT_TEXT" | grep -qiE "(mmx|opencli|kimi)\s+(image|search|quota|text|speech|adapter|list|plugin|browser|open|fetch|抓取|生成|搜索)"; then
      WITHOUT_TOOL="✅"
    fi
  fi
  
  # Count hallucination indicators (wrong flags, non-existent subcommands, made-up tools)
  WITH_HALLUC=0
  WITHOUT_HALLUC=0
  
  if [ -f "$WITH_FILE" ]; then
    WITH_HALLUC=$(grep -ciE "(no such|not found|cannot find|unknown command|invalid|does not exist|unrecognized|no command|error:)" "$WITH_FILE" 2>/dev/null || true)
    WITH_HALLUC=$(echo "$WITH_HALLUC" | tr -d '\n\r' | grep -oE '[0-9]+' || echo 0)
    [ -z "$WITH_HALLUC" ] && WITH_HALLUC=0
  fi
  if [ -f "$WITHOUT_FILE" ]; then
    WITHOUT_HALLUC=$(grep -ciE "(no such|not found|cannot find|unknown command|invalid|does not exist|unrecognized|no command|error:)" "$WITHOUT_FILE" 2>/dev/null || true)
    WITHOUT_HALLUC=$(echo "$WITHOUT_HALLUC" | tr -d '\n\r' | grep -oE '[0-9]+' || echo 0)
    [ -z "$WITHOUT_HALLUC" ] && WITHOUT_HALLUC=0
  fi
  
  # Detect "used cli-hub" in with-clihub
  CLI_HUB_USED="❌"
  if [ -f "$WITH_FILE" ]; then
    if grep -qiE "(cli-hub|cli.hub|registry|lookup|discover)" "$WITH_FILE" 2>/dev/null; then
      CLI_HUB_USED="✅"
    fi
  fi
  
  printf "| %s | %s | %s | %s | %s | %+d%%%% | %s / %s | %s | %d | %d |\n" \
    "${tid:0:1}" "${tid/_/ }" "$PROMPT_SHORT" "$WSZ" "$OSZ" "$DELTA_PCT" \
    "$WITH_TOOL" "$CLI_HUB_USED" "$WITHOUT_TOOL" "$WITH_HALLUC" "$WITHOUT_HALLUC" \
    >> "$SUMMARY"
done

cat >> "$SUMMARY" << 'FOOTER'

---

## 🔑 Legend

- **Tool ID:** Whether the model correctly identified and suggested the tool command
- **cli-hub used:** Whether the model referenced cli-hub, registry, or lookup (with-clihub only)
- **Hallucinations:** Count of hallucination indicators (wrong commands, non-existent flags, etc.)
- **Δ:** Size difference as percentage of without-clihub file size
  - Positive: with-clihub output is larger (more thorough answers)
  - Negative: with-clihub output is smaller (more concise)

## 📈 Scorecard

### Average File Size
| Condition | Avg Bytes |
|-----------|----------|
| With cli-hub | __WITH_AVG__ |
| Without cli-hub | __WITHOUT_AVG__ |

### Tool Identification Rate
| Condition | Correct | Total | Rate |
|-----------|---------|-------|------|
| With cli-hub | __WITH_TOOL_COUNT__ | 8 | __WITH_TOOL_RATE__% |
| Without cli-hub | __WITHOUT_TOOL_COUNT__ | 8 | __WITHOUT_TOOL_RATE__% |

### Hallucination Summary
| Condition | Total Hallucinations |
|-----------|---------------------|
| With cli-hub | __WITH_HALLUC_TOTAL__ |
| Without cli-hub | __WITHOUT_HALLUC_TOTAL__ |

### cli-hub Usage
| Metric | Count |
|--------|-------|
| Tests where cli-hub was referenced | __CLIHUB_USED__ / 8 |

---

## 🏆 Final Verdict

__VERDICT__

*Generated by run.sh v2 on __DATE__*
FOOTER

# Compute averages
WITH_TOTAL=0
WITHOUT_TOTAL=0
WITH_TOOL_COUNT=0
WITHOUT_TOOL_COUNT=0
WITH_HALLUC_TOTAL=0
WITHOUT_HALLUC_TOTAL=0
CLIHUB_USED=0

for tid in "${TEST_NAMES[@]}"; do
  WITH_FILE="$RESULTS/with-clihub/${tid}.txt"
  WITHOUT_FILE="$RESULTS/without-clihub/${tid}.txt"
  
  WSZ=$(wc -c < "$WITH_FILE" 2>/dev/null || echo 0)
  OSZ=$(wc -c < "$WITHOUT_FILE" 2>/dev/null || echo 0)
  WITH_TOTAL=$((WITH_TOTAL + WSZ))
  WITHOUT_TOTAL=$((WITHOUT_TOTAL + OSZ))
  
  # Re-check tool identification
  if [ -f "$WITH_FILE" ]; then
    WITH_TEXT=$(cat "$WITH_FILE" 2>/dev/null || echo "")
    if echo "$WITH_TEXT" | grep -qiE "(mmx|opencli|kimi)\s+(image|search|quota|text|speech|adapter|list|plugin|browser|open|fetch|抓取|生成|搜索)"; then
      WITH_TOOL_COUNT=$((WITH_TOOL_COUNT + 1))
    fi
    WHC=$(grep -ciE "(no such|not found|cannot find|unknown command|invalid|does not exist|unrecognized|no command|error:)" "$WITH_FILE" 2>/dev/null || true)
    WHC=$(echo "$WHC" | tr -d '\n\r' | grep -oE '[0-9]+' || echo 0)
    [ -z "$WHC" ] && WHC=0
    WITH_HALLUC_TOTAL=$((WITH_HALLUC_TOTAL + WHC))
    if grep -qiE "(cli-hub|cli.hub|registry|lookup|discover)" "$WITH_FILE" 2>/dev/null; then
      CLIHUB_USED=$((CLIHUB_USED + 1))
    fi
  fi
  
  if [ -f "$WITHOUT_FILE" ]; then
    WITHOUT_TEXT=$(cat "$WITHOUT_FILE" 2>/dev/null || echo "")
    if echo "$WITHOUT_TEXT" | grep -qiE "(mmx|opencli|kimi)\s+(image|search|quota|text|speech|adapter|list|plugin|browser|open|fetch|抓取|生成|搜索)"; then
      WITHOUT_TOOL_COUNT=$((WITHOUT_TOOL_COUNT + 1))
    fi
    WOHC=$(grep -ciE "(no such|not found|cannot find|unknown command|invalid|does not exist|unrecognized|no command|error:)" "$WITHOUT_FILE" 2>/dev/null || true)
    WOHC=$(echo "$WOHC" | tr -d '\n\r' | grep -oE '[0-9]+' || echo 0)
    [ -z "$WOHC" ] && WOHC=0
    WITHOUT_HALLUC_TOTAL=$((WITHOUT_HALLUC_TOTAL + WOHC))
  fi
done

WITH_AVG=$((WITH_TOTAL / 8))
WITHOUT_AVG=$((WITHOUT_TOTAL / 8))
WITH_TOOL_RATE=$((WITH_TOOL_COUNT * 100 / 8))
WITHOUT_TOOL_RATE=$((WITHOUT_TOOL_COUNT * 100 / 8))

# Determine verdict
if [ "$WITH_HALLUC_TOTAL" -lt "$WITHOUT_HALLUC_TOTAL" ] && [ "$WITH_TOOL_COUNT" -gt "$WITHOUT_TOOL_COUNT" ]; then
  VERDICT="✅ **cli-hub improves both accuracy and reliability.** Fewer hallucinations and better tool identification."
elif [ "$WITH_HALLUC_TOTAL" -lt "$WITHOUT_HALLUC_TOTAL" ]; then
  VERDICT="✅ **cli-hub reduces hallucinations** ($WITH_HALLUC_TOTAL vs $WITHOUT_HALLUC_TOTAL). Tool identification similar."
elif [ "$WITH_TOOL_COUNT" -gt "$WITHOUT_TOOL_COUNT" ]; then
  VERDICT="✅ **cli-hub improves tool identification** ($WITH_TOOL_COUNT/8 vs $WITHOUT_TOOL_COUNT/8). Hallucinations similar."
else
  VERDICT="⚠️ **No clear advantage observed.** Results are similar in both conditions."
fi

# Replace placeholders
sed -i "s/__WITH_AVG__/$WITH_AVG/" "$SUMMARY"
sed -i "s/__WITHOUT_AVG__/$WITHOUT_AVG/" "$SUMMARY"
sed -i "s/__WITH_TOOL_COUNT__/$WITH_TOOL_COUNT/" "$SUMMARY"
sed -i "s/__WITHOUT_TOOL_COUNT__/$WITHOUT_TOOL_COUNT/" "$SUMMARY"
sed -i "s/__WITH_TOOL_RATE__/$WITH_TOOL_RATE/" "$SUMMARY"
sed -i "s/__WITHOUT_TOOL_RATE__/$WITHOUT_TOOL_RATE/" "$SUMMARY"
sed -i "s/__WITH_HALLUC_TOTAL__/$WITH_HALLUC_TOTAL/" "$SUMMARY"
sed -i "s/__WITHOUT_HALLUC_TOTAL__/$WITHOUT_HALLUC_TOTAL/" "$SUMMARY"
sed -i "s/__CLIHUB_USED__/$CLIHUB_USED/" "$SUMMARY"
sed -i "s/__DATE__/$SUMMARY_DATE/" "$SUMMARY"
sed -i "s|__VERDICT__|$VERDICT|" "$SUMMARY"

pass "SUMMARY.md generated at $SUMMARY"

# ════════════════════════════════════════════════════════════════
#  PHASE 6: Cleanup — Restore cli-hub
# ════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Phase 6: Restore cli-hub               ║"
echo "╚══════════════════════════════════════════╝"
echo ""

info "Re-installing cli-hub ..."
rm -rf ~/.agents/skills/cli-hub ~/.claude/skills/cli-hub
mkdir -p ~/.agents/skills/cli-hub ~/.claude/skills/cli-hub
cp "$CLI_HUB_SRC/SKILL.md" ~/.agents/skills/cli-hub/
cp -r "$CLI_HUB_SRC/scripts" ~/.agents/skills/cli-hub/
cp -r "$CLI_HUB_SRC/references" ~/.agents/skills/cli-hub/ 2>/dev/null || true
cp "$CLI_HUB_SRC/SKILL.md" ~/.claude/skills/cli-hub/
cp -r "$CLI_HUB_SRC/scripts" ~/.claude/skills/cli-hub/
cp -r "$CLI_HUB_SRC/references" ~/.claude/skills/cli-hub/ 2>/dev/null || true

info "Running discover ..."
mkdir -p ~/.openclaw/cli-registry
cd ~/.agents/skills/cli-hub
python3 scripts/cli-registry.py discover 2>&1 | tail -5
# Also re-register kimi
python3 scripts/cli-registry.py register kimi --desc "Kimi AI CLI" 2>&1 | tail -1 || true
mkdir -p ~/.claude/cli-registry
cp ~/.openclaw/cli-registry/*.json ~/.claude/cli-registry/ 2>/dev/null || true

RESTORE_COUNT=$(ls ~/.openclaw/cli-registry/*.json 2>/dev/null | grep -v keywords | wc -l)
pass "cli-hub restored — $RESTORE_COUNT tools registered"

# ════════════════════════════════════════════════════════════════
#  FINAL SCORECARD
# ════════════════════════════════════════════════════════════════
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  🏆 FINAL SCORECARD                     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Model:          $MODEL"
echo "  Tests:          8 prompts × 2 rounds"
echo "  With avg:       ${WITH_AVG} bytes"
echo "  Without avg:    ${WITHOUT_AVG} bytes"
echo "  Tool ID (with):    ${WITH_TOOL_COUNT}/8 (${WITH_TOOL_RATE}%)"
echo "  Tool ID (without): ${WITHOUT_TOOL_COUNT}/8 (${WITHOUT_TOOL_RATE}%)"
echo "  Halluc (with):     $WITH_HALLUC_TOTAL"
echo "  Halluc (without):  $WITHOUT_HALLUC_TOTAL"
echo "  cli-hub refs:      $CLIHUB_USED/8"
echo ""
echo "  Verdict: $VERDICT"
echo ""

echo "╔══════════════════════════════════════════╗"
echo "║  ✅ Benchmark Complete!                 ║"
echo "║  Results: $RESULTS"
echo "║  Summary: $SUMMARY"
echo "╚══════════════════════════════════════════╝"
