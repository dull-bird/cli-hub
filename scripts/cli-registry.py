#!/usr/bin/env python3
"""cli-hub — CLI Registry — unified management for external CLI tools.

Reads/writes lightweight JSON registry entries. Powers the cli-hub AgentSkill.
Compatible with OpenClaw, Claude Code, Codex CLI, Cursor, Aider.

Usage:
    python3 cli-registry.py register <name> [--binary <bin>] [--desc <text>]
    python3 cli-registry.py list [--format json]
    python3 cli-registry.py lookup <name>
    python3 cli-registry.py discover [--scan] [--scan-path <dir>] [--no-filter]
    python3 cli-registry.py remove <name>
    python3 cli-registry.py help <name>
    python3 cli-registry.py search <keyword...>
    python3 cli-registry.py --version
"""

import json
import os
import re
import sys
import argparse
import subprocess
import fnmatch
import time
from datetime import datetime
from pathlib import Path

VERSION = "1.3.0"


def _default_registry_dir():
    """Resolve the registry location.

    Priority:
      1. CLI_HUB_REGISTRY env var (lets hooks/agents pin a shared registry)
      2. The first host-agent registry dir that already exists
      3. OpenClaw default (back-compat)
    """
    env = os.environ.get("CLI_HUB_REGISTRY")
    if env:
        return Path(env).expanduser()
    for base in (".openclaw", ".claude", ".cursor", ".codex"):
        cand = Path.home() / base / "cli-registry"
        if cand.is_dir():
            return cand
    return Path.home() / ".openclaw" / "cli-registry"


REGISTRY_DIR = _default_registry_dir()
SKILLS_DIR = Path.home() / ".agents" / "skills"
KEYWORD_INDEX_PATH = REGISTRY_DIR / ".keywords.json"

# ── P0: Knowledge base ──────────────────────────────────────────
# Built-in descriptions, keywords, and categories.
# Priority: built-in desc > --help summary > "External CLI: <name>"

