#!/usr/bin/env python3
"""cli-hub hook for Claude Code (and Claude-Code-compatible agents).

Wires the CLI registry into two moments so the agent never has to *remember*
to look things up:

  UserPromptSubmit  Inject the list of installed-but-unfamiliar CLI tools, so
                    the agent knows they exist at all (solves "I didn't know
                    mmx could do that"). Injected once per session.

  PreToolUse(Bash)  When a command uses an unfamiliar tool, inject that tool's
                    usage hint (subcommands / flags) right before it runs.
                    Injected once per tool per session.

Both are non-blocking: they only add context, never deny a command. Only tools
flagged "novel" surface — well-known tools (git, jq, docker, ...) are ignored,
so the context cost stays tiny.

Install with scripts/install-hooks.py. Pure stdlib, no dependencies.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "cli-registry.py"

# Wrapper commands to skip when finding the "real" tool in a segment.
_WRAPPERS = {"sudo", "doas", "command", "env", "time", "nohup", "nice",
             "xargs", "stdbuf", "setsid", "exec", "builtin", "then", "do",
             "else", "if", "while"}


def _registry(*cli_args, timeout=8):
    try:
        r = subprocess.run([sys.executable, str(SCRIPT), *cli_args],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           universal_newlines=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except Exception:
        return -1, ""


def _seen(session_id, key):
    """Return True the first time (session_id, key) is seen; record it."""
    d = Path(tempfile.gettempdir()) / "cli-hub-hooks" / (session_id or "nosession")
    try:
        d.mkdir(parents=True, exist_ok=True)
        f = d / re.sub(r"[^A-Za-z0-9_.-]", "_", key)[:120]
        if f.exists():
            return False
        f.write_text("")
    except Exception:
        return True  # fail open: better to inject twice than crash
    return True


def _emit(event, context):
    if context:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event, "additionalContext": context}}))
    sys.exit(0)


def _candidate_tools(command):
    """Best-effort: pull the leading binary name from each command segment."""
    out, seen = [], set()
    for seg in re.split(r"\|\||&&|[|;&\n]", command):
        toks = seg.strip().split()
        i = 0
        while i < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[i]):
            i += 1  # skip VAR=val assignments
        while i < len(toks) and toks[i] in _WRAPPERS:
            i += 1  # skip sudo/env/... wrappers
        if i >= len(toks):
            continue
        name = os.path.basename(toks[i])
        if re.match(r"^[a-z][a-z0-9._-]*$", name) and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def handle_user_prompt(data):
    if not _seen(data.get("session_id", ""), "__session__"):
        sys.exit(0)  # only the first prompt of a session does the work
    # Keep the registry fresh — all cheap, daily-gated, and best-effort.
    _registry("autodiscover", timeout=20)              # new tools installed since last time
    _registry("skills-check", "--daily", timeout=20)   # official-skill status (local)
    _, drift = _registry("check-stale", "--novel", "--daily", "--update", timeout=40)

    code, out = _registry("non-standard", "--format", "text")
    if code != 0 or not out:
        sys.exit(0)
    ctx = ("This machine has these non-standard CLI tools installed that you "
           "likely don't know from training. Consider them when they fit the "
           "user's request; verify exact usage before running:\n" + out)
    updated = [l for l in drift.splitlines() if l.startswith("updated:")]
    if updated:
        ctx += "\n\nUpdated since last check (cached info refreshed):\n" + "\n".join(updated)
    _emit("UserPromptSubmit", ctx)
    sys.exit(0)


def handle_pre_tool(data):
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    command = (data.get("tool_input") or {}).get("command", "")
    if not command:
        sys.exit(0)
    sid = data.get("session_id", "")
    hints = []
    for tool in _candidate_tools(command):
        if not _seen(sid, "tool:" + tool):
            continue
        code, out = _registry("hint", tool)
        if code == 0 and out:
            hints.append(out)
    if hints:
        _emit("PreToolUse",
              "cli-hub — usage for unfamiliar tool(s) in this command:\n\n"
              + "\n\n".join(hints))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    event = data.get("hook_event_name", "")
    if event == "UserPromptSubmit":
        handle_user_prompt(data)
    elif event == "PreToolUse":
        handle_pre_tool(data)
    sys.exit(0)


if __name__ == "__main__":
    main()
