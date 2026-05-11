# cli-hub

> One Skill to rule them all.

An [OpenClaw AgentSkill](https://agentskills.io) that gives AI agents a unified interface to **any** CLI tool on your system — without writing a separate skill for each one.

**The problem:** every CLI tool needs its own `SKILL.md` for an AI agent to know how to use it. 20 tools = 20 skills = maintenance nightmare.

**The solution:** one skill + a lightweight registry. The agent checks: **official skill → registry → live `--help`**. Tools with official skills take priority. Everything else is auto-discovered.

## How It Works

```
User: "use jq to extract the name field"
              │
              ▼
     ┌─────────────────┐
     │  cli-hub    │  ← single skill (not N)
     └────────┬────────┘
              │
     ┌────────▼──────────┐
     │ 1. Official Skill? │  Authoritative SKILL.md exists?
     │    → USE IT        │
     ├────────────────────┤
     │ 2. Registry JSON?  │  ~/.openclaw/cli-registry/<tool>.json
     │    → cached help   │
     ├────────────────────┤
     │ 3. Live --help     │  Run <tool> --help on the fly
     └────────────────────┘
```

## Install

```bash
# Via ClawHub (recommended)
openclaw skills install cli-hub

# Or manually
git clone https://github.com/dull-bird/cli-hub.git
cp -r cli-hub ~/.agents/skills/cli-hub
```

## 30-Second Demo

```bash
# 1. Auto-discover everything on your system
$ python3 cli-registry.py discover

Found: jq ...    Registered: jq (15 subcommands, 8 flags)
Found: fzf ...   Registered: fzf (3 subcommands, 6 flags)
Found: gh ...    Registered: gh (25 subcommands, 0 flags)
Found: rg ...    Registered: rg (10 subcommands, 8 flags)
Found: mihomo ...Registered: mihomo (official skill: takes priority)
Found: opencli ..Registered: opencli (official skill: takes priority)
...

Registered 13 new CLI tools.

# 2. List what's available
$ python3 cli-registry.py list

NAME          BINARY       OFFICIAL  SUBS  DESCRIPTION
─────────────────────────────────────────────────────────
curl          curl         -           0   External CLI: curl
gh            gh           -          25   External CLI: gh
git           git          -          19   Distributed version control
jq            jq           -          15   External CLI: jq
mihomo        mihomo       yes         0   External CLI: mihomo
opencli       opencli      yes         0   External CLI: opencli
...

# 3. Look up a tool
$ python3 cli-registry.py lookup gh

# CLI: gh
Binary: gh
Description: External CLI: gh

## Subcommands (25)
  auth              Authenticate gh with GitHub
  browse            Open the repository in the browser
  codespace         Connect to and manage codespaces
  gist              Manage gists
  issue             Manage issues
  pr                Manage pull requests
  release           Manage releases
  repo              Manage repositories
  run               View recent workflow runs
  secret            Manage secrets
...
```

## Agent Interaction Demo

```
 👤 User:    "用 jq 把 data.json 里的所有 name 字段提取出来"
            ─────────────────────────────────────────────
 🤖 Agent:  [checks: ~/.agents/skills/jq/SKILL.md → not found]
            [lookup: registry/jq.json → found, 15 commands]
            [runs: jq '.[].name' data.json]
            ─────────────────────────────────────────────
            ["Alice", "Bob", "Charlie"]

 👤 User:    "用 gh 看看我 open 的 PR"
            ─────────────────────────────────────────────
 🤖 Agent:  [checks: ~/.agents/skills/gh/SKILL.md → not found]
            [lookup: registry/gh.json → found, has 'pr' subcommand]
            [runs: gh pr list --state open]
            ─────────────────────────────────────────────
            #1 Add login page   about 2 hours ago
            #3 Fix navbar       about 1 day ago

 👤 User:    "切到日本节点"
            ─────────────────────────────────────────────
 🤖 Agent:  [checks: ~/.agents/skills/mihomo/SKILL.md → FOUND]
            [official skill takes priority]
            [uses: mihomo start; mihomo switch-node "日本 1 | SS | ZJ"]
```

## Priority in Action

```
User: "切到日本节点"
        │
        ├─ mihomo/SKILL.md  EXISTS → ✅ use it
        │  (handwritten, knows start/stop/sub/specific scripts)
        │
User: "gh pr list"
        │
        ├─ gh/SKILL.md  NOT EXISTS → skip
        │  └─ registry/gh.json  EXISTS → ✅ use it
        │     (cached 25 subcommands from --help)
        │
User: "xsv select name data.csv"
        │
        ├─ xsv/SKILL.md  NOT EXISTS → skip
        │  └─ registry/xsv.json  NOT EXISTS → skip
        │     └─ xsv --help  → ✅ live discovery
        │        (parse output, construct command, optionally register)
```

## Registry Format

Tools are stored as simple JSON files in `~/.openclaw/cli-registry/`:

```json
{
  "name": "jq",
  "binary": "jq",
  "description": "Command-line JSON processor",
  "official_skill": null,
  "registered_at": "2026-05-12T00:25:00.000000",
  "auto_discovered": {
    "subcommands": [
      {"name": "filter", "desc": "Apply a filter to the input JSON"},
      {"name": "map", "desc": "Transform each element of an array"}
    ],
    "flags": [
      {"flag": "-r", "value": "", "desc": "Raw output (no JSON quoting)"},
      {"flag": "-c", "value": "", "desc": "Compact output"}
    ],
    "help_raw": "jq - commandline JSON processor ..."
  }
}
```

See [examples/registry-entry.json](examples/registry-entry.json) for a full example.

No YAML frontmatter. No markdown. Just structured data. Lightweight enough for hundreds of tools.

## Commands

| Command | Description |
|---------|-------------|
| `register <name>` | Register a CLI tool (extracts help, subcommands, flags) |
| `list` | List all registered tools |
| `lookup <name>` | Show full info for a tool |
| `discover` | Auto-detect known binaries and register them |
| `remove <name>` | Remove from registry |
| `help <name>` | Fetch live `--help` output |

## Why Not N Skills?

- **Explosion:** 20 CLI tools = 20 skills = 20 files to maintain
- **Staleness:** Tools update, skills lag behind → `--help` is always current
- **Official skills:** CLI authors may publish better skills → priority system respects them
- **Onboarding:** Run `discover` once, all tools available immediately

Think of this as `opencli external register` but for AI agents instead of humans.

## Related

- [OpenClaw Skills](https://docs.openclaw.ai/tools/skills)
- [AgentSkills Spec](https://agentskills.io)
- [ClawHub](https://clawhub.ai)
- Inspired by [prefrontalsys/register-tool](https://github.com/prefrontalsys/register-tool) (Claude Code)
