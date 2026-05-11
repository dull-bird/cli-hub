---
name: cli-hub
description: >
  Universal CLI discovery gateway. Use this skill FIRST whenever the user appears
  to be running, asking about, or interacting with ANY command-line tool.
  Trigger patterns: "run <cmd>", "execute <cmd>", "用 <cmd>",
  "帮我 <run/look/check/do>", "怎么用 <tool>", any backtick-wrapped
  command, any line that looks like a shell command with flags/arguments.
  When triggered, resolve the tool via: official skill → registry → --help.
---

# CLI Hub

One skill to manage all CLI tools. Works across OpenClaw, Claude Code, Codex CLI,
Cursor, and Aider.

## Trigger Check (read FIRST)

This skill triggers broadly — any mention of a CLI. To avoid overloading the
context window, do a quick sanity check before proceeding:

- Is the user asking something purely conversational? ("你好", "今天天气", ...) → skip
- Is another official skill already handling this? → defer to it
- Does the request involve running a tool, looking up a command, or understanding
  CLI output? → proceed

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
