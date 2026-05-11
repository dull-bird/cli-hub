#!/usr/bin/env python3
"""cli-hub — CLI Registry — unified management for external CLI tools.

Reads/writes lightweight JSON registry entries. Powers the cli-hub AgentSkill.
Compatible with OpenClaw, Claude Code, Codex CLI, Cursor, Aider.

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

VERSION = "1.1.0"
REGISTRY_DIR = Path.home() / ".openclaw" / "cli-registry"
SKILLS_DIR = Path.home() / ".agents" / "skills"

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
    return subprocess.call(["which", binary],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


def _find_official_skill(name):
    for root in [SKILLS_DIR, Path.home() / ".openclaw" / "skills"]:
        sp = root / name / "SKILL.md"
        if sp.is_file():
            with open(sp, encoding="utf-8") as fh:
                head = fh.read(500)
            if head.startswith("---") and "name:" in head:
                return str(sp)
    return None


# ── help extraction ─────────────────────────────────────────────

def _fetch_help_text(binary, subcommand=None):
    """Get help text trying --help, -h, help, man, bare invocation."""
    if subcommand:
        attempts = [
            [binary, subcommand, "-h"],        # short help first (avoid man pages)
            [binary, subcommand, "--help"],
            [binary, "help", subcommand],
        ]
    else:
        attempts = [
            [binary, "--help"],
            [binary, "-h"],
            [binary, "help"],
        ]

    for cmd in attempts:
        code, out, err = _run(cmd, timeout=15)
        output = (out + err).strip()
        if len(output) > 80:
            return output

    # man page fallback
    code, out, err = _run(["man", binary], timeout=10)
    if len(out.strip()) > 80:
        return out.strip()[:16384]

    # bare invocation
    code, out, err = _run([binary], timeout=10)
    output = (out + err).strip()
    return output if output else ""


def _extract_help(binary):
    """Extract structured help: usage, subcommands with options, global options."""
    text = _fetch_help_text(binary)
    if not text:
        return {"binary": binary, "help_raw": "{} — help unavailable".format(binary)}

    result = {
        "binary": binary,
        "help_raw": text[:12288],
        "usage": _extract_usage(text),
        "subcommands": {},
        "global_options": [],
    }

    subs = _parse_subcommands(text)
    top_subs = subs[:12]

    result["global_options"] = _parse_options(text)

    for s in top_subs:
        name = s["name"]
        sub_help = _fetch_help_text(binary, name)
        sub_info = {
            "desc": s["desc"],
            "usage": _extract_usage(sub_help) if sub_help else "",
            "options": _parse_options(sub_help) if sub_help else [],
        }
        result["subcommands"][name] = sub_info

    return result


def _extract_usage(text):
    """Extract usage line(s)."""
    lines = []
    in_usage = False
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r'^(usage|用法|使用方式|使い方)\s*[:：]', s, re.I):
            in_usage = True
            continue
        if in_usage:
            if s == "" or re.match(r'^[A-Z][a-z]+(\s+[a-z]+)*\s*[:：]', s):
                break
            if len(s) > 5:
                lines.append(s)
    if not lines:
        for line in text.split("\n"):
            s = line.strip()
            if s and not s.startswith("#") and len(s) > 10:
                lines.append(s)
                break
    return "\n".join(lines[:5])


def _parse_subcommands(text):
    """Extract subcommands from indented help text."""
    subs = []
    seen = set()
    noise = {
        "or", "and", "the", "for", "see", "a", "an", "of", "to", "in",
        "usage", "options", "commands", "examples", "arguments", "flags",
        "help", "all", "on", "off", "yes", "no", "true", "false",
        "be", "is", "it", "if", "by", "at", "also", "note", "use",
        "after", "before", "with", "from", "into", "out", "up", "per",
    }
    for m in re.finditer(r'(?m)^\s{2,}([a-z][a-z0-9._-]{2,30})\s{2,}(.+)', text):
        name, desc = m.group(1), m.group(2).strip()[:150]
        name = name.rstrip("._")
        if name.lower() not in noise and name not in seen:
            seen.add(name)
            subs.append({"name": name, "desc": desc})
    return subs


def _parse_options(text):
    """Extract options/flags with types."""
    options = []
    seen = set()
    skip = {"-h", "--help", "-v", "--version", "-V"}
    for m in re.finditer(
        r'(?m)^\s{0,6}(-{1,2}[\w][\w-]*(?:,\s*-{1,2}[\w][\w-]*)?)'
        r'(?:\s+(?!-)\S+)?\s{2,}(.+)',
        text
    ):
        flag_group = m.group(1)
        desc = m.group(2).strip()[:120] if m.group(2) else ""
        flags = [f.strip() for f in flag_group.split(",")]
        primary = next((f for f in flags if f.startswith("--")), flags[0])
        if primary in skip:
            continue
        value = ""
        type_match = re.search(r'(?:<([^>]+)>|\[=?(.+?)\])', desc)
        if type_match:
            value = type_match.group(1) or type_match.group(2)
        if primary not in seen:
            seen.add(primary)
            options.append({
                "flag": primary,
                "aliases": [f for f in flags if f != primary],
                "value": value,
                "desc": desc[:100]
            })
    return options[:25]


# ── commands ─────────────────────────────────────────────────────

def cmd_register(args):
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
    subs = info.get("subcommands", {})
    opts = info.get("global_options", [])
    print("   Discovered: {} subcommands with detail, {} global options".format(len(subs), len(opts)))


def cmd_list(args):
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
                "subcommands": len(ad.get("subcommands", {})),
                "global_options": len(ad.get("global_options", [])),
            }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        header = "{:<22s} {:<17s} {:<10s} {:>5s} {:>5s}  {}".format(
            "NAME", "BINARY", "OFFICIAL", "SUBS", "OPTS", "DESCRIPTION")
        print(header)
        print("-" * 90)
        for e in entries:
            d = json.loads(e.read_text(encoding="utf-8"))
            official = "yes" if d.get("official_skill") else "-"
            ad = d.get("auto_discovered", {})
            subs = len(ad.get("subcommands", {}))
            opts = len(ad.get("global_options", []))
            print("{:<22s} {:<17s} {:<10s} {:>5d} {:>5d}  {}".format(
                d["name"], d.get("binary", d["name"]),
                official, subs, opts, d.get("description", "")[:35]))


def cmd_lookup(args):
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
        print("Official Skill: {} (takes priority)".format(d["official_skill"]))

    ad = d.get("auto_discovered", {})

    usage = ad.get("usage")
    if usage:
        print("\n## Usage")
        print("```")
        print(usage)
        print("```")

    globals_opts = ad.get("global_options", [])
    if globals_opts:
        print("\n## Global Options ({})".format(len(globals_opts)))
        for o in globals_opts[:10]:
            v = " <{}>".format(o["value"]) if o.get("value") else ""
            aliases = " ({})".format(", ".join(o["aliases"])) if o.get("aliases") else ""
            print("  {}{}  {} {}".format(o["flag"], v, o.get("desc", ""), aliases))

    subs = ad.get("subcommands", {})
    if subs:
        print("\n## Subcommands ({})".format(len(subs)))
        for name, info in subs.items():
            print("\n### {} — {}".format(name, info.get("desc", "")))
            sub_usage = info.get("usage")
            if sub_usage:
                print("  Usage: `{}`".format(sub_usage.split("\n")[0][:120]))
            sub_opts = info.get("options", [])
            if sub_opts:
                for o in sub_opts[:8]:
                    v = " <{}>".format(o["value"]) if o.get("value") else ""
                    print("    {} {}  {}".format(o["flag"], v, o.get("desc", "")[:60]))


def cmd_discover(args):
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
    path = REGISTRY_DIR / "{}.json".format(args.cli)
    if path.is_file():
        path.unlink()
        print("Removed: {}".format(args.cli))
    else:
        print("Not registered: {}".format(args.cli))


def cmd_help_cli(args):
    binary = args.cli
    p = REGISTRY_DIR / "{}.json".format(args.cli)
    if p.is_file():
        binary = json.loads(p.read_text(encoding="utf-8")).get("binary", binary)
    output = _fetch_help_text(binary)
    if output:
        print(output[:5000])
    else:
        print("No help output from {}".format(binary))


def main():
    parser = argparse.ArgumentParser(
        description="CLI Registry for cli-hub AgentSkill",
        prog="cli-registry")
    parser.add_argument("--version", action="version", version=VERSION)

    sub = parser.add_subparsers(dest="command")
    sub.required = True

    p = sub.add_parser("register", help="Register a CLI tool")
    p.add_argument("cli", help="CLI name")
    p.add_argument("--binary", help="Binary name if different")
    p.add_argument("--desc", help="Description")
    p.add_argument("--force", action="store_true",
                   help="Register even if binary not on PATH")

    p = sub.add_parser("list", help="List registered CLIs")
    p.add_argument("--format", default="table", choices=["table", "json"])

    p = sub.add_parser("lookup", help="Look up a CLI")
    p.add_argument("cli", help="CLI name")

    p = sub.add_parser("discover", help="Auto-discover known CLI binaries")
    p.add_argument("--scan-path", help="Extra directory to scan")

    p = sub.add_parser("remove", help="Remove from registry")
    p.add_argument("cli", help="CLI name")

    p = sub.add_parser("help", help="Fetch live --help output")
    p.add_argument("cli", help="CLI name or binary")

    args = parser.parse_args()
    {
        "register": cmd_register,
        "list": cmd_list,
        "lookup": cmd_lookup,
        "discover": cmd_discover,
        "remove": cmd_remove,
        "help": cmd_help_cli,
    }[args.command](args)


if __name__ == "__main__":
    main()
