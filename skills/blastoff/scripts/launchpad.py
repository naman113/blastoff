#!/usr/bin/env python3
"""Launchpad tracker. Standard library only.

Run from the go-to-market workspace (the folder that holds .launchpad/).

  launchpad.py init --product "Name" [--site URL] [--repo PATH] [--hub URL]
  launchpad.py profile [--motion M] [--buyer B] [--channels C ...] [--have H ...]
                                        record the intake answers and build the tailored checklist;
                                        with no options, show the current plan
  launchpad.py set KEY VALUE            product | domain | site | booking_url | hub_url | product_repo
                                        (domain = the address the site will have; site = set once it is live)
  launchpad.py done STEP_ID [...]       mark steps done
  launchpad.py undo STEP_ID [...]
  launchpad.py status                   what is done, what is next, who does it
  launchpad.py guide                    (re)write LAUNCH_GUIDE.md from the current state
  launchpad.py sync                     build .launchpad/hub-sync.json for the hub's Sync box
  launchpad.py pull FILE                read a hub export (hub-data.json) back into the state
  launchpad.py check                    verify step ids match the hub page
  launchpad.py doctor                   what is installed and what is missing in this workspace
  launchpad.py seal                     record the state of every file before handing work to an agent
  launchpad.py seal --verify [--allow PATTERN ...]
                                        list what changed since; exit 1 if anything outside the
                                        allowed patterns (or anything in the product repo) changed
  launchpad.py agents [--default|--no-default] [--force]
                                        install the four agents into .claude/agents/;
                                        --default makes launch-coordinator the session agent here
"""
import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

def _safe_console():
    """Windows consoles and piped output often cannot print every character. Never crash on that."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


_safe_console()

SKILL = Path(__file__).resolve().parent.parent
STEPS_FILE = SKILL / "assets" / "steps.json"
HUB_FILE = SKILL / "assets" / "hub.html"
WORK = Path.cwd() / ".launchpad"
STATE = WORK / "state.json"
LEADS = WORK / "leads.json"
POSTS = WORK / "posts.json"
SYNC = WORK / "hub-sync.json"
GUIDE = Path.cwd() / "LAUNCH_GUIDE.md"

LEAD_STAGES = ["replied", "talking", "meeting", "proposal", "won", "lost"]
LEAD_SOURCES = ["Sellbird", "LinkedIn", "Instagram", "Website", "Referral", "Other"]
POST_STATUSES = ["Idea", "Drafted", "Scheduled", "Posted"]
POST_PLATFORMS = ["LinkedIn", "Instagram", "X", "Other"]
SETTABLE = ["product", "domain", "site", "booking_url", "hub_url", "product_repo"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def today():
    return dt.date.today().isoformat()


def stages():
    return json.loads(STEPS_FILE.read_text(encoding="utf-8"))["stages"]


def every_step():
    """All steps the skill knows, whether or not they are in this person's plan."""
    return [s for g in stages() for s in g["steps"]]


MOTIONS = ["self-serve", "sales-led"]
BUYERS = ["small", "large", "consumer"]
CHANNELS = ["site", "linkedin", "instagram", "x", "outbound"]
HAVES = ["domain", "website", "booking", "linkedin-page"]
SOCIAL = {"linkedin", "instagram", "x"}


def profile_tags(profile):
    if not profile:
        return None
    tags = {f"motion:{profile.get('motion')}", f"buyer:{profile.get('buyer')}"}
    tags |= {f"ch:{c}" for c in profile.get("channels", [])}
    tags |= {f"have:{h}" for h in profile.get("have", [])}
    if SOCIAL & set(profile.get("channels", [])):
        tags.add("ch:social")
    return tags


def in_plan(step, tags):
    if tags is None:          # no intake yet: everything is in the plan
        return True
    if step.get("if_any") and not (set(step["if_any"]) & tags):
        return False
    if step.get("unless_any") and (set(step["unless_any"]) & tags):
        return False
    return True


def _current_profile():
    return load(STATE, {}).get("profile") if STATE.exists() else None


def all_steps():
    """The steps in this person's plan."""
    tags = profile_tags(_current_profile())
    return [s for s in every_step() if in_plan(s, tags)]


