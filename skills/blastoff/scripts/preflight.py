#!/usr/bin/env python3
"""Check what the launcher needs before it installs anything. Changes nothing.

Prints one line per tool and exits 1 if a required one is missing.
"""
import re
import shutil
import subprocess
import sys

def _safe_console():
    """Windows consoles and piped output often cannot print every character. Never crash on that."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


_safe_console()

def version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", (out.stdout or "") + (out.stderr or ""))
        return tuple(int(x or 0) for x in m.groups()) if m else None
    except (OSError, subprocess.SubprocessError):
        return None


def find_python():
    """Sellbird needs Python 3.11+. Return (command, version) of the best one found."""
    best = None
    for name in ("python3.13", "python3.12", "python3.11", "python3", "python", "py"):
        path = shutil.which(name)
        if not path:
            continue
        v = version([path, "--version"])
        if v and (best is None or v > best[1]):
            best = (name, v)
    return best


def main():
    ok = True
    rows = []

    py = find_python()
    if py and py[1] >= (3, 11, 0):
        rows.append(("ok", "Python", f"{py[0]} is {'.'.join(map(str, py[1]))}", ""))
    else:
        ok = False
        found = f"found {'.'.join(map(str, py[1]))}" if py else "not found"
        rows.append(("MISSING", "Python 3.11+", found, "Sellbird needs 3.11 or newer. Install it from python.org or your package manager."))

    for name, cmd, need, why in (
        ("git", ["git", "--version"], None, "Needed to clone Sellbird."),
        ("Node.js 18+", ["node", "--version"], (18, 0, 0), "Needed for 'npx skills add' and the Postiz command-line tool."),
        ("npx", ["npx", "--version"], None, "Comes with Node.js."),
    ):
        exe = shutil.which(cmd[0])
        v = version([exe] + cmd[1:]) if exe else None
        if v and (need is None or v >= need):
            rows.append(("ok", name, ".".join(map(str, v)), ""))
        else:
            ok = False
            rows.append(("MISSING", name, "not found" if not v else ".".join(map(str, v)), why))

    claude = shutil.which("claude")
    if claude:
        rows.append(("ok", "Claude Code CLI", claude, ""))
    else:
        ok = False
        rows.append(("MISSING", "Claude Code CLI", "'claude' is not on PATH",
                     "Sellbird thinks by calling 'claude -p'. The VS Code extension alone is not enough: install the CLI and run 'claude login'."))

    postiz = shutil.which("postiz")
    rows.append(("ok" if postiz else "later", "Postiz CLI", postiz or "not installed yet", "" if postiz else "Installed in the social stage: npm install -g postiz"))

    for status, name, detail, hint in rows:
        print(f"[{status:^7}] {name:<16} {detail}")
        if hint:
            print(f"{'':10}{hint}")
    print("\nReady." if ok else "\nFix the MISSING items first, then run this again.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
