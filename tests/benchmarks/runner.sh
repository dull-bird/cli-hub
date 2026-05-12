#!/bin/bash
ROUND="${1:-with-clihub}"
OUTDIR="/tmp/clihub-test-ai/$ROUND"
mkdir -p "$OUTDIR"

tests=(
  "A1_mmx_image:用mmx生成一张猫的图片，告诉我用什么命令"
  "A2_mmx_search:用mmx搜索deepseek api pricing相关信息"
  "A3_mmx_quota:查看mmx的API额度还剩多少"
  "A4_opencli_list:用opencli列出所有可用的网站适配器"
  "A5_opencli_browse:用opencli在浏览器里打开github.com"
  "A6_mmx_text:用mmx帮我生成一段关于AI agent的简短介绍"
  "A7_opencli_site:用opencli抓取bilibili热门视频"
  "A8_mmx_speech:用mmx列出可用的语音合成声音"
)

export ANTHROPIC_BASE_URL="http://localhost:8088"
export ANTHROPIC_API_KEY="not-needed"

for test in "${tests[@]}"; do
  id="${test%%:*}"
  prompt="${test#*:}"
  echo "--- $id ---"
  timeout 120 claude -p "$prompt" --model deepseek-chat > "$OUTDIR/${id}.txt" 2>&1
  echo "  $(wc -c < "$OUTDIR/${id}.txt") bytes"
done

echo "=== Done: $ROUND ==="