KNOWN_CLI_KB = {
    # ── data processing ──
    "jq": {
        "desc": "Lightweight command-line JSON processor — filter, transform, and query JSON data",
        "keywords": ["json", "filter", "transform", "query", "parse", "extract", "select", "map", "reduce"],
        "category": "data-processing",
    },
    "yq": {
        "desc": "YAML/JSON/XML processor — jq wrapper for YAML with similar syntax",
        "keywords": ["yaml", "json", "xml", "filter", "transform", "query", "parse", "convert"],
        "category": "data-processing",
    },
    "sed": {
        "desc": "Stream editor for filtering and transforming text",
        "keywords": ["text", "filter", "replace", "substitute", "transform", "stream", "edit"],
        "category": "text-processing",
    },
    "awk": {
        "desc": "Pattern scanning and text processing language",
        "keywords": ["text", "pattern", "scan", "column", "field", "parse", "report", "transform"],
        "category": "text-processing",
    },
    "grep": {
        "desc": "Print lines matching a pattern — search text with regex",
        "keywords": ["search", "text", "regex", "pattern", "match", "find", "grep", "filter"],
        "category": "text-processing",
    },
    "rg": {
        "desc": "ripgrep — recursively search directories for regex patterns (fast grep alternative)",
        "keywords": ["search", "text", "regex", "pattern", "match", "find", "grep", "ripgrep", "recursive"],
        "category": "text-processing",
    },
    "fd": {
        "desc": "Simple, fast file search — find entries in the filesystem (find alternative)",
        "keywords": ["search", "file", "find", "locate", "filesystem", "directory"],
        "category": "file-management",
    },
    "find": {
        "desc": "Search for files in a directory hierarchy",
        "keywords": ["search", "file", "find", "locate", "filesystem", "directory", "recursive"],
        "category": "file-management",
    },
    "xargs": {
        "desc": "Build and execute command lines from standard input",
        "keywords": ["pipe", "batch", "execute", "argument", "stdin", "parallel"],
        "category": "text-processing",
    },
    "wc": {
        "desc": "Print newline, word, and byte counts for each file",
        "keywords": ["count", "lines", "words", "bytes", "file", "statistics"],
        "category": "text-processing",
    },
    "sort": {
        "desc": "Sort lines of text files",
        "keywords": ["sort", "order", "lines", "text", "alphabetical", "numeric"],
        "category": "text-processing",
    },
    "uniq": {
        "desc": "Report or omit repeated lines",
        "keywords": ["unique", "duplicate", "lines", "text", "count", "filter"],
        "category": "text-processing",
    },
    "cut": {
        "desc": "Remove sections from each line of files — extract columns",
        "keywords": ["columns", "fields", "delimiter", "extract", "text", "csv"],
        "category": "text-processing",
    },

    # ── version control ──
    "git": {
        "desc": "Fast, scalable, distributed revision control system",
        "keywords": ["version", "control", "commit", "branch", "merge", "clone", "push", "pull", "diff"],
        "category": "version-control",
    },
    "gh": {
        "desc": "GitHub CLI — manage repositories, PRs, issues from the terminal",
        "keywords": ["github", "pr", "pull request", "issue", "repo", "repository", "release", "gist", "codespace"],
        "category": "version-control",
    },

    # ── containers ──
    "docker": {
        "desc": "Container platform — build, run, and manage containers",
        "keywords": ["container", "image", "docker", "build", "run", "compose", "deploy", "registry"],
        "category": "containers",
    },
    "kubectl": {
        "desc": "Kubernetes CLI — deploy and manage containerized applications on clusters",
        "keywords": ["kubernetes", "k8s", "cluster", "deploy", "pod", "service", "container", "orchestration"],
        "category": "containers",
    },
    "helm": {
        "desc": "Kubernetes package manager — install and manage Helm charts",
        "keywords": ["kubernetes", "k8s", "chart", "package", "deploy", "install", "template"],
        "category": "containers",
    },

    # ── networking ──
    "curl": {
        "desc": "Transfer data from or to a server — HTTP/HTTPS/FTP/Gopher client",
        "keywords": ["http", "https", "download", "api", "request", "rest", "web", "url", "ftp", "post", "get"],
        "category": "networking",
    },
    "wget": {
        "desc": "Non-interactive network downloader — retrieve files via HTTP/HTTPS/FTP",
        "keywords": ["download", "http", "https", "ftp", "mirror", "recursive", "web", "file"],
        "category": "networking",
    },
    "ssh": {
        "desc": "OpenSSH remote login client — securely connect to remote machines",
        "keywords": ["ssh", "remote", "login", "shell", "secure", "tunnel", "connect", "key"],
        "category": "networking",
    },
    "scp": {
        "desc": "Secure copy — transfer files between hosts over SSH",
        "keywords": ["copy", "transfer", "remote", "secure", "file", "ssh"],
        "category": "networking",
    },
    "rsync": {
        "desc": "Fast, versatile file copying tool — sync directories locally and remotely",
        "keywords": ["sync", "copy", "backup", "mirror", "transfer", "remote", "incremental"],
        "category": "networking",
    },
    "ping": {
        "desc": "Send ICMP ECHO_REQUEST to test network connectivity",
        "keywords": ["network", "connectivity", "latency", "test", "ping", "icmp"],
        "category": "networking",
    },
    "dig": {
        "desc": "DNS lookup utility — query DNS name servers",
        "keywords": ["dns", "domain", "lookup", "query", "nameserver", "resolve", "record"],
        "category": "networking",
    },
    "ss": {
        "desc": "Socket statistics — dump socket information (netstat replacement)",
        "keywords": ["socket", "network", "port", "connection", "tcp", "udp", "listen"],
        "category": "networking",
    },
    "ip": {
        "desc": "Show/manipulate routing, devices, policy routing, and tunnels",
        "keywords": ["network", "route", "interface", "address", "tunnel", "link", "ip"],
        "category": "networking",
    },

    # ── media ──
    "ffmpeg": {
        "desc": "Complete solution for recording, converting, and streaming audio/video",
        "keywords": ["video", "audio", "convert", "encode", "decode", "media", "stream", "compress", "transcode"],
        "category": "media",
    },
    "convert": {
        "desc": "ImageMagick — convert between image formats, resize, apply effects",
        "keywords": ["image", "convert", "resize", "format", "png", "jpg", "gif", "crop", "rotate"],
        "category": "media",
    },

    # ── languages / runtimes ──
    "python3": {
        "desc": "Python 3 interpreter and scripting language",
        "keywords": ["python", "script", "programming", "language", "interpreter", "run"],
        "category": "languages",
    },
    "node": {
        "desc": "Node.js JavaScript runtime — run JavaScript outside the browser",
        "keywords": ["javascript", "js", "node", "runtime", "server", "script", "npm"],
        "category": "languages",
    },
    "npm": {
        "desc": "Node.js package manager — install and manage JavaScript packages",
        "keywords": ["package", "install", "node", "javascript", "dependency", "module", "registry"],
        "category": "languages",
    },
    "pnpm": {
        "desc": "Fast, disk-space efficient package manager for Node.js",
        "keywords": ["package", "install", "node", "javascript", "dependency", "fast"],
        "category": "languages",
    },
    "yarn": {
        "desc": "Fast, reliable, and secure dependency management for JavaScript",
        "keywords": ["package", "install", "node", "javascript", "dependency", "yarn"],
        "category": "languages",
    },
    "bun": {
        "desc": "All-in-one JavaScript runtime — bundler, test runner, package manager",
        "keywords": ["javascript", "runtime", "bundler", "test", "package", "fast"],
        "category": "languages",
    },
    "cargo": {
        "desc": "Rust package manager and build tool",
        "keywords": ["rust", "package", "build", "compile", "dependency", "project"],
        "category": "languages",
    },
    "go": {
        "desc": "Go programming language — compile, build, and run Go programs",
        "keywords": ["go", "golang", "compile", "build", "run", "format", "module"],
        "category": "languages",
    },
    "rustc": {
        "desc": "Rust compiler — compile Rust source code",
        "keywords": ["rust", "compile", "build", "language", "binary"],
        "category": "languages",
    },
    "make": {
        "desc": "GNU make — build automation tool",
        "keywords": ["build", "compile", "automation", "makefile", "target", "dependency"],
        "category": "build",
    },
    "cmake": {
        "desc": "Cross-platform build system generator",
        "keywords": ["build", "compile", "cmake", "makefile", "project", "configure"],
        "category": "build",
    },
    "gcc": {
        "desc": "GNU C compiler — compile C programs",
        "keywords": ["c", "compile", "build", "gcc", "linker", "binary"],
        "category": "build",
    },

    # ── databases ──
    "sqlite3": {
        "desc": "SQLite CLI — manage SQLite databases from the command line",
        "keywords": ["sql", "database", "sqlite", "query", "table", "select", "insert", "db"],
        "category": "databases",
    },
    "psql": {
        "desc": "PostgreSQL interactive terminal — query and manage PostgreSQL databases",
        "keywords": ["sql", "database", "postgresql", "postgres", "query", "table", "select", "psql"],
        "category": "databases",
    },

    # ── cloud ──
    "aws": {
        "desc": "AWS CLI — manage Amazon Web Services from the command line",
        "keywords": ["aws", "amazon", "cloud", "s3", "ec2", "lambda", "iam", "deploy"],
        "category": "cloud",
    },
    "gcloud": {
        "desc": "Google Cloud CLI — manage Google Cloud Platform resources",
        "keywords": ["google", "cloud", "gcp", "compute", "storage", "deploy", "iam"],
        "category": "cloud",
    },
    "az": {
        "desc": "Azure CLI — manage Microsoft Azure resources",
        "keywords": ["azure", "microsoft", "cloud", "vm", "storage", "deploy", "resource"],
        "category": "cloud",
    },
    "terraform": {
        "desc": "Infrastructure as Code — define and provision cloud infrastructure",
        "keywords": ["infrastructure", "iac", "cloud", "provision", "deploy", "state", "plan", "apply"],
        "category": "cloud",
    },

    # ── system ──
    "systemctl": {
        "desc": "Control the systemd system and service manager",
        "keywords": ["systemd", "service", "daemon", "start", "stop", "restart", "status", "enable"],
        "category": "system",
    },
    "journalctl": {
        "desc": "Query the systemd journal — view and filter logs",
        "keywords": ["log", "journal", "systemd", "debug", "error", "service", "boot"],
        "category": "system",
    },
    "htop": {
        "desc": "Interactive process viewer — monitor system resources",
        "keywords": ["process", "cpu", "memory", "monitor", "system", "resource", "interactive"],
        "category": "system",
    },
    "ncdu": {
        "desc": "NCurses Disk Usage — interactive disk usage analyzer",
        "keywords": ["disk", "usage", "space", "file", "directory", "size", "interactive"],
        "category": "system",
    },

    # ── compression / archive ──
    "tar": {
        "desc": "Tape archiver — create and extract archive files",
        "keywords": ["archive", "compress", "extract", "tar", "gz", "backup", "bundle"],
        "category": "archives",
    },
    "gzip": {
        "desc": "Compress or decompress files using Lempel-Ziv coding",
        "keywords": ["compress", "decompress", "gz", "file", "zip"],
        "category": "archives",
    },
    "unzip": {
        "desc": "List, test, and extract compressed files in a ZIP archive",
        "keywords": ["unzip", "extract", "archive", "zip", "decompress"],
        "category": "archives",
    },
    "zip": {
        "desc": "Package and compress files into a ZIP archive",
        "keywords": ["zip", "compress", "archive", "package", "bundle"],
        "category": "archives",
    },

    # ── other tools ──
    "fzf": {
        "desc": "Command-line fuzzy finder — filter lists interactively",
        "keywords": ["fuzzy", "find", "filter", "interactive", "search", "select", "picker", "menu"],
        "category": "interactive",
    },
    "bat": {
        "desc": "cat clone with syntax highlighting and Git integration",
        "keywords": ["view", "cat", "syntax", "highlight", "file", "preview", "pager"],
        "category": "file-management",
    },
    "eza": {
        "desc": "Modern replacement for ls — list files with colors and icons",
        "keywords": ["list", "directory", "file", "ls", "tree", "color"],
        "category": "file-management",
    },
    "code": {
        "desc": "Visual Studio Code editor — open files, folders, and manage extensions",
        "keywords": ["editor", "code", "vscode", "ide", "file", "diff", "extension"],
        "category": "editors",
    },
    "mihomo": {
        "desc": "Clash meta kernel — proxy and network routing (official skill exists)",
        "keywords": ["proxy", "mihomo", "clash", "vpn", "node", "routing", "network", "switch"],
        "category": "networking",
    },
    "clang": {
        "desc": "C language family compiler frontend — compile C/C++/Objective-C",
        "keywords": ["compiler", "c", "c++", "objc", "clang", "build", "compile"],
        "category": "development",
    },
    "clangd": {
        "desc": "Clang Language Server — IDE features for C/C++ (auto-complete, goto-def, diagnostics)",
        "keywords": ["lsp", "language server", "c", "c++", "ide", "autocomplete", "diagnostics", "clangd"],
        "category": "development",
    },
}

