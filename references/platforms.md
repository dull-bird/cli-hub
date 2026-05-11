# Platform Paths

cli-hub auto-detects the current AI agent platform at runtime. If your platform
isn't listed, it falls back to running `<tool> --help` directly.

## Supported Platforms

| Platform     | Skill root                | Registry root                    |
|-------------|---------------------------|----------------------------------|
| OpenClaw     | `~/.agents/skills/`       | `~/.openclaw/cli-registry/`      |
| Claude Code  | `~/.claude/skills/`       | `~/.claude/cli-registry/`        |
| Codex CLI    | `~/.agents/skills/`       | `~/.codex/cli-registry/`         |
| Cursor       | `~/.cursor/skills/`       | `~/.cursor/cli-registry/`        |
| Aider        | `~/.aider/skills/`        | `~/.aider/cli-registry/`         |

Auto-detection order: check `SKILLS_ROOT` env var → check which dirs exist → fallback.

## Manual Override

```bash
export CLI_HUB_REGISTRY=~/.my-custom-dir
export CLI_HUB_SKILLS=~/.my-skills-dir
python3 cli-registry.py discover
```
