#!/usr/bin/env python3
"""Check what the launcher needs before it installs anything. Changes nothing.

Prints one line per tool and exits 1 if a required one is missing. Python 3.9 or 3.10 passes
with a 'later' note: only Sellbird (cold outbound) needs 3.11+. When paid ads are in the plan it
also notes whether claude-ads' installer will find CPython 3.11 or 3.12; that is never a failure,
because claude-ads can be installed without its Python helpers.
"""
import json
import os
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
    """Blastoff needs Python 3.9+, Sellbird 3.11+. Return (command, version) of the best one found."""
    best = None
    for name in ("python3.13", "python3.12", "python3.11", "python3", "python", "py"):
        path = shutil.which(name)
        if not path:
            continue
        v = version([path, "--version"])
        if v and (best is None or v > best[1]):
            best = (name, v)
    return best


def ads_planned():
    """True when the workspace's plan includes paid ads. No plan yet means not asked about yet."""
    try:
        st = json.loads(open(os.path.join(".launchpad", "state.json"), encoding="utf-8").read())
        return "ads" in (st.get("profile") or {}).get("channels", [])
    except (OSError, ValueError, AttributeError):
        return False


def ads_python_row():
    """claude-ads' installer uses 'python3' (install.sh) or 'python' (install.ps1) and accepts only 3.11 or 3.12."""
    name = "python" if os.name == "nt" else "python3"
    exe = shutil.which(name)
    v = version([exe, "--version"]) if exe else None
    if v and v[:2] in ((3, 11), (3, 12)):
        return ("ok", "claude-ads Python", f"{name} is {'.'.join(map(str, v))}", "")
    found = f"{name} is {'.'.join(map(str, v))}" if v else f"'{name}' not found"
    return ("later", "claude-ads Python", found,
            f"claude-ads' Python helpers need CPython 3.11 or 3.12 as '{name}'. Install 3.12, or install claude-ads "
            "with --no-deps (-NoDeps on Windows): skills only, without the landing-page fetch and PDF reports.")


def main():
    ok = True
    rows = []

    py = find_python()
    if py and py[1] >= (3, 11, 0):
        rows.append(("ok", "Python", f"{py[0]} is {'.'.join(map(str, py[1]))}", ""))
    elif py and py[1] >= (3, 9, 0):
        rows.append(("later", "Python 3.11+", f"{py[0]} is {'.'.join(map(str, py[1]))} (enough for everything else)",
                     "Only cold outbound (Sellbird) and claude-ads' Python helpers need 3.11 or newer. Install it from python.org or your package manager before that stage."))
    else:
        ok = False
        found = f"found {'.'.join(map(str, py[1]))}" if py else "not found"
        rows.append(("MISSING", "Python 3.9+", found, "Blastoff needs 3.9 or newer (3.11+ for Sellbird outbound). Install it from python.org or your package manager."))

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

    if ads_planned():
        rows.append(ads_python_row())

    for status, name, detail, hint in rows:
        print(f"[{status:^7}] {name:<16} {detail}")
        if hint:
            print(f"{'':10}{hint}")
    print("\nReady." if ok else "\nFix the MISSING items first, then run this again.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
