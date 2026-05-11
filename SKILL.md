---
name: cli-hub
description: >
  Unified interface for ALL external CLI tools. Triggers when the user mentions
  ANY CLI tool name (git, curl, gh, npm, docker, ffmpeg, jq, rg, fzf, awk, sed,
  grep, find, ssh, mihomo, opencli etc.) OR wants to "run", "use", "execute"
  a tool, OR asks "how to" use a CLI, OR says "用...命令", "帮我运行...".
  Use this skill FIRST whenever a request might involve a command-line tool.
---

# CLI Hub

One skill to manage all CLI tools. Works across OpenClaw, Claude Code, Codex CLI,
Cursor, and Aider.

## Platform Detection

At runtime, determine platform by checking which directories exist:

| Platform     | Skill root                | Registry root                    |
|-------------|---------------------------|----------------------------------|
| OpenClaw     | `~/.agents/skills/`       | `~/.openclaw/cli-registry/`      |
| Claude Code  | `~/.claude/skills/`       | `~/.claude/cli-registry/`        |
| Codex CLI    | `~/.agents/skills/`       | `~/.codex/cli-registry/`         |
| Cursor       | `~/.cursor/skills/`       | `~/.cursor/cli-registry/`        |

Fallback: run `<tool> --help` directly if no registry path is available.

See [references/platforms.md](references/platforms.md) for details.

## Priority Resolution

When the user wants to use a CLI tool:

1. **Official Skill** — `$SKILLS_ROOT/<tool>/SKILL.md` exists → use it
2. **Registry** — `$REGISTRY_ROOT/<tool>.json` → cached help + subcommands
3. **Live Discovery** — run `<tool> --help` and parse on the fly

## Registry Script

```bash
# Auto-detect platform; override with env vars:
#   CLI_HUB_REGISTRY=~/.my-registry
#   CLI_HUB_SKILLS=~/.my-skills

SCRIPT=$(find ~/.agents/skills/cli-hub -name cli-registry.py 2>/dev/null || \
         find ~/.claude/skills/cli-hub -name cli-registry.py 2>/dev/null || \
         find ~/.cursor/skills/cli-hub -name cli-registry.py 2>/dev/null)
```

### Commands

| Command | Use |
|---------|-----|
| `python3 $SCRIPT register <cli> [--binary <bin>] [--desc <text>]` | Register a CLI tool |
| `python3 $SCRIPT list [--format json]` | List all registered tools |
| `python3 $SCRIPT lookup <cli>` | Show structured info (subcommands, flags, help) |
| `python3 $SCRIPT discover` | Auto-scan system for known binaries |
| `python3 $SCRIPT remove <cli>` | Remove from registry |
| `python3 $SCRIPT help <cli>` | Live `--help` dump (registered or not) |

### Decision Tree

```
1. ls $SKILLS_ROOT/<tool>/SKILL.md
   → EXISTS: read and follow that skill (it's authoritative)
   → NOT FOUND: continue

2. python3 $SCRIPT lookup <tool>
   → FOUND: see subcommands, flags, raw help → construct the command
   → NOT FOUND: continue

3. Run: <tool> --help
   → Parse the output to understand usage
   → Register if useful: python3 $SCRIPT register <tool>
```

## Typical Workflows

### Known registered tool
```
User: "用 jq 把 name 字段提取出来"
→ lookup shows binary=jq, has filter command
→ Run: jq '.name' input.json
```

### Unknown tool (fallback)
```
User: "用 xsv 处理这个 csv"
→ No official skill, not in registry
→ Run: xsv --help → understand subcommands
→ Run: xsv select name,age data.csv
→ Register: python3 $SCRIPT register xsv
```

### New tool installed
```
User: "我刚装了 ripgrep"
→ Run: python3 $SCRIPT discover
→ rg now in registry
→ Future queries hit cache instantly
```

## Design Principle

- **No duplication:** If an official SKILL.md exists, this skill defers completely
- **Registry is cache, not source:** `--help` is the ground truth; registry caches it
- **JSON not YAML:** Registry entries are plain JSON, no frontmatter, machine-readable
- **Always fallback:** Even unregistered tools work via live `--help`
