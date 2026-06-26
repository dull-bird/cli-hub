#!/usr/bin/env python3
"""Install (or remove) the cli-hub hooks in Claude Code settings.

Adds a UserPromptSubmit hook and a PreToolUse(Bash) hook, both invoking
scripts/cli-hub-hook.py. Idempotent — safe to run repeatedly.

    python3 scripts/install-hooks.py             # user settings (~/.claude)
    python3 scripts/install-hooks.py --project   # project settings (./.claude)
    python3 scripts/install-hooks.py --uninstall

After installing, restart Claude Code (or run /hooks) so it reloads settings.
"""
import argparse
import json
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "cli-hub-hook.py"
CMD = "python3 {}".format(HOOK)

# (event, matcher) — UserPromptSubmit has no matcher; PreToolUse matches Bash.
DEFS = [("UserPromptSubmit", None), ("PreToolUse", "Bash")]


def _load(path):
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            sys.exit("Refusing to touch unparseable {}".format(path))
    return {}


def _has_cmd(group, cmd):
    return any(h.get("command") == cmd
               for block in group for h in block.get("hooks", []))


def install(settings):
    hooks = settings.setdefault("hooks", {})
    for event, matcher in DEFS:
        group = hooks.setdefault(event, [])
        if _has_cmd(group, CMD):
            continue
        block = {"hooks": [{"type": "command", "command": CMD}]}
        if matcher is not None:
            block["matcher"] = matcher
        group.append(block)
    return settings


def uninstall(settings):
    hooks = settings.get("hooks", {})
    for event, _ in DEFS:
        group = hooks.get(event, [])
        group[:] = [b for b in group if not _has_cmd([b], CMD)]
        if not group:
            hooks.pop(event, None)
    if not hooks:
        settings.pop("hooks", None)
    return settings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", action="store_true",
                    help="Write ./.claude/settings.json instead of ~/.claude")
    ap.add_argument("--uninstall", action="store_true")
    args = ap.parse_args()

    if not HOOK.is_file():
        sys.exit("Hook script not found: {}".format(HOOK))

    path = (Path(".claude/settings.json") if args.project
            else Path.home() / ".claude" / "settings.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    settings = uninstall(_load(path)) if args.uninstall else install(_load(path))
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")

    print("{} cli-hub hooks in {}".format(
        "Removed" if args.uninstall else "Installed", path))
    if args.uninstall:
        return
    print("  UserPromptSubmit + PreToolUse(Bash) -> {}".format(CMD))
    print("\nNext: restart Claude Code (or run /hooks) to load them.")
    print("From now on, tools you install are surfaced automatically. For tools you")
    reg = HOOK.parent / "cli-registry.py"
    print("already have, list them with:  python3 {} autodiscover --seed".format(reg))
    print("then surface the ones you want: python3 {} flag <tool> <tool> ...".format(reg))


if __name__ == "__main__":
    main()
