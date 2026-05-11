#!/usr/bin/env python3
"""CLI Registry — unified management for external CLI tools.

Reads/writes lightweight JSON registry entries in ~/.openclaw/cli-registry/.
Powers the external-cli OpenClaw AgentSkill.

Usage:
    python3 cli-registry.py register <name> [--binary <bin>] [--desc <text>]
    python3 cli-registry.py list [--format json]
    python3 cli-registry.py lookup <name>
    python3 cli-registry.py discover [--scan-path <dir>]
    python3 cli-registry.py remove <name>
    python3 cli-registry.py help <name>
    python3 cli-registry.py --version
"""

import json
import os
import re
import sys
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

VERSION = "1.0.0"
REGISTRY_DIR = Path.home() / ".openclaw" / "cli-registry"
SKILLS_DIR = Path.home() / ".agents" / "skills"

# Common CLI binaries to scan during discover
KNOWN_CLIS = [
    "jq", "yq", "fzf", "rg", "fd", "bat", "eza", "gh", "docker",
    "kubectl", "helm", "terraform", "aws", "gcloud", "az",
    "python3", "node", "npm", "pnpm", "yarn", "bun",
    "cargo", "go", "rustc", "make", "cmake", "gcc", "g++",
    "curl", "wget", "ffmpeg", "convert", "sqlite3", "psql",
    "mihomo", "mmx", "opencli", "code", "git", "htop", "ncdu",
    "ssh", "scp", "rsync", "tar", "gzip", "unzip", "zip",
    "sed", "awk", "grep", "find", "xargs", "wc", "sort", "uniq",
    "systemctl", "journalctl", "ss", "ip", "ping", "dig",
]


# ── helpers ────────────────────────────────────────────────────

def _run(cmd, timeout=10):
    """Run command and return (code, stdout, stderr)."""
    try:
        r = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=timeout
        )
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return -1, "", "binary not found: {}".format(cmd[0])
    except subprocess.TimeoutExpired:
        return -2, "", "timed out"


