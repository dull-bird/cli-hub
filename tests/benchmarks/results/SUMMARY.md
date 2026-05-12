# Benchmark Results — V4 Pro (2026-05-12)

Model: DeepSeek V4 Pro (max effort)
Method: `claude -p "..." --model deepseek-v4-pro`, one-shot, no interaction

## WITH cli-hub (7/8 used cli-hub correctly)

| Test | Bytes | Used cli-hub | Hallucinated |
|------|-------|-------------|-------------|
| U1 mmx image | 1043 | ✓ | 0 |
| U2 mmx search | 1712 | — | 0 |
| U3 mmx quota | 1829 | ✓ | 0 |
| U4 mmx text | 577 | ✓ | 0 |
| U5 mmx speech | 591 | ✓ | 0 |
| U6 opencli list | 1335 | ✓ | 0 |
| U7 opencli browse | 882 | ✓ | 1 |
| U8 opencli site | 3039 | ✓ | 0 |

## WITHOUT cli-hub (5/8 hallucinated tool identity)

| Test | Bytes | Used cli-hub | Hallucinated |
|------|-------|-------------|-------------|
| U1 mmx image | 1870 | — | ✗ (2) |
| U2 mmx search | 504 | — | ✗ (1) |
| U3 mmx quota | 1315 | — | — |
| U4 mmx text | 1684 | — | — |
| U5 mmx speech | 1012 | — | ✗ (4) |
| U6 opencli list | 487 | — | — |
| U7 opencli browse | 922 | — | — |
| U8 opencli site | 1350 | — | ✗ (1) |

## Key Insight

Without cli-hub, V4 Pro (reasoning model) over-thinks tool names:
- "mmx" → "could be Midjourney, macOS say command, espeak..."
- "opencli" → "could be OpenAPI CLI, OpenWear..."

With cli-hub, V4 Pro references the registry instead of guessing.
