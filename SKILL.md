---
name: clihub
description: Universal CLI discovery gateway — one skill to manage all CLI tools
tags: [cli, agent, tool, discovery]
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

When the user wants to use a CLI tool, resolve in order:

1. **Official Skill** — `$SKILLS_ROOT/<tool>/SKILL.md` exists → use it
2. **Registry** — `$REGISTRY_ROOT/<tool>.json` → cached help, subcommands, keywords
3. **Keyword Search** — `$REGISTRY_ROOT/.keywords.json` → maps task words to tool names
4. **Live Discovery** — run `<tool> --help` and parse on the fly

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
| `python3 $SCRIPT lookup <cli>` | Show structured info (desc, subcommands, flags, keywords, help) |
| `python3 $SCRIPT search <keyword...>` | Find tools by task keywords (e.g. "json filter") |
| `python3 $SCRIPT discover` | Auto-scan system for known binaries |
| `python3 $SCRIPT remove <cli>` | Remove from registry |
| `python3 $SCRIPT help <cli>` | Fetch live `--help` output |
| `python3 $SCRIPT remove <cli>` | Remove from registry |
| `python3 $SCRIPT help <cli>` | Live `--help` dump (registered or not) |

### Decision Tree

```
User: "extract JSON fields from data.json"
        │
    ┌───▼─────────────────────────────┐
    │ 1. Explicit tool mentioned?     │
    │    "use jq to..." → skip to step 4
    ├─────────────────────────────────┤
    │ 2. Keyword Search               │
    │    search "json extract" → jq (2 hits), yq (1 hit)
    │    → jq is best match
    ├─────────────────────────────────┤
    │ 3. Check Official Skill         │
    │    ls $SKILLS_ROOT/jq/SKILL.md  │
    │    → NOT FOUND → continue       │
    ├─────────────────────────────────┤
    │ 4. Check Registry               │
    │    lookup jq → binary=jq, has 'filter' subcommand
    │    → FOUND: construct command   │
    ├─────────────────────────────────┤
    │ 5. Live --help (fallback)       │
    │    Only if registry not found   │
    └─────────────────────────────────┘
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