def _whereis(binary):
    """Check if binary exists on PATH."""
    return subprocess.call(["which", binary],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


def _find_official_skill(name):
    """Check if an official SKILL.md exists for this CLI."""
    for root in [SKILLS_DIR, Path.home() / ".openclaw" / "skills"]:
        sp = root / name / "SKILL.md"
        if sp.is_file():
            with open(sp, encoding="utf-8") as fh:
                head = fh.read(500)
            if head.startswith("---") and "name:" in head:
                return str(sp)
    return None


# ── help extraction ─────────────────────────────────────────────

def _extract_help(binary):
    """Run <binary> --help and extract subcommands, flags, and raw text."""
    result = {"binary": binary, "subcommands": [], "flags": [], "examples": []}

    # Try --help, -h, help in order
    for flag in ["--help", "-h", "help"]:
        code, out, err = _run([binary, flag], timeout=15)
        output = (out + err).strip()
        if len(output) > 80:
            result["help_raw"] = output[:8192]
            break
    else:
        code, out, err = _run([binary], timeout=10)
        output = (out + err).strip()
        if output:
            result["help_raw"] = output[:8192]

    if not result.get("help_raw"):
        result["help_raw"] = "{} — help unavailable".format(binary)
        return result

    text = result["help_raw"]

    # ── subcommand extraction ──
    # Pattern A: "  command    description" (argparse, cobra, clap)
    # Pattern B: "   command   description" (git style)
    # Pattern C: bullet lists "* command: desc"
    subs = _parse_subcommands(text)
    result["subcommands"] = subs[:25]

    # ── flag extraction ──
    flags = _parse_flags(text)
    result["flags"] = flags[:20]

    return result


def _parse_subcommands(text):
    """Extract subcommands from help text using multiple patterns."""
    subs = []
    seen = set()

    # Common noise words to exclude
    noise = {"or", "and", "the", "for", "see", "a", "an", "of", "to", "in",
             "usage", "options", "commands", "examples", "arguments", "flags",
             "help", "all", "on", "off", "yes", "no", "true", "false",
             "be", "is", "it", "if", "by", "at", "also", "note", "use"}

    # Pattern 1: indented "  name  desc" (argparse / click style)
    for m in re.finditer(r'(?m)^\s{2,}([a-z][a-z0-9_-]{2,30})\s{2,}(.+)', text):
        name, desc = m.group(1), m.group(2).strip()[:120]
        if name.lower() not in noise and name not in seen:
            seen.add(name)
            subs.append({"name": name, "desc": desc})

    # Pattern 2: "  * name: desc" or "  - name: desc"
    for m in re.finditer(r'(?m)^\s*[-*]\s+([a-z][a-z0-9_-]{2,30}):?\s*(.*)', text):
        name, desc = m.group(1), m.group(2).strip()[:120]
        if name.lower() not in noise and name not in seen:
            seen.add(name)
            subs.append({"name": name, "desc": desc})

    return subs


def _parse_flags(text):
    """Extract flags from help text."""
    flags = []
    seen = set()

    for m in re.finditer(r'(?m)(-{1,2}[\w][\w-]*)(?:\s+(\w+))?\s*(.{0,80})', text):
        flag = m.group(1)
        if flag in ("-h", "--help", "-v", "--version"):
            continue
        value = m.group(2) if m.group(2) and not m.group(2).startswith("-") else ""
        desc = m.group(3).strip() if m.group(3) else ""
        if flag not in seen:
            seen.add(flag)
            flags.append({"flag": flag, "value": value, "desc": desc[:80]})

    return flags


# ── commands ─────────────────────────────────────────────────────

def cmd_register(args):
    """Register a CLI tool in the registry."""
    name = args.cli
    binary = args.binary or name
    desc = args.desc or ""

    if not args.force and not _whereis(binary):
        print("Warning: {} not found on PATH. Use --force to register anyway.".format(binary))

    official = _find_official_skill(name)
    info = _extract_help(binary)

    entry = {
        "name": name,
        "binary": binary,
        "description": desc or "External CLI: {}".format(name),
        "official_skill": official,
        "registered_at": datetime.now().isoformat(),
        "auto_discovered": info,
    }

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    path = REGISTRY_DIR / "{}.json".format(name)
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Registered: {} -> {}".format(name, path))
    if official:
        print("   Official skill: {} (takes priority)".format(official))
    n_subs = len(info.get("subcommands", []))
    n_flags = len(info.get("flags", []))
    if n_subs or n_flags:
        print("   Discovered: {} subcommands, {} flags".format(n_subs, n_flags))


def cmd_list(args):
    """List all registered CLI tools."""
    entries = sorted(REGISTRY_DIR.glob("*.json"))
    if not entries:
        print("No CLI tools registered.")
        print("Try: python3 cli-registry.py discover")
        return

    if args.format == "json":
        result = {}
        for e in entries:
            d = json.loads(e.read_text(encoding="utf-8"))
            ad = d.get("auto_discovered", {})
            result[d["name"]] = {
                "binary": d.get("binary"),
                "description": d.get("description"),
                "has_official_skill": bool(d.get("official_skill")),
                "subcommands": len(ad.get("subcommands", [])),
                "flags": len(ad.get("flags", [])),
            }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        header = "{:<22s} {:<17s} {:<10s} {:>5s}  {}".format(
            "NAME", "BINARY", "OFFICIAL", "SUBS", "DESCRIPTION")
        print(header)
        print("-" * 80)
        for e in entries:
            d = json.loads(e.read_text(encoding="utf-8"))
            official = "yes" if d.get("official_skill") else "-"
            ad = d.get("auto_discovered", {})
            subs = len(ad.get("subcommands", []))
            print("{:<22s} {:<17s} {:<10s} {:>5d}  {}".format(
                d["name"], d.get("binary", d["name"]),
                official, subs, d.get("description", "")[:40]))


def cmd_lookup(args):
    """Show full registry info for a CLI tool."""
    path = REGISTRY_DIR / "{}.json".format(args.cli)
    if not path.is_file():
        print("Not registered: {}".format(args.cli))
        print("  Try: python3 cli-registry.py register {}".format(args.cli))
        sys.exit(1)

    d = json.loads(path.read_text(encoding="utf-8"))

    print("# CLI: {}".format(d["name"]))
    print("Binary: {}".format(d.get("binary")))
    if d.get("description"):
        print("Description: {}".format(d["description"]))
    if d.get("official_skill"):
        print("Official Skill: {}".format(d["official_skill"]))
        print("> CHECK official skill FIRST for authoritative instructions")
    print("Registered: {}".format(d.get("registered_at", "unknown")))

    ad = d.get("auto_discovered", {})
    subs = ad.get("subcommands", [])
    flags = ad.get("flags", [])
    raw = ad.get("help_raw", "")

    if subs:
        print("\n## Subcommands ({})".format(len(subs)))
        for s in subs[:20]:
            print("  {:<22s} {}".format(s["name"], s["desc"]))

    if flags:
        print("\n## Flags ({})".format(len(flags)))
        for f in flags[:15]:
            val = " <{}>".format(f["value"]) if f.get("value") else ""
            print("  {}{:<14s} {}".format(f["flag"], val, f.get("desc", "")))

    if raw:
        print("\n## Raw Help ({} chars)".format(len(raw)))
        print(raw[:3000])


def cmd_discover(args):
    """Auto-scan PATH for known CLI binaries and register them."""
    count = 0
    for binary in KNOWN_CLIS:
        if (REGISTRY_DIR / "{}.json".format(binary)).is_file():
            continue
        if _whereis(binary):
            print("Found: {} ...".format(binary), end=" ", flush=True)
            try:
                cmd_register(argparse.Namespace(
                    cli=binary, binary=binary, desc="", force=False))
                count += 1
            except Exception as exc:
                print("failed ({})".format(exc))

    # Also scan extra path if given
    if args.scan_path:
        sp = Path(args.scan_path)
        if sp.is_dir():
            for f in sp.iterdir():
                if f.is_file() and os.access(str(f), os.X_OK):
                    name = f.name
                    if not (REGISTRY_DIR / "{}.json".format(name)).is_file():
                        print("Found: {} ...".format(name), end=" ", flush=True)
                        try:
                            cmd_register(argparse.Namespace(
                                cli=name, binary=str(f), desc="", force=False))
                            count += 1
                        except Exception as exc:
                            print("failed ({})".format(exc))

    print("\nRegistered {} new CLI tools.".format(count))


def cmd_remove(args):
    """Remove a CLI from the registry."""
    path = REGISTRY_DIR / "{}.json".format(args.cli)
    if path.is_file():
        path.unlink()
        print("Removed: {}".format(args.cli))
    else:
        print("Not registered: {}".format(args.cli))


def cmd_help_cli(args):
    """Fetch live --help for a CLI (registered or not)."""
    binary = args.cli
    p = REGISTRY_DIR / "{}.json".format(args.cli)
    if p.is_file():
        binary = json.loads(p.read_text(encoding="utf-8")).get("binary", binary)

    code, out, err = _run([binary, "--help"], timeout=10)
    if code != 0:
        code, out, err = _run([binary, "-h"], timeout=10)
    if code != 0:
        code, out, err = _run([binary, "help"], timeout=10)
    output = (out + err).strip()
    if output:
        print(output[:5000])
    else:
        print("No help output from {}".format(binary))


# ── main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CLI Registry for OpenClaw external-cli Skill",
        prog="cli-registry")
    parser.add_argument("--version", action="version", version=VERSION)

    sub = parser.add_subparsers(dest="command")
    sub.required = True

    p = sub.add_parser("register", help="Register a CLI tool")
    p.add_argument("cli", help="CLI name")
    p.add_argument("--binary", help="Binary name if different")
    p.add_argument("--desc", help="Description")
    p.add_argument("--force", action="store_true", help="Register even if binary not on PATH")

    p = sub.add_parser("list", help="List registered CLIs")
    p.add_argument("--format", default="table", choices=["table", "json"])

    p = sub.add_parser("lookup", help="Look up a CLI")
    p.add_argument("cli", help="CLI name")

    p = sub.add_parser("discover", help="Auto-discover known CLI binaries")
    p.add_argument("--scan-path", help="Extra directory to scan for executables")

    p = sub.add_parser("remove", help="Remove from registry")
    p.add_argument("cli", help="CLI name")

    p = sub.add_parser("help", help="Fetch live --help output")
    p.add_argument("cli", help="CLI name or binary")

    args = parser.parse_args()

    cmds = {
        "register": cmd_register,
        "list": cmd_list,
        "lookup": cmd_lookup,
        "discover": cmd_discover,
        "remove": cmd_remove,
        "help": cmd_help_cli,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
