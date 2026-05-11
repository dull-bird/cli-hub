# external-cli

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
     │  external-cli    │  ← single skill (not N)
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
openclaw skills install external-cli

# Or manually
git clone https://github.com/dull-bird/external-cli.git
cp -r external-cli ~/.agents/skills/external-cli
```

## Quick Start

```bash
# Auto-discover all CLI tools on your system
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py discover

# Register a specific tool
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py register jq --desc "JSON processor"

# List registered tools
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py list

# Look up a tool (commands, flags, help)
python3 ~/.agents/skills/external-cli/scripts/cli-registry.py lookup git
```

## Priority System

| Priority | Source | When |
|----------|--------|------|
| 🥇 Highest | Official `SKILL.md` | `~/.agents/skills/<tool>/SKILL.md` exists |
| 🥈 Medium | Registry JSON | Tool was registered + help cached |
| 🥉 Lowest | Live `--help` | On-the-fly discovery |

Official skills always win. If a CLI's author publishes an OpenClaw skill later, the registry automatically defers to it. No cleanup needed.

## Registry Format

Tools are stored as simple JSON files in `~/.openclaw/cli-registry/`:

```json
{
  "name": "jq",
  "binary": "jq",
  "description": "JSON processor",
  "official_skill": null,
  "auto_discovered": {
    "subcommands": [...],
    "flags": [...],
    "help_raw": "..."
  }
}
```

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