def load(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{path} is not valid JSON: {e}")


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def state():
    if not STATE.exists():
        sys.exit("No .launchpad/state.json here. Run: launchpad.py init --product \"Name\"")
    return load(STATE, {})


def cmd_init(a):
    if STATE.exists() and not a.force:
        sys.exit(".launchpad/state.json already exists. Use 'set' to change values, or --force to start over.")
    st = {"product": a.product, "domain": "", "site": a.site or "", "booking_url": "", "hub_url": a.hub or "",
          "product_repo": a.repo or "", "created": today(), "done": {}}
    save(STATE, st)
    if not LEADS.exists():
        save(LEADS, [])
    if not POSTS.exists():
        save(POSTS, [])
    ignore = Path.cwd() / ".gitignore"
    lines = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
    for entry in ("tools/", ".launchpad/hub-sync.json", ".launchpad/leads.json", ".launchpad/prospects.csv", ".launchpad/seal.json"):
        if entry not in lines:
            lines.append(entry)
    ignore.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_guide(st)
    print(f"Started the tracker for {a.product}. Wrote LAUNCH_GUIDE.md.")


def cmd_profile(a):
    st = state()
    if not (a.motion or a.buyer or a.channels is not None or a.have is not None):
        pr = st.get("profile")
        if not pr:
            print("No intake answers recorded yet. Example:\n  launchpad.py profile --motion sales-led --buyer small --channels site linkedin outbound --have domain")
            return
        print(json.dumps(pr, indent=2))
        for note in st.get("profile_notes", []):
            print("note:", note)
        cmd_status(a)
        return
    pr = dict(st.get("profile") or {"motion": "sales-led", "buyer": "small", "channels": [], "have": []})
    if a.motion:
        pr["motion"] = a.motion
    if a.buyer:
        pr["buyer"] = a.buyer
    if a.channels is not None:
        pr["channels"] = [c for c in CHANNELS if c in a.channels]
    if a.have is not None:
        pr["have"] = [h for h in HAVES if h in a.have]
    notes = []
    ch, have = set(pr["channels"]), set(pr["have"])
    if "website" in have:
        have.add("domain")
    if "outbound" in ch and pr["buyer"] == "consumer":
        ch.discard("outbound")
        notes.append("Cold email was left out: Sellbird finds and writes to businesses, not individual consumers. Content and the site carry this plan.")
    if "outbound" in ch and "site" not in ch and "website" not in have:
        ch.add("site")
        notes.append("The website was added: outbound needs a live site, because Sellbird learns the product from it and every prospect will visit it.")
    if "outbound" in ch and pr["buyer"] == "large":
        notes.append("Outbound is a weak fit for buyers inside larger companies: Sellbird finds owners named on small businesses' own sites. Expect to build the target list by hand and use Sellbird for writing and sending.")
    if "website" in have and "site" in ch:
        notes.append("You already have a live site, so nothing is rebuilt. It gets audited as it stands; the findings are yours to fix or hand to whoever maintains it.")
    if not ch:
        notes.append("No channels chosen, so the plan is only the product brief. Add channels when you are ready.")
    pr["channels"] = [c for c in CHANNELS if c in ch]
    pr["have"] = [h for h in HAVES if h in have]
    st["profile"] = pr
    st["profile_notes"] = notes
    # steps the person already has are ticked; ticks made this way are undone if the answer changes
    tags = profile_tags(pr)
    auto_before = set(st.get("auto_done", []))
    auto_now = {s["id"] for s in every_step() if s.get("auto_done") in tags and in_plan(s, tags)}
    for i in auto_before - auto_now:
        st["done"].pop(i, None)
    for i in auto_now:
        st["done"].setdefault(i, today())
    st["auto_done"] = sorted(auto_now)
    save(STATE, st)
    write_guide(st)
    plan = all_steps()
    you = sum(1 for s in plan if s["who"] == "you")
    print(f"Plan built: {len(plan)} steps ({you} for you, {len(plan) - you} for Claude Code); {len(every_step()) - len(plan)} left out.")
    for note in notes:
        print("note:", note)
    cmd_status(a)


def cmd_set(a):
    if a.key not in SETTABLE:
        sys.exit(f"Unknown key. Use one of: {', '.join(SETTABLE)}")
    st = state()
    st[a.key] = a.value
    save(STATE, st)
    write_guide(st)
    print(f"{a.key} = {a.value}")


def cmd_mark(a, value):
    st = state()
    known = {s["id"] for s in every_step()}
    bad = [i for i in a.ids if i not in known]
    if bad:
        sys.exit(f"Unknown step id(s): {', '.join(bad)}. Run 'launchpad.py status' to list them.")
    for i in a.ids:
        if value:
            st["done"][i] = today()
        else:
            st["done"].pop(i, None)
    save(STATE, st)
    write_guide(st)
    cmd_status(a)


def cmd_status(_a):
    st = state()
    total = len(all_steps())
    done_in_plan = sum(1 for s in all_steps() if s["id"] in st["done"])
    print(f"{st.get('product') or 'Product'}: {done_in_plan} of {total} steps done")
    tags = profile_tags(st.get("profile"))
    if tags is None:
        print("No intake answers recorded yet, so every step is shown. Run the intake, then 'launchpad.py profile ...'.")
    for g in stages():
        plan = [s for s in g["steps"] if in_plan(s, tags)]
        if not plan:
            continue
        n = sum(1 for s in plan if s["id"] in st["done"])
        print(f"\n{g['title']}  ({n}/{len(plan)})")
        for s in plan:
            mark = "x" if s["id"] in st["done"] else " "
            who = "You        " if s["who"] == "you" else "Claude Code"
            print(f"  [{mark}] {who}  {s['id']:<18} {s['text']}")
    steps = all_steps()
    by_id = {s["id"]: s for s in steps}
    todo = [s for s in steps if s["id"] not in st["done"]]
    if not todo:
        print("\nSetup is complete.")
        return
    ready = [s for s in todo if all(n in st["done"] for n in s.get("needs", []) if n in by_id)]
    cc = next((s for s in ready if s["who"] == "cc"), None)
    you = next((s for s in ready if s["who"] == "you"), None)
    print()
    print(f"Next for Claude Code: {cc['text']}  ({cc['id']})" if cc else "Next for Claude Code: nothing it can start yet")
    print(f"Next for you:         {you['text']}  ({you['id']})" if you else "Next for you:         nothing right now")
    for s in todo:
        if s["who"] == "cc" and s not in ready:
            waits = [by_id[n] for n in s.get("needs", []) if n in by_id and n not in st["done"] and by_id[n]["who"] == "you"]
            if waits:
                print(f"Waiting on you:       '{s['text']}' needs '{waits[0]['text']}' ({waits[0]['id']})")


def write_guide(st):
    out = [f"# Launch guide: {st.get('product') or 'your product'}", "",
           "This file is written by the launchpad skill. It lists every setup step, who does it, and how.",
           f"Last updated {today()}. {len(st['done'])} of {len(all_steps())} steps done.", ""]
    if st.get("hub_url"):
        out += [f"Hub: {st['hub_url']}", ""]
    if st.get("site"):
        out += [f"Site: {st['site']}", ""]
    out += ["Steps marked **You** need your sign-in, your card or your judgement. Claude Code does the rest and stops for your approval between stages.", ""]
    tags = profile_tags(st.get("profile"))
    pr = st.get("profile")
    if pr:
        out += ["**Your plan**, from your answers at the start: "
                + ("people sign up and pay by themselves" if pr.get("motion") == "self-serve" else "you sell through a conversation")
                + "; buyers are " + {"small": "small owner-run businesses", "large": "teams inside larger companies", "consumer": "individual consumers"}.get(pr.get("buyer"), "not yet decided")
                + "; channels: " + (", ".join(pr.get("channels", [])) or "none") + ".", ""]
        for note in st.get("profile_notes", []):
            out += [f"> {note}", ""]
    number = 0
    for g in stages():
        plan = [s for s in g["steps"] if in_plan(s, tags)]
        if not plan:
            continue
        number += 1
        out += [f"## {number}. {g['title']}", "", g["why"], ""]
        for s in plan:
            box = "x" if s["id"] in st["done"] else " "
            who = "You" if s["who"] == "you" else "Claude Code"
            out.append(f"- [{box}] **{who}:** {s['text']}")
            out.append(f"  {s['how']}")
            if s.get("cmd"):
                out.append(f"  Command: `{s['cmd']}`")
            out.append("")
    left_out = [s for s in every_step() if not in_plan(s, tags)]
    if left_out:
        out += ["## Not in your plan", "",
                f"{len(left_out)} steps were left out because of your answers. To change the plan, tell Claude Code what changed "
                "(for example \"add Instagram\" or \"I want cold email after all\") and it will rebuild this checklist.", ""]
    chans = set((pr or {}).get("channels", CHANNELS))
    out += ["## Running it week to week", ""]
    if "outbound" in chans:
        out += ["- **Every working day:** open Sellbird's dashboard, approve the Outbox, and answer replies it flagged for you.",
                "- **To stop all sending at once:** `sellbird sending pause`, or ask Claude Code to pause Sellbird."]
    if chans & SOCIAL:
        out += ["- **Once a week:** ask Claude Code for next week's posts, review them in the hub's Content tab, and tell it which to schedule."]
    if chans & {"site", "outbound"}:
        out += ["- **When the product changes:** tell Claude Code. It refreshes the capability list from your code and names any claim on the site that no longer holds."]
    out += ["- **When you want the hub current:** ask Claude Code to \"sync the hub\".",
            "- **When your situation changes:** tell Claude Code what changed and it rebuilds this checklist.", ""]
    GUIDE.write_text("\n".join(out), encoding="utf-8")


def cmd_guide(_a):
    write_guide(state())
    print(f"Wrote {GUIDE}")


def clean(items, kind):
    """Validate leads or posts. Returns (good, problems)."""
    good, problems = [], []
    if not isinstance(items, list):
        return [], [f"{kind} file must hold a list"]
    for n, it in enumerate(items, 1):
        if not isinstance(it, dict):
            problems.append(f"{kind} #{n}: not an object")
            continue
        it = {k: v for k, v in it.items() if isinstance(v, str) and v.strip()}
        if kind == "lead":
            if not (it.get("email") or it.get("name") or it.get("company")):
                problems.append(f"lead #{n}: needs an email, a name or a company")
                continue
            if "stage" in it and it["stage"] not in LEAD_STAGES:
                problems.append(f"lead #{n}: stage '{it['stage']}' is not one of {LEAD_STAGES}; dropped the stage")
                it.pop("stage")
            if "source" in it and it["source"] not in LEAD_SOURCES:
                it["source"] = "Other"
            if "next_date" in it and not DATE.match(it["next_date"]):
                problems.append(f"lead #{n}: next_date must be YYYY-MM-DD; dropped it")
                it.pop("next_date")
        else:
            if not it.get("title"):
                problems.append(f"post #{n}: needs a title")
                continue
            if "status" in it and it["status"] not in POST_STATUSES:
                problems.append(f"post #{n}: status '{it['status']}' is not one of {POST_STATUSES}; dropped it")
                it.pop("status")
            if "platform" in it and it["platform"] not in POST_PLATFORMS:
                it["platform"] = "Other"
            if "date" in it and not DATE.match(it["date"]):
                problems.append(f"post #{n}: date must be YYYY-MM-DD; dropped it")
                it.pop("date")
        good.append(it)
    return good, problems


def cmd_sync(_a):
    st = state()
    leads, p1 = clean(load(LEADS, []), "lead")
    posts, p2 = clean(load(POSTS, []), "post")
    data = {"meta": {k: st[k] for k in ("product", "site", "booking_url") if st.get(k)},
            "setup_done": sorted(st["done"]), "setup_active": [s["id"] for s in all_steps()],
            "leads": leads, "posts": posts, "built": today()}
    save(SYNC, data)
    for p in p1 + p2:
        print("warning:", p)
    print(f"Wrote {SYNC}: {len(leads)} leads, {len(posts)} posts, {len(st['done'])} steps done.")
    print("Open the hub, press Sync, paste this file's contents (or choose the file), then press Import.")
    if st.get("hub_url"):
        print("Hub:", st["hub_url"])


def cmd_pull(a):
    st = state()
    data = load(Path(a.file), None)
    if not isinstance(data, dict):
        sys.exit("That file is not a hub export.")
    known = {s["id"] for s in every_step()}
    added = [i for i in data.get("setup_done", []) if i in known and i not in st["done"]]
    for i in added:
        st["done"][i] = today()
    save(STATE, st)
    if isinstance(data.get("leads"), list):
        save(WORK / "hub-leads.json", data["leads"])
    if isinstance(data.get("posts"), list):
        save(WORK / "hub-posts.json", data["posts"])
    write_guide(st)
    print(f"Pulled the hub export: {len(added)} newly done step(s). "
          f"Hub leads and posts saved to .launchpad/hub-leads.json and hub-posts.json for reference.")


def cmd_check(_a):
    ids = [s["id"] for s in every_step()]
    hub = HUB_FILE.read_text(encoding="utf-8")
    block = hub[hub.index("const SETUP = ["):hub.index("];", hub.index("const SETUP = ["))]
    hub_ids = re.findall(r'\{id:"([a-z_]+\.[a-z_]+)"', block)
    if ids != hub_ids:
        only_json = [i for i in ids if i not in hub_ids]
        only_hub = [i for i in hub_ids if i not in ids]
        sys.exit(f"Step ids differ. Only in steps.json: {only_json}. Only in hub.html: {only_hub}. Order must match too.")
    if len(set(ids)) != len(ids):
        sys.exit("Duplicate step ids in steps.json")
    print(f"OK: {len(ids)} steps, identical in steps.json and hub.html.")


SKILLS_NEEDED = ["product-marketing", "competitor-profiling", "customer-research", "pricing",
                 "site-architecture", "copywriting", "cro", "offers", "frontend-design",
                 "seo-audit", "ai-seo", "schema", "content-strategy", "social",
                 "web-quality-audit", "seo", "accessibility", "performance", "core-web-vitals",
                 "best-practices", "seo-geo", "web-design-guidelines"]
BRIEF_HEADINGS = ["Observable signals", "Motion", "Approved for public use"]


def cmd_doctor(_a):
    """Report what is in place. Never exits non-zero: it is a map, not a gate."""
    cwd, home = Path.cwd(), Path.home()
    rows = []

    def row(ok, what, detail, fix=""):
        rows.append(("ok" if ok else "MISSING", what, detail, "" if ok else fix))

    st = load(STATE, None) if STATE.exists() else None
    row(bool(st), "Tracker", ".launchpad/state.json" if st else "not started", 'launchpad.py init --product "Name"')
    st = st or {"done": {}}
    pr = st.get("profile")
    row(bool(pr), "Intake answers", ("channels: " + (", ".join(pr.get("channels", [])) or "none")) if pr else "not recorded",
        "ask the intake questions, then launchpad.py profile ...")
    chans = set((pr or {}).get("channels", CHANNELS))

    missing = [n for n in SKILLS_NEEDED
               if not (cwd / ".claude" / "skills" / n / "SKILL.md").exists()
               and not (home / ".claude" / "skills" / n / "SKILL.md").exists()]
    row(not missing, "Skill packs", f"{len(SKILLS_NEEDED) - len(missing)} of {len(SKILLS_NEEDED)} installed",
        "missing: " + ", ".join(missing) + ". See the install commands in references/stack.md")

    agent_files = sorted((SKILL / "assets" / "agents").glob("*.md"))
    gone, stale = [], []
    for f in agent_files:
        here = next((d / f.name for d in (cwd / ".claude" / "agents", home / ".claude" / "agents") if (d / f.name).exists()), None)
        if here is None:
            gone.append(f.stem)
        elif here.read_text(encoding="utf-8") != f.read_text(encoding="utf-8"):
            stale.append(f.stem)
    if gone:
        row(False, "Agents", f"{len(agent_files) - len(gone)} of {len(agent_files)} installed", "launchpad.py agents")
    elif stale:
        row(False, "Agents", "installed, but older than this skill's: " + ", ".join(stale), "launchpad.py agents --force  (replaces them; keep a copy first if you edited them)")
    else:
        row(True, "Agents", f"{len(agent_files)} of {len(agent_files)} installed", "")

    cap = WORK / "capabilities.md"
    if cap.exists():
        text = cap.read_text(encoding="utf-8")
        shipped = len(re.findall(r"\|\s*Shipped\s*\|?\s*$", text, re.M))
        has_commit = bool(re.search(r"\bcommit\b", text, re.I))
        row(shipped > 0 and has_commit, "Capability inventory",
            f"{shipped} shipped row(s)" + ("" if has_commit else ", no commit recorded"),
            "needs at least one Shipped row and the commit it was built from (references/discovery.md)")
    else:
        row(False, "Capability inventory", "not built", "Stage 1, step 1 (references/discovery.md)")

    brief = cwd / ".agents" / "product-marketing.md"
    if brief.exists():
        text = brief.read_text(encoding="utf-8").lower()
        lack = [h for h in BRIEF_HEADINGS if h.lower() not in text]
        row(not lack, "Product brief", "present" if not lack else "present, missing: " + ", ".join(lack),
            "add those headings (Stage 1, step 6)")
    else:
        row(False, "Product brief", "not written", "Stage 1")

    builds_site = "site" in chans and "website" not in set((pr or {}).get("have", []))
    if builds_site:
        row((cwd / "site" / "index.html").exists(), "Site", "site/index.html", "Stage 3; then site_check.py")
        audit = cwd / "site" / "audit.md"
        if audit.exists():
            at = audit.read_text(encoding="utf-8")
            m = re.search(r"## Must fix(.*?)(?:\n## |\Z)", at, re.S)
            open_must = len(re.findall(r"^\|\s*\d+\s*\|", m.group(1), re.M)) if m else 0
            row(open_must == 0, "Site audit", "no must-fix findings" if open_must == 0 else f"{open_must} must-fix finding(s) open", "send them to content-writer, then re-audit")
        else:
            row(False, "Site audit", "not run", "Stage 3: site-auditor agent writes site/audit.md")
    if chans & {"site", "outbound"}:
        row(bool(st.get("domain") or st.get("site")), "Site domain", st.get("domain") or st.get("site") or "not chosen", "launchpad.py set domain <address>  (needed for the sitemap and canonical link)")
        row(bool(st.get("booking_url")), "Booking link", st.get("booking_url") or "not set", "launchpad.py set booking_url <url>")
        row(bool(st.get("site")), "Live site address", st.get("site") or "not set", "after deploy: launchpad.py set site <url>")
    row(bool(st.get("hub_url")), "Hub", st.get("hub_url") or "not set", "references/hub.md, then launchpad.py set hub_url <link>")
    if "outbound" in chans:
        sb = cwd / "tools" / "sellbird"
        sb_ok = (sb / ".venv").exists()
        row(sb_ok, "Sellbird", "installed" if sb_ok else ("cloned, not installed" if sb.exists() else "not installed"), "Stage 5 (references/sellbird.md)")
        row(shutil.which("claude") is not None, "Claude Code CLI", shutil.which("claude") or "not on PATH", "Sellbird needs it: install the CLI and run 'claude login'")

    for status, what, detail, fix in rows:
        print(f"[{status:^7}] {what:<22} {detail}")
        if fix:
            print(f"{'':10}{fix}")
    plan_ids = {s["id"] for s in all_steps()}
    print(f"\n{sum(1 for r in rows if r[0] == 'ok')} of {len(rows)} in place, {len(plan_ids & set(st['done']))} of {len(plan_ids)} setup steps in the plan done.")


SEAL = WORK / "seal.json"
SEAL_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", "target"}
SEAL_MAX_FILES = 20000


def _snapshot(st):
    """Workspace files by content hash; product repo files by size and time (it can be large)."""
    cwd = Path.cwd()
    files, truncated = {}, False

    def walk(base, prefix, by_hash, skip_rel=()):
        nonlocal truncated
        stack = [base]
        while stack:
            d = stack.pop()
            try:
                entries = sorted(d.iterdir())
            except OSError:
                continue
            for e in entries:
                rel = e.relative_to(base).as_posix()
                if e.is_dir():
                    if e.name in SEAL_SKIP_DIRS or rel in skip_rel or e.is_symlink():
                        continue
                    stack.append(e)
                elif e.is_file():
                    if len(files) >= SEAL_MAX_FILES:
                        truncated = True
                        return
                    try:
                        if by_hash:
                            files[prefix + rel] = hashlib.sha256(e.read_bytes()).hexdigest()
                        else:
                            stt = e.stat()
                            files[prefix + rel] = f"{stt.st_size}:{stt.st_mtime_ns}"
                    except OSError:
                        continue

    walk(cwd, "", True, skip_rel=("tools", ".claude/skills"))
    files.pop(".launchpad/seal.json", None)
    repo = (st.get("product_repo") or "").strip()
    if repo:
        rp = (cwd / repo).resolve()
        if rp.is_dir() and rp != cwd.resolve() and cwd.resolve() not in rp.parents:
            walk(rp, "PRODUCT_REPO/", False)
    return files, truncated


def cmd_seal(a):
    st = state()
    now, truncated = _snapshot(st)
    if not a.verify:
        save(SEAL, {"taken": dt.datetime.now().isoformat(timespec="seconds"), "files": now})
        print(f"Sealed {len(now)} files." + (" (file limit reached; the rest are not watched)" if truncated else ""))
        return
    if not SEAL.exists():
        sys.exit("No seal to verify against. Run 'launchpad.py seal' before handing work to an agent.")
    before = load(SEAL, {}).get("files", {})
    changed = sorted(k for k in now if k in before and now[k] != before[k])
    added = sorted(k for k in now if k not in before)
    removed = sorted(k for k in before if k not in now)
    allow = a.allow or []

    def ok(path):
        return not path.startswith("PRODUCT_REPO/") and any(fnmatch.fnmatch(path, pat) for pat in allow)

    bad = 0
    for label, items in (("changed", changed), ("added", added), ("removed", removed)):
        for path in items:
            allowed = ok(path)
            bad += not allowed
            print(f"{'ok       ' if allowed else 'UNEXPECTED'} {label:<8} {path}")
    if not (changed or added or removed):
        print("Nothing changed since the seal.")
    elif bad:
        print(f"\n{bad} file(s) changed outside what was allowed. Look at them before trusting this agent's report.")
        sys.exit(1)
    else:
        print("\nOnly allowed files changed.")


def cmd_agents(a):
    src = SKILL / "assets" / "agents"
    dst = Path.cwd() / ".claude" / "agents"
    first = not dst.exists()
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.md")):
        target = dst / f.name
        if target.exists() and not a.force:
            print(f"kept      {target.relative_to(Path.cwd())}  (already there; --force to replace)")
        else:
            shutil.copyfile(f, target)
            print(f"installed {target.relative_to(Path.cwd())}")
    settings = Path.cwd() / ".claude" / "settings.json"
    if a.default or a.no_default:
        data = load(settings, {})
        if not isinstance(data, dict):
            sys.exit(f"{settings} does not hold a JSON object; not changing it.")
        if a.default:
            if data.get("agent") not in (None, "launch-coordinator"):
                sys.exit(f"{settings} already sets agent = {data['agent']!r}. Not replacing it.")
            data["agent"] = "launch-coordinator"
            print("Sessions in this folder now start as launch-coordinator.")
        elif data.get("agent") == "launch-coordinator":
            data.pop("agent")
            print("Removed launch-coordinator as the session agent here.")
        save(settings, data)
    if first:
        print("This folder had no agents before, so restart Claude Code for it to see them.")


def main():
    p = argparse.ArgumentParser(description="Launchpad tracker")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--product", required=True); s.add_argument("--site"); s.add_argument("--repo"); s.add_argument("--hub"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("set"); s.add_argument("key"); s.add_argument("value"); s.set_defaults(fn=cmd_set)
    s = sub.add_parser("profile"); s.add_argument("--motion", choices=MOTIONS); s.add_argument("--buyer", choices=BUYERS)
    s.add_argument("--channels", nargs="*", choices=CHANNELS); s.add_argument("--have", nargs="*", choices=HAVES); s.set_defaults(fn=cmd_profile)
    s = sub.add_parser("done"); s.add_argument("ids", nargs="+"); s.set_defaults(fn=lambda a: cmd_mark(a, True))
    s = sub.add_parser("undo"); s.add_argument("ids", nargs="+"); s.set_defaults(fn=lambda a: cmd_mark(a, False))
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("guide").set_defaults(fn=cmd_guide)
    sub.add_parser("sync").set_defaults(fn=cmd_sync)
    s = sub.add_parser("pull"); s.add_argument("file"); s.set_defaults(fn=cmd_pull)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("seal"); s.add_argument("--verify", action="store_true"); s.add_argument("--allow", nargs="*"); s.set_defaults(fn=cmd_seal)
    s = sub.add_parser("agents"); s.add_argument("--default", action="store_true"); s.add_argument("--no-default", action="store_true"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_agents)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