# Common shell/Unix utilities to skip during PATH scanning
UNIX_BASICS = {
    "[", "alias", "apt", "apt-get", "arch", "bash", "bg", "bind", "builtin",
    "bunzip2", "bzcat", "bzip2", "cal", "case", "cat", "cd", "chgrp",
    "chmod", "chown", "clear", "cmp", "comm", "command", "compgen", "cp",
    "cpio", "csplit", "cut", "dash", "date", "dd", "declare", "df", "diff",
    "dir", "dircolors", "dirname", "dirs", "dmidecode", "dmesg", "done",
    "dpkg", "du", "echo", "ed", "egrep", "elif", "else", "enable", "env",
    "eval", "exec", "exit", "expand", "export", "expr", "factor", "false",
    "fc", "fg", "fgrep", "fi", "file", "findmnt", "fmt", "fold", "for",
    "free", "function", "getopt", "getopts", "groups", "gunzip", "gzip",
    "hash", "head", "history", "hostid", "hostname", "id", "if", "info",
    "install", "jobs", "join", "kill", "ld", "ldd", "less", "let", "link",
    "ln", "local", "locale", "logger", "login", "logname", "logout", "lp",
    "ls", "lscpu", "lsblk", "lsof", "man", "mapfile", "md5sum", "mkdir",
    "mkfifo", "mknod", "mktemp", "more", "mount", "mpstat", "mv", "namei",
    "newgrp", "nice", "nl", "nohup", "nproc", "od", "paste", "pip", "pip3",
    "popd", "pr", "printenv", "printf", "ps", "pushd", "pwd", "python",
    "read", "readarray", "readlink", "realpath", "rename", "renice", "rev",
    "rm", "rmdir", "run-parts", "sdiff", "select", "seq", "set", "sh",
    "sha1sum", "sha256sum", "shift", "shopt", "shred", "shuf", "sleep",
    "sort", "source", "split", "stat", "stdbuf", "strings", "strip", "stty",
    "su", "sudo", "sum", "suspend", "sync", "tac", "tail", "tee", "test",
    "time", "timeout", "times", "touch", "tput", "tr", "trap", "true",
    "truncate", "tset", "tsort", "tty", "type", "typeset", "ulimit",
    "umask", "umount", "unalias", "uname", "unexpand", "uniq", "unlink",
    "unset", "until", "updatedb", "uptime", "users", "vi", "vim", "wait",
    "wall", "watch", "w", "whatis", "whereis", "which", "while", "who",
    "whoami", "write", "xdg-open", "yes", "zcat", "zless", "zmore",
}

# Name patterns to skip during PATH scan (glob). Applied automatically with --scan.
_SYSTEM_NOISE_PATTERNS = [
    "x86_64-*", "i386*", "i686*", "arm-*", "aarch64-*", "powerpc*",
    "dpkg-*", "deb-*", "dh_*",
    "pbm*", "pgm*", "pnm*", "ppm*", "pnmt*", "pnmd*", "pnms*",
    "pam*", "ybm*", "bmpt*", "anytopnm", "bmtoa", "giftopnm",
    "jpegtopnm", "pngtopnm", "pnmto*", "pnm-*",
    "*-cc-*", "gcc-*", "g++-*", "c++-*", "cpp-*",
    "clang-*", "clang++-*", "llvm-*",
    "*-config", "*-setup",
    "systemd-*", "busctl*",
    "x-*", "xsession*", "xset*", "xvfb*", "xgamma",
    "xhost", "xinput*", "xkill", "xmodmap", "xrdb", "xrefresh", "xsetroot",
    "man-recode", "man2*", "pod2*", "perldoc*",
    "ptar*", "ptargrep", "ptardiff", "perl*", "pl2*", "prove",
    "avahi-*", "dbus-*", "eject", "getent", "gsettings*", "gvfs-*",
    "hwclock", "ispell*", "locale", "logname", "logger",
    "md5sum*", "ntfs-*", "os-prober", "paperconf*", "pbmt*",
    "pkexec", "pldd", "policy-*", "prename", "ptx", "pwdx",
    "rename.ul", "rev", "rotatelogs", "rtmon", "runcon", "runuser",
    "script", "scriptreplay", "sensible-*", "setsid",
    "sha1*", "sha256*", "sha384*", "sha512*", "shred",
    "skill", "slabtop", "snice", "splain",
    "ss-local", "ss-redir", "ss-server",
    "tabs", "taskset", "tempfile", "tic", "tload",
    "tzselect", "unlink26", "unshare",
    "update-*", "utmp*", "vmstat", "volname",
    "zdump", "zegrep", "zfgrep", "zic",
    "alsabat", "alsaloop", "alsamixer", "alsatplg", "alsaucm",
    "aplay", "arecord", "amidi", "aplaymidi", "aseqdump",
    "aseqnet", "iecset", "speaker-test",
    "animate-im*", "compare-im*", "composite-im*", "conjure-im*",
    "convert-im*", "display-im*", "identify-im*", "import-im*",
    "mogrify-im*", "montage-im*", "stream-im*",
    "get-edid", "getwebcam", "parse-edid",
    "setpci", "setxkbmap", "showconsolefont",
    "spice-vdagent", "spice-vdagentd",
    "python*-config", "python*.*-config",
]

# Flattened set of known binary names (for quick lookup in discover)
_KNOWN_BINARIES = set(KNOWN_CLI_KB.keys())


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

def _fetch_help_text(binary, subcommand=None, light=False):
    """Get help text trying --help, -h, help, man, bare invocation.

    light=True: only --help/-h with a short timeout, and NO man / bare-invocation
    fallback. The bare-invocation fallback launches the tool with no args, which
    hangs on TUIs/REPLs — fine for a one-off lookup, fatal for bulk scanning.
    """
    if subcommand:
        attempts = [
            [binary, subcommand, "-h"],
            [binary, subcommand, "--help"],
            [binary, "help", subcommand],
        ]
    else:
        attempts = [[binary, "--help"], [binary, "-h"]]
        if not light:
            attempts.append([binary, "help"])

    timeout = 4 if light else 15
    for cmd in attempts:
        code, out, err = _run(cmd, timeout=timeout)
        output = (out + err).strip()
        if len(output) > 80:
            return output

    if light:
        return ""  # skip the hang-prone fallbacks

    # man page fallback
    code, out, err = _run(["man", binary], timeout=10)
    if len(out.strip()) > 80:
        return out.strip()[:16384]

    # bare invocation
    code, out, err = _run([binary], timeout=10)
    output = (out + err).strip()
    return output if output else ""


