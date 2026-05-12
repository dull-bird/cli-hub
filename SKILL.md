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
    │    lookup jq → binary, description, keywords,
    │    subcommands, help_raw        │
    │    → FOUND: construct command   │
    ├─────────────────────────────────┤
    │ 5. Live --help (fallback)       │
    │    Only if registry not found   │
    └─────────────────────────────────┘
```

### Reading help_raw (for UNKNOWN tools)

When the tool is NOT in the built-in knowledge base (no human-written description,
no keywords), you MUST read its `help_raw` field — it's your only source of truth.

**How to parse help_raw efficiently:**

1. **Find the usage line** — usually at the top or marked "Usage:" / "用法:"
   → Tells you the basic invocation pattern: `tool [OPTIONS] COMMAND [ARGS]`

2. **Scan for COMMAND sections** — look for headings like:
   - "Commands:", "Subcommands:", "Available commands:"
   - "Unit Commands:", "Management Commands:"
   - Single-word lines ending with `:` or `：` followed by indented blocks
   - Each indented line is typically a command + description

3. **Identify OPTIONS sections** — look for:
   - Flag-like patterns: `-x`, `--option`, `--option=VALUE`
   - Lines starting with `-` and followed by a description
   - Help text often lists all options before any commands

4. **Extract the summary** — the first non-flag, non-usage line over 15 chars
   is usually the tool's one-line description

5. **Watch for nested commands** — some tools use `cmd subcmd <args>`:
   - `subscription use <name>` → "use" is a sub-action of "subscription"
   - `container ls`, `container start` → grouped under "container"

6. **Check description/keywords from registry** — even for unknown tools,
   `_extract_summary()` may have found a description. The `keywords` field
   may be empty for unknown tools; fall back to tokenizing the description.

**Example: parsing an unseen tool's help_raw:**

```
help_raw = """
xsv 0.13.0
Usage: xsv <command> [<args>...]

Commands:
    cat      Concatenate CSV files by rows
    count    Count records
    flatten  Flatten conditional nested fields
    fmt      Reformat CSV data
    headers  Show headers of CSV data
    select   Select columns from CSV
    sort     Sort CSV data
    ...
"""

→ Look at "Commands:" heading → find indented blocks
→ Commands: cat, count, flatten, fmt, headers, select, sort
→ Each has a description after the name
→ Construct: xsv select name,age data.csv
```

## Typical Workflows

### Known tool (in knowledge base)
```
User: "用 jq 把 name 字段提取出来"
→ search "json extract" → jq (built-in desc + keywords)
→ lookup jq → binary=jq, has 'filter' subcommand
→ Run: jq '.name' input.json
```

### Unknown tool (NOT in knowledge base — rely on help_raw)
```
User: "用 xsv 处理这个 csv"
→ No official skill, not in KB, not in registry
→ Run: xsv --help → store as help_raw
→ READ help_raw (follow "Reading help_raw" guide above):
   → Usage: xsv <command> [<args>...]
   → Commands: cat, count, select, sort, headers...
   → Found "select" subcommand: "Select columns from CSV"
→ Run: xsv select name,age data.csv
→ Register: python3 $SCRIPT register xsv
```

### Unknown tool (found in registry, but no KB entry)
```
User: "用 fq 解析这个二进制文件"
→ search "binary parse" → fq (matched from description tokens)
→ lookup fq → binary=fq, description="Tool for inspecting binary data"
→ description came from _extract_summary(), keywords from description tokens
→ READ help_raw to learn subcommands and options
→ Construct command from help_raw
```

## Design Principle

- **No duplication:** If an official SKILL.md exists, this skill defers completely
- **Registry is cache, not source:** `--help` is the ground truth; registry caches it
- **JSON not YAML:** Registry entries are plain JSON, no frontmatter, machine-readable
- **Always fallback:** Even unregistered tools work via live `--help`
