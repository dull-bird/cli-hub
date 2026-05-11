---
name: external-cli
description: >
  Unified interface for ALL external CLI tools. Use when the user wants to run
  or interact with ANY command-line tool (jq, fzf, gh, docker, mmx, mihomo,
  opencli, etc.). This skill automatically discovers CLI capabilities from
  a registry or live --help output. Triggers on: "run <tool>", "use <tool>",
  "用 <tool> 命令", any mention of a known binary name.
---

# External CLI Hub

One skill to manage all CLI tools. Instead of N separate skills, this single
entry handles ANY CLI tool through a priority-based discovery system.

## Priority Resolution

When the user wants to use a CLI tool, resolve in this order:

1. **Official Skill** — `~/.agents/skills/<tool>/SKILL.md` exists → use it (authoritative)
2. **Registry** — `~/.openclaw/cli-registry/<tool>.json` → cached help + subcommands
3. **Live Discovery** — run `<tool> --help` and parse on the fly

## Registry Script

```bash
SCRIPT=~/.agents/skills/external-cli/scripts/cli-registry.py
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

### Using a Tool (Decision Tree)

```
1. ls ~/.agents/skills/<tool>/SKILL.md
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