def _fetch_version(binary):
    """Extract version from --version output.

    Handles: "git version 2.17.1", "gh version 2.92.0",
    "curl 7.58.0", "v22.14.0", "Python 3.6.9", "mihomo-cli v2.8.1"
    """
    try:
        code, out, err = _run([binary, "--version"], timeout=5)
        output = (out + err).strip()
        if not output:
            code, out, err = _run([binary, "-V"], timeout=5)
            output = (out + err).strip()
        if output:
            m = re.search(r'\d+\.\d+(?:\.\d+)?(?:[a-z]\d*)?', output)
            if m:
                return m.group(0)
    except Exception:
        pass
    return None


# ── P1: Smart summary extraction ────────────────────────────────

def _extract_summary(text):
    """Extract a one-line tool description from --help output.

    Strategy (first to succeed wins):
      1. Find the NAME / DESCRIPTION section heading and grab the next line
      2. Find the first sentence after the usage block
      3. Find the first substantial non-flag line
    Returns None if nothing useful found.
    """
    if not text or len(text) < 20:
        return None

    lines = [l.strip() for l in text.split("\n")]

    # Strategy 1: NAME or DESCRIPTION section
    in_target = False
    for i, line in enumerate(lines):
        lo = line.lower().rstrip(":")
        if lo in ("name", "description", "overview"):
            in_target = True
            continue
        if in_target and len(line) > 15 and not line.startswith("-"):
            # Grab up to the next blank or heading
            parts = []
            for j in range(i, min(i + 8, len(lines))):
                l2 = lines[j].strip()
                if not l2 or l2.endswith(":") or l2.startswith("-"):
                    break
                parts.append(l2)
            if parts:
                return " ".join(parts)[:300]
            return line[:200]
        if in_target and (line == "" or line.startswith("-")):
            continue

    # Strategy 2: first sentence-like line after skipping usage/options blurb
    for i, line in enumerate(lines):
        if len(line) < 15:
            continue
        lo = line.lower()
        # Skip boilerplate
        if any(lo.startswith(w) for w in ("usage", "用法", "使い方", "usage:", "用法:", "使い方:")):
            continue
        if lo.startswith("-") and ("--" in line or "-" in line[:3]):
            continue
        # Look for a substantive line
        if re.match(r'^[A-Z]', line) and len(line) > 20:
            # Stop at next blank or flag line
            return line[:300]

    # Strategy 3: any substantial non-flag line
    for line in lines:
        if len(line) > 20 and not line.startswith("-") and not line.startswith("#"):
            return line[:200]

    return None


def _clean_help_raw(text):
    """Prepare help text for LLM consumption.

    - Strip version/copyright headers
    - Remove excessive blank lines
    - Keep first 5000 chars (the useful part is always at the top)
    """
    lines = text.split("\n")
    cleaned = []
    skip_header = True
    for line in lines:
        s = line.strip()
        # Skip version/copyright noise at the top
        if skip_header:
            if any(w in s.lower() for w in ("version", "copyright", "license",
                   "all rights reserved", "maintainer", "built on", "contributors")):
                continue
            if s and len(s) < 80 and not s.startswith("-"):
                skip_header = False
        cleaned.append(line)
    result = "\n".join(cleaned).strip()
    # Deduplicate blank lines
    import re as _re
    result = _re.sub(r'\n{3,}', '\n\n', result)
    return result[:5000]


def _format_commands_text(parsed_subs):
    """Build a compact command summary for LLM consumption."""
    if not parsed_subs:
        return ""
    lines = []
    for s in parsed_subs[:20]:
        name = s["name"]
        desc = s.get("desc", "")
        if desc:
            lines.append("{} — {}".format(name, desc))
        else:
            lines.append(name)
    return "\n".join(lines)


def _format_options_text(options):
    """Build a compact options summary for LLM consumption."""
    if not options:
        return ""
    lines = []
    for o in options[:15]:
        flag = o["flag"]
        aliases = ", ".join(o.get("aliases", []))
        label = "{} ({})".format(flag, aliases) if aliases else flag
        value = " <{}>".format(o["value"]) if o.get("value") else ""
        desc = o.get("desc", "")
        lines.append("{}{} — {}".format(label, value, desc))
    return "\n".join(lines)


def _extract_help(binary, light=False):
    """Extract structured help: usage, subcommands with options, global options.

    light=True skips the per-subcommand drill-down (and its many subprocess
    calls) — used for bulk scanning where speed and not-hanging matter. The
    top-level commands_text is still populated from the main --help.
    """
    text = _fetch_help_text(binary, light=light)
    if not text:
        return {"binary": binary, "help_raw": "{} — help unavailable".format(binary)}

    parsed_subs = _parse_subcommands(text)
    parsed_opts = _parse_options(text)

    result = {
        "binary": binary,
        "version": _fetch_version(binary),
        "help_raw": _clean_help_raw(text),
        "usage": _extract_usage(text),
        "summary": _extract_summary(text),
        "commands_text": _format_commands_text(parsed_subs),
        "options_text": _format_options_text(parsed_opts),
        "subcommands": {},
        "global_options": [],
    }

    if light:
        return result

    top_subs = parsed_subs[:12]

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


# ── P3: Quality scoring / noise filtering ─────────────────────

_NOISE_PATTERNS = [
    # Error from dynamic linker / missing libraries
    r'error while loading shared libraries',
    r'error while loading',
    # Node.js / process errors
    r'error:\s',
    r'eaddrinuse',
    r'econnrefused',
    r'enoent',
    r'module_not_found',
    r'cannot find module',
    # Shell/exec errors
    r'command not found',
    r'no such file or directory',
    r'permission denied',
    r'syntax error',
    # Pure error stubs
    r'^/.*\berror[:\s]',
]

def _is_noise_help(help_raw):
    """Returns True if the help output looks like an error, not real help."""
    if not help_raw or len(help_raw) < 50:
        return True
    # If the entire output is just usage (no description, no commands, no options),
    # it's likely not a useful CLI tool to register.
    lower = help_raw.lower()
    for pat in _NOISE_PATTERNS:
        if re.search(pat, lower):
            return True
    return False


def _score_tool_quality(result):
    """Score extracted help data 0-10. Higher = more useful to register."""
    score = 0.0
    summary = result.get("summary", "") or ""
    subcommands = result.get("subcommands", {})
    options_text = result.get("options_text", "") or ""
    usage = result.get("usage", "") or ""
    help_raw = result.get("help_raw", "")
    commands_text = result.get("commands_text", "") or ""

    # Has meaningful summary (not just usage line repeated)
    if summary and len(summary) > 20 and summary != usage.strip():
        score += 3.0
    elif summary and len(summary) > 10:
        score += 1.5

    # Has subcommands → interactive CLI tool. Count the parsed top-level
    # commands too, so a light extract (no drill-down) isn't penalised.
    cmd_lines = [l for l in commands_text.splitlines() if l.strip()]
    n_sub = max(len(subcommands), len(cmd_lines))
    if n_sub > 1:
        score += 3.0
    elif n_sub == 1:
        score += 1.5

    # Has structured options → useful flag surface
    if options_text and len(options_text) > 40:
        score += 2.0
    elif options_text and len(options_text) > 10:
        score += 1.0

    # Length of help_raw indicates documentation richness
    if help_raw and len(help_raw) > 500:
        score += 1.5
    elif help_raw and len(help_raw) > 100:
        score += 0.5

    # Commands_text shows the tool has structured subcommands
    if commands_text and len(commands_text) > 100:
        score += 0.5

    return score


# Quality threshold for filtered scan (default discover)
_MIN_QUALITY_SCORE = 3.0


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


# ── P2: Keyword index ───────────────────────────────────────────

def _build_keyword_index():
    """Build a reverse index: keyword → [tool names].

    Sources: built-in KNOWN_CLI_KB keywords, then fallback to description tokens.
    Stored as REGISTRY_DIR/.keywords.json.
    """
    index = {}

    # From knowledge base
    for name, kb in KNOWN_CLI_KB.items():
        for kw in kb.get("keywords", []):
            k = kw.lower()
            if k not in index:
                index[k] = []
            if name not in index[k]:
                index[k].append(name)

    # Supplement: extract keywords from registered tool descriptions
    for entry_path in sorted(REGISTRY_DIR.glob("*.json")):
        name = entry_path.stem
        if name.startswith("."):
            continue
        try:
            d = json.loads(entry_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        desc = d.get("description", "")
        if not desc or desc.startswith("External CLI:"):
            continue
        # Tokenize description for additional keywords
        tokens = set(re.findall(r'[a-z0-9]{3,}', desc.lower()))
        noise = {"the", "and", "for", "with", "from", "into", "that", "this",
                 "tool", "command", "line", "cli", "external", "file"}
        for t in tokens - noise:
            if t not in index:
                index[t] = []
            if name not in index[t]:
                index[t].append(name)

    return index


def _save_keyword_index():
    """Save the keyword index to disk."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    index = _build_keyword_index()
    KEYWORD_INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(index)


# ── commands ─────────────────────────────────────────────────────

def _resolve_description(name, help_text):
    """Resolve description with priority: KB > --help summary > fallback."""
    # P0: Built-in knowledge base
    kb = KNOWN_CLI_KB.get(name)
    if kb and kb.get("desc"):
        return kb["desc"]

    # P1: Smart extraction from --help
    summary = _extract_summary(help_text) if help_text else None
    if summary:
        return summary

    # Fallback
    return "External CLI: {}".format(name)


def _resolve_keywords(name):
    """Get keywords for a tool. Returns empty list if not in KB."""
    kb = KNOWN_CLI_KB.get(name)
    if kb:
        return kb.get("keywords", [])
    return []


def cmd_register(args):
    name = args.cli
    binary = args.binary or name
    desc = args.desc or ""

    if not args.force and not _whereis(binary):
        print("Warning: {} not found on PATH. Use --force to register anyway.".format(binary))

    official = _find_official_skill(name)
    info = _extract_help(binary, light=getattr(args, "light", False))

    # P0+P1: smart description resolution
    description = desc or _resolve_description(name, info.get("help_raw", ""))

    # P0: keywords from knowledge base
    keywords = _resolve_keywords(name)

    entry = {
        "name": name,
        "binary": binary,
        "description": description,
        "official_skill": official,
        "registered_at": datetime.now().isoformat(),
        "keywords": keywords,
        "auto_discovered": info,
    }
    if getattr(args, "novel", False):
        entry["surface"] = True

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    path = REGISTRY_DIR / "{}.json".format(name)
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Registered: {} -> {}".format(name, path))
    print("   {}".format(description[:80]))
    if official:
        print("   Official skill: {} (takes priority)".format(official))
    subs = info.get("subcommands", {})
    opts = info.get("global_options", [])
    print("   {} subcommands, {} options, {} keywords".format(
        len(subs), len(opts), len(keywords)))


def cmd_list(args):
    entries = [e for e in sorted(REGISTRY_DIR.glob("*.json")) if not e.name.startswith(".")]
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
                "keywords": d.get("keywords", []),
            }
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        header = "{:<18s} {:<13s} {:<8s} {:>4s} {:>4s} {:>3s}  {}".format(
            "NAME", "BINARY", "OFFICIAL", "SUBS", "OPTS", "KW", "DESCRIPTION")
        print(header)
        print("-" * 90)
        for e in entries:
            d = json.loads(e.read_text(encoding="utf-8"))
            official = "yes" if d.get("official_skill") else "-"
            ad = d.get("auto_discovered", {})
            subs = len(ad.get("subcommands", {}))
            opts = len(ad.get("global_options", []))
            kw_cnt = len(d.get("keywords", []))
            print("{:<18s} {:<13s} {:<8s} {:>4d} {:>4d} {:>3d}  {}".format(
                d["name"], d.get("binary", d["name"]),
                official, subs, opts, kw_cnt, d.get("description", "")[:35]))


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
    ad = d.get("auto_discovered", {})
    if ad.get("version"):
        print("Registered version: {}".format(ad["version"]))
        print("Official Skill: {} (takes priority)".format(d["official_skill"]))
    keywords = d.get("keywords", [])
    if keywords:
        print("Keywords: {}".format(", ".join(keywords)))

    ad = d.get("auto_discovered", {})

    summary = ad.get("summary")
    if summary:
        print("\n## Help Summary")
        print(summary)

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


def cmd_search(args):
    """Search registered tools by keyword."""
    keywords = [kw.lower() for kw in args.keyword]

    # Try to load the keyword index
    index = {}
    if KEYWORD_INDEX_PATH.is_file():
        try:
            index = json.loads(KEYWORD_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Also check individual registry entries
    hits = {}  # name → set of matched keywords

    # Search index
    for kw in keywords:
        matches = index.get(kw, [])
        for name in matches:
            if name not in hits:
                hits[name] = set()
            hits[name].add(kw)

    # Search entries directly (covers tools registered after last index build)
    for entry_path in sorted(REGISTRY_DIR.glob("*.json")):
        name = entry_path.stem
        if name.startswith("."):
            continue
        try:
            d = json.loads(entry_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        # Check built-in keywords
        for kw in d.get("keywords", []):
            for qk in keywords:
                if qk in kw.lower():
                    if name not in hits:
                        hits[name] = set()
                    hits[name].add(qk)

        # Check description
        desc = d.get("description", "").lower()
        for qk in keywords:
            if qk in desc and name not in hits:
                hits[name] = set()
                hits[name].add(qk)

    if not hits:
        print("No tools found for: {}".format(", ".join(keywords)))
        print("Try: python3 cli-registry.py list")
        return

    # Sort by number of matched keywords (descending)
    sorted_hits = sorted(hits.items(), key=lambda x: len(x[1]), reverse=True)

    print("Search: {}".format(", ".join(keywords)))
    print("{:<18s} {:>4s}  {}".format("TOOL", "MATCH", "DESCRIPTION"))
    print("-" * 80)
    for name, matched in sorted_hits:
        entry_path = REGISTRY_DIR / "{}.json".format(name)
        desc = ""
        if entry_path.is_file():
            try:
                d = json.loads(entry_path.read_text(encoding="utf-8"))
                desc = d.get("description", "")[:55]
            except Exception:
                pass
        print("{:<18s} {:>4d}  {}".format(name, len(matched), desc))

    print("\n{} tools matched. Use 'lookup <name>' for details.".format(len(hits)))


def cmd_discover(args):
    count = 0
    skipped = 0
    use_filter = not getattr(args, 'no_filter', False) and not args.scan
    scan_names = None  # None = scan all, set = only these names

    if getattr(args, 'names', None):
        scan_names = set(n.strip() for n in args.names.split(",") if n.strip())
    elif getattr(args, 'kb', False):
        scan_names = _KNOWN_BINARIES

    # Exclude patterns (glob): skip matching names during scan.
    # When --scan, automatically include system noise patterns.
    exclude_pats = []
    if args.scan:
        exclude_pats.extend(_SYSTEM_NOISE_PATTERNS)
    if getattr(args, 'exclude', None):
        exclude_pats.extend(p.strip() for p in args.exclude.split(",") if p.strip())

    def _matches_exclude(name):
        for pat in exclude_pats:
            if fnmatch.fnmatch(name, pat):
                return True
        return False

    # Determine which PATH dirs to scan
    all_path_dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if Path(d).is_dir()]
    user_paths = {os.path.expanduser(p) for p in (
        "~/.local/bin", "~/.local/node/bin", "~/.npm-global/bin",
        "~/bin", "~/.nvm/current/bin", "~/.nix-profile/bin",
    )}
    # Always include /usr/local/bin for tools installed via make install / brew
    user_paths.add("/usr/local/bin")

    if args.scan or scan_names:
        scan_paths = all_path_dirs
    elif args.scan_path:
        scan_paths = [args.scan_path]
    else:
        scan_paths = [d for d in all_path_dirs if d in user_paths]

    # Phase 1: KB tools — scan ALL PATH, ALWAYS register (trusted, no quality check)
    for binary in sorted(_KNOWN_BINARIES):
        if scan_names and binary not in scan_names:
            continue
        if (REGISTRY_DIR / "{}.json".format(binary)).is_file():
            continue
        if _whereis(binary):
            print("Found: {} (KB)".format(binary))
            try:
                cmd_register(argparse.Namespace(
                    cli=binary, binary=binary, desc="", force=False))
                count += 1
            except Exception as exc:
                print("  failed ({})".format(exc))

    # Phase 2: Non-KB PATH scan (default=user paths, --scan=all)
    seen = set(_KNOWN_BINARIES) | {
        e.stem for e in REGISTRY_DIR.glob("*.json")
    }
    if scan_names:
        print("\nScanning PATH for: {} ...".format(", ".join(sorted(scan_names))))

    for path_dir in scan_paths:
        d = Path(path_dir)
        if not d.is_dir():
            continue
        try:
            for entry in d.iterdir():
                name = entry.name
                if name in seen or name in UNIX_BASICS:
                    continue
                if _matches_exclude(name):
                    continue
                if len(name) < 2 or len(name) > 30:
                    continue
                if not re.match(r'^[a-z][a-z0-9._-]+$', name):
                    continue
                if scan_names and name not in scan_names:
                    continue
                if not (entry.is_file() and os.access(str(entry), os.X_OK)):
                    continue
                seen.add(name)

                # Quality filter for non-KB tools
                if use_filter or (not args.scan and not scan_names):
                    result = _extract_help(str(entry))
                    if _is_noise_help(result.get("help_raw", "")):
                        skipped += 1
                        continue
                    if _score_tool_quality(result) < _MIN_QUALITY_SCORE:
                        skipped += 1
                        continue

                print("Found: {} ...".format(name), end=" ", flush=True)
                try:
                    cmd_register(argparse.Namespace(
                        cli=name, binary=str(entry), desc="", force=False))
                    count += 1
                except Exception as exc:
                    print("failed ({})".format(exc))
        except PermissionError:
            continue

    if use_filter and skipped > 0:
        print("\n  (filtered {} low-quality/noise tools)".format(skipped))

    # Phase 3: custom directory
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

    if count > 0:
        kw_count = _save_keyword_index()
        print("\nKeyword index: {} terms".format(kw_count))

    print("\nRegistered {} new CLI tools.".format(count))


def cmd_remove(args):
    path = REGISTRY_DIR / "{}.json".format(args.cli)
    if path.is_file():
        path.unlink()
        print("Removed: {}".format(args.cli))
        # Rebuild keyword index
        _save_keyword_index()
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


def _refresh_entry(name, entry):
    """Re-extract a tool's cached help while PRESERVING its curated
    description and surface flag (so an auto-refresh never wipes research)."""
    cmd_register(argparse.Namespace(
        cli=name, binary=entry.get("binary", name),
        desc=entry.get("description", ""), force=True,
        novel=bool(entry.get("surface"))))


def cmd_check_stale(args):
    """Find tools whose installed version differs from the registry.

    --novel : only check surfaced tools (cheap; for the daily hook pass)
    --daily : skip if already run today (date-marked)
    --update: re-register drifted tools, preserving curated desc + surface
    """
    if args.daily:
        marker = REGISTRY_DIR / ".last-stale"
        today = datetime.now().strftime("%Y-%m-%d")
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == today:
            return
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text(today, encoding="utf-8")

    stale, checked = [], 0
    for name, d in _iter_registry():
        if args.novel and not _is_novel(name, d):
            continue
        binary = d.get("binary", name)
        registered_ver = d.get("auto_discovered", {}).get("version")
        installed_ver = _fetch_version(binary)
        if installed_ver is None:
            continue
        checked += 1
        if registered_ver and installed_ver != registered_ver:
            stale.append((name, registered_ver, installed_ver, d))

    if args.update:
        for name, old, new, d in stale:
            _refresh_entry(name, d)
            print("updated: {} {} -> {}".format(name, old, new))  # parsed by the hook
        if stale:
            _save_keyword_index()
        return

    # report mode
    if not stale:
        print("All {} tools up to date.".format(checked))
        return
    print("{} stale (installed != registered):".format(len(stale)))
    for name, old, new, _ in stale:
        print("  {}: {} -> {}".format(name, old, new))
    print("\nDry run. Use --update to refresh.")

# ── Discovery surface (which tools the model likely doesn't know) ──

def _load_entry(name):
    p = REGISTRY_DIR / "{}.json".format(name)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _iter_registry():
    for p in sorted(REGISTRY_DIR.glob("*.json")):
        if p.stem.startswith("."):
            continue
        try:
            yield p.stem, json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue


def _is_novel(name, entry=None):
    """True for tools the base model likely does NOT know, worth surfacing.

    Sources are deliberately opt-in/curated — never inferred from mere absence
    in the KB, because a raw PATH scan registers lots of system noise:
      - KB entries flagged "novel" (AI-native tools cli-hub ships knowledge for)
      - registry entries flagged "surface" (user ran `register --novel` / `flag`)
    """
    if name in UNIX_BASICS:
        return False
    kb = KNOWN_CLI_KB.get(name)
    if kb and kb.get("novel"):
        return True
    if entry is None:
        entry = _load_entry(name)
    return bool(entry and entry.get("surface"))


def cmd_non_standard(args):
    """List installed tools the base model likely doesn't know (for discovery).

    Compact by design — meant to be injected into an agent's context so it
    knows these tools exist. Silent when there is nothing to surface.
    """
    rows = sorted((name, (entry.get("description") or "").strip())
                  for name, entry in _iter_registry() if _is_novel(name, entry))

    if args.format == "json":
        print(json.dumps([{"name": n, "description": d} for n, d in rows],
                         indent=2, ensure_ascii=False))
        return
    for name, desc in rows:
        print("{} — {}".format(name, desc) if desc else name)


def cmd_hint(args):
    """Compact one-tool usage hint for hook injection.

    Exits 1 (silent) unless the tool is registered AND novel, so we never
    spend context reminding the model about tools it already knows.
    """
    name = args.cli
    entry = _load_entry(name)
    if entry is None or (not args.force and not _is_novel(name, entry)):
        sys.exit(1)

    ad = entry.get("auto_discovered", {})
    lines = ["{} — {}".format(name, (entry.get("description") or "").strip())]
    usage = (ad.get("usage") or "").strip().split("\n")[0][:160]
    # Skip ASCII-art banners / decoration: keep only text-like usage lines.
    if usage and sum(c.isalnum() or c.isspace() for c in usage) / len(usage) > 0.6:
        lines.append("usage: {}".format(usage))
    commands = (ad.get("commands_text") or "").strip()
    if commands:
        cmds = [c.split(" — ")[0].strip() for c in commands.splitlines() if c.strip()]
        if cmds:
            lines.append("subcommands: {}".format(", ".join(cmds[:20])))
    skill = entry.get("skill") or {}
    if skill.get("installed"):
        v = " v{}".format(skill["version"]) if skill.get("version") else ""
        lines.append("→ has an official skill installed{} — prefer it: {}".format(v, skill.get("path", "")))
    elif skill.get("candidates"):
        hit = skill["candidates"][0]["hits"][0]
        lines.append("→ an installable skill may exist (unverified): {}".format(hit))
    elif entry.get("official_skill"):
        lines.append("(official skill: {})".format(entry["official_skill"]))
    print("\n".join(lines))


PATH_SEEN = REGISTRY_DIR / ".path-seen.json"


def _path_binaries():
    """name -> resolved path for executables on PATH (first match wins)."""
    found = {}
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = Path(d)
        if not p.is_dir():
            continue
        try:
            for e in p.iterdir():
                name = e.name
                if name in found or not re.match(r'^[a-z][a-z0-9._-]+$', name):
                    continue
                if e.is_file() and os.access(str(e), os.X_OK):
                    found[name] = str(e)
        except PermissionError:
            continue
    return found


def _under_home(path):
    """True if the binary lives under $HOME (i.e. user-installed, not system)."""
    try:
        return str(Path(path).resolve()).startswith(str(Path.home().resolve()) + os.sep)
    except Exception:
        return False


def cmd_autodiscover(args):
    """Incremental discovery for hooks: register only newly-appeared binaries,
    auto-surfacing the user-installed ones. Cheap on the common (no-change) path.

    A tool is auto-surfaced (flagged novel) when it is installed under $HOME,
    not in the built-in KB (so the model probably doesn't know it), and has a
    real description. System binaries (/usr/bin ...) are registered but never
    auto-surfaced. Override any guess with `flag <tool> [--off]`.
    """
    current = _path_binaries()
    names = sorted(current)

    prev = None
    if PATH_SEEN.is_file():
        try:
            prev = set(json.loads(PATH_SEEN.read_text(encoding="utf-8")))
        except Exception:
            prev = None

    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    PATH_SEEN.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")

    if getattr(args, "seed", False):
        new = [n for n in names if _under_home(current[n])]
        bulk = True
    elif prev is None:
        print("Baseline recorded ({} binaries on PATH).".format(len(names)))
        return
    else:
        new = [n for n in names if n not in prev]
        # A big batch (e.g. `pip install jupyter` adds ~20 console scripts) is a
        # weak signal — register but don't auto-surface, or the manifest floods.
        bulk = len(new) > 8

    if not new:
        if args.verbose:
            print("No new tools on PATH.")
        return

    registered, surfaced, suggested = 0, [], []
    seen_desc = set()
    deadline = time.monotonic() + 60  # bound the one-time seed; rest caught later
    for name in new:
        if time.monotonic() > deadline:
            break
        if name in UNIX_BASICS or (REGISTRY_DIR / "{}.json".format(name)).is_file():
            continue
        if any(fnmatch.fnmatch(name, pat) for pat in _SYSTEM_NOISE_PATTERNS):
            continue
        path = current[name]
        info = _extract_help(path, light=True)
        if _is_noise_help(info.get("help_raw", "")) or \
                _score_tool_quality(info) < _MIN_QUALITY_SCORE:
            continue
        summary = (info.get("summary") or "").strip().lower()
        candidate = _under_home(path) and name not in KNOWN_CLI_KB and len(summary) > 15
        dup = candidate and summary in seen_desc       # kills foo / foo-cli / foo3 triples
        surface = candidate and not bulk and not dup    # auto-surface only small, deliberate installs
        cmd_register(argparse.Namespace(
            cli=name, binary=path, desc="", force=False, novel=surface, light=True))
        registered += 1
        if candidate and not dup:
            seen_desc.add(summary)
            (surfaced if surface else suggested).append(name)

    if registered:
        _save_keyword_index()
    msg = "Auto-registered {} new tool(s)".format(registered)
    if surfaced:
        msg += "; surfaced: " + ", ".join(surfaced)
    if suggested:
        msg += "; candidates (flag <name> to surface): " + ", ".join(suggested[:30])
    print(msg)


def _skill_info(name):
    """Locate an installed official skill for a tool; parse light frontmatter."""
    path = _find_official_skill(name)
    if not path:
        return None
    info = {"path": path, "version": None}
    try:
        text = Path(path).read_text(encoding="utf-8")
        m = re.search(r'^---\s*(.*?)\s*---', text, re.S)
        fm = m.group(1) if m else text[:600]
        v = re.search(r'(?mi)^\s*version\s*:\s*(.+)$', fm)
        if v:
            info["version"] = v.group(1).strip().strip('"\'')
    except Exception:
        pass
    return info


# Provider-agnostic: only searchers whose binary is present get used. Never
# hardcode a single skill marketplace.
_SKILL_SEARCHERS = [
    ("clawhub", lambda n: ["clawhub", "search", n]),
    ("skills", lambda n: ["skills", "search", n]),
]


def cmd_skills_check(args):
    """Record, per tool, whether an official agent-skill is installed (and its
    version). With --search, also query any skill registries whose CLI is
    present. Honest scope: skills rarely declare CLI-version compatibility, so
    we record presence/version, NOT a CLI<->skill version match.
    """
    if args.daily:
        marker = REGISTRY_DIR / ".last-skills"
        today = datetime.now().strftime("%Y-%m-%d")
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == today:
            return
        REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
        marker.write_text(today, encoding="utf-8")

    targets = [args.cli] if args.cli else [n for n, e in _iter_registry() if _is_novel(n, e)]
    if not targets:
        print("No novel tools to check (flag one, or pass a name).")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    for name in targets:
        entry = _load_entry(name)
        if entry is None:
            print("{}: not registered".format(name))
            continue
        skill = _skill_info(name)
        rec = dict(entry.get("skill") or {})  # preserve prior candidates/announced
        rec["checked"] = today
        rec["installed"] = bool(skill)
        if skill:
            rec["path"] = skill["path"]
            rec["version"] = skill["version"]
            rec.pop("candidates", None)
            rec.pop("announced", None)
        elif args.search:
            candidates = []
            for binary, build in _SKILL_SEARCHERS:
                if not _whereis(binary):
                    continue
                _, out, _err = _run(build(name), timeout=20)
                hits = [l.strip() for l in (out or "").splitlines()
                        if name.lower() in l.lower()][:2]
                if hits:
                    candidates.append({"via": binary, "hits": hits})
            if candidates:
                rec["candidates"] = candidates
                rec.pop("announced", None)   # re-arm the one-time reminder
            else:
                rec.pop("candidates", None)
        entry["skill"] = rec
        (REGISTRY_DIR / "{}.json".format(name)).write_text(
            json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")

        if skill:
            v = " v{}".format(skill["version"]) if skill["version"] else ""
            print("{}: official skill INSTALLED{} — {}".format(name, v, skill["path"]))
        elif rec.get("candidates"):
            print("{}: installable skill — {}".format(name, "; ".join(
                "{}: {}".format(c["via"], c["hits"][0]) for c in rec["candidates"])))
        else:
            tip = "" if args.search else " (use --search to query skill registries)"
            print("{}: no official skill installed{}".format(name, tip))


def cmd_skill_pending(args):
    """List tools with an installable skill that is not installed and not yet
    announced, then mark them announced (so the user is reminded only once).

    Local + zero-network: it reads candidates recorded earlier by
    `skills-check --search` (which the user runs manually or via cron). Output
    is one `name<TAB>top-hit` line per tool, for the session hook to relay.
    """
    pending = []
    for name, entry in _iter_registry():
        skill = entry.get("skill") or {}
        cands = skill.get("candidates")
        if not cands or skill.get("installed") or skill.get("announced"):
            continue
        hits = cands[0].get("hits") or [name]
        pending.append((name, hits[0]))
        if not args.peek:
            skill["announced"] = True
            entry["skill"] = skill
            (REGISTRY_DIR / "{}.json".format(name)).write_text(
                json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")

    for name, hit in pending:
        print("{}\t{}".format(name, hit))


def cmd_flag(args):
    """Mark/unmark one or more registered tools as novel (surfaced)."""
    names = args.cli if isinstance(args.cli, list) else [args.cli]
    for name in names:
        entry = _load_entry(name)
        if entry is None:
            print("Not registered: {} (run: register {} first)".format(name, name))
            continue
        if args.off:
            entry.pop("surface", None)
        else:
            entry["surface"] = True
        (REGISTRY_DIR / "{}.json".format(name)).write_text(
            json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Surface flag {} for {}".format("OFF" if args.off else "ON", name))


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
    p.add_argument("--desc", help="Description (override auto-detection)")
    p.add_argument("--force", action="store_true",
                   help="Register even if binary not on PATH")
    p.add_argument("--novel", action="store_true",
                   help="Mark as a tool the model likely doesn't know (surface in discovery manifest)")

    p = sub.add_parser("list", help="List registered CLIs")
    p.add_argument("--format", default="table", choices=["table", "json"])

    p = sub.add_parser("lookup", help="Look up a CLI")
    p.add_argument("cli", help="CLI name")

    p = sub.add_parser("search", help="Search tools by keyword")
    p.add_argument("keyword", nargs="+", help="Keyword(s) to search for")

    p = sub.add_parser("discover", help="Auto-discover CLI binaries (user paths, filtered)")
    p.add_argument("--scan", action="store_true",
                   help="Full PATH scan: all directories, no quality filter")
    p.add_argument("--names", help="Comma-separated tool names to scan for (over PATH)")
    p.add_argument("--exclude", help="Comma-separated patterns to skip (glob). --scan auto-excludes system noise")
    p.add_argument("--kb", action="store_true",
                   help="Full PATH scan limited to knowledge-base tools (fast + safe)")
    p.add_argument("--scan-path", help="Extra directory to scan for executables")
    p.add_argument("--no-filter", action="store_true",
                   help="Disable quality filtering (register noise too)")

    p = sub.add_parser("check-stale", help="Check for tools with updated versions")
    p.add_argument("--update", action="store_true",
                   help="Refresh drifted tools (preserves curated desc + surface)")
    p.add_argument("--novel", action="store_true",
                   help="Only check surfaced/novel tools (cheap)")
    p.add_argument("--daily", action="store_true",
                   help="Skip if already run today (for the hook)")

    p = sub.add_parser("skills-check",
                       help="Record whether an official skill is installed for novel tools")
    p.add_argument("cli", nargs="?", help="Single tool (default: all novel tools)")
    p.add_argument("--search", action="store_true",
                   help="Also query installed skill-registry CLIs (clawhub/skills)")
    p.add_argument("--daily", action="store_true",
                   help="Skip if already run today (for the hook)")

    p = sub.add_parser("remove", help="Remove from registry")
    p.add_argument("cli", help="CLI name")

    p = sub.add_parser("help", help="Fetch live --help output")
    p.add_argument("cli", help="CLI name or binary")

    p = sub.add_parser("non-standard",
                       help="List installed tools the model likely doesn't know")
    p.add_argument("--format", default="text", choices=["text", "json"])

    p = sub.add_parser("autodiscover",
                       help="Incrementally register newly-appeared PATH tools (for hooks)")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--seed", action="store_true",
                   help="One-time: surface tools already installed under $HOME")

    p = sub.add_parser("hint", help="Compact usage hint for one novel tool (for hooks)")
    p.add_argument("cli", help="CLI name")
    p.add_argument("--force", action="store_true",
                   help="Emit even if the tool isn't flagged novel")

    p = sub.add_parser("flag", help="Mark registered tool(s) as novel (surface in manifest)")
    p.add_argument("cli", nargs="+", help="CLI name(s)")
    p.add_argument("--off", action="store_true", help="Unset the novel flag")

    p = sub.add_parser("skill-pending",
                       help="List (and mark announced) tools with an uninstalled skill, for the hook")
    p.add_argument("--peek", action="store_true",
                   help="List without marking announced")

    args = parser.parse_args()
    {
        "register": cmd_register,
        "list": cmd_list,
        "lookup": cmd_lookup,
        "search": cmd_search,
        "discover": cmd_discover,
        "remove": cmd_remove,
        "help": cmd_help_cli,
        "check-stale": cmd_check_stale,
        "non-standard": cmd_non_standard,
        "autodiscover": cmd_autodiscover,
        "skills-check": cmd_skills_check,
        "skill-pending": cmd_skill_pending,
        "hint": cmd_hint,
        "flag": cmd_flag,
    }[args.command](args)


if __name__ == "__main__":
    main()
