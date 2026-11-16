#!/usr/bin/env python3
"""Prove this skill's own scripts work on this machine. Standard library only.

  python selftest.py

Runs every tracker command and the site checker in a throwaway folder and prints PASS or FAIL for
each. It installs nothing, touches no network and leaves nothing behind. It does not test Claude
Code, the skill packs, Sellbird or Postiz: those are checked by preflight.py and 'launchpad.py doctor'.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

def _safe_console():
    """Windows consoles and piped output often cannot print every character. Never crash on that."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


_safe_console()

HERE = Path(__file__).resolve().parent
LP = [sys.executable, str(HERE / "launchpad.py")]
SC = [sys.executable, str(HERE / "site_check.py")]
results = []


def run(cmd, cwd, expect=0, home=None):
    env = None
    if home is not None:  # a throwaway home, so the person's real ~/.claude never affects a result
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    return p.returncode == expect, (p.stdout or "") + (p.stderr or "")


def test(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok and detail:
        print("      " + detail.strip().replace("\n", "\n      ")[:800])


FAQ = [("Do staff need an app?", "No. Reminders arrive as ordinary texts."),
       ("Does it work for two sites?", "Yes. Each site has its own list."),
       ("How do people sign in?", "With an email address and a password.")]
LD = json.dumps({"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "name": "Self Test", "url": "https://selftest.test/", "sameAs": ["https://www.linkedin.com/company/selftest"]},
    {"@type": "WebSite", "url": "https://selftest.test/", "name": "Self Test"},
    {"@type": "SoftwareApplication", "name": "Self Test", "dateModified": "2030-01-01"},
    {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}]})
GOOD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Self Test: invoices that send themselves</title>
<meta name="description" content="Self Test sends recurring invoices for small bookkeeping firms so month end takes minutes instead of days.">
<link rel="canonical" href="https://selftest.test/"><link rel="icon" href="data:,">
<meta property="og:title" content="Self Test"><meta property="og:description" content="Recurring invoices for bookkeepers.">
<meta property="og:type" content="website"><meta property="og:url" content="https://selftest.test/">
<meta property="og:image" content="https://selftest.test/og.png"><meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">%s</script><style>a:focus-visible{outline:2px solid}</style>
</head><body><header><a href="#top">Self Test</a></header><main id="top"><h1>Invoices that send themselves</h1>
<p>Self Test is invoicing software for small bookkeeping firms. It sends each client's recurring invoice on the right day every month, so month end takes minutes instead of days and nothing is forgotten.</p>
<p>%s</p><h2>Questions</h2><dl>%s</dl>
<a href="https://book.test/acme">Book a 15-minute call</a></main>
<footer>Self Test. <a href="mailto:hello@selftest.test">Contact us</a>. Last updated <time datetime="2030-01-01">1 January 2030</time>.</footer></body></html>""" % (
    LD, "Recurring invoices for bookkeepers, sent on schedule. " * 40, "".join(f"<dt>{q}</dt><dd>{a}</dd>" for q, a in FAQ))


def ads_tests(tmp):
    """Paid ads: the stage, its gating, the landing-page rule, and a doctor that knows claude-ads is global."""
    ws, home = tmp / "ads-ws", tmp / "ads-home"
    ws.mkdir()
    home.mkdir()
    run(LP + ["init", "--product", "Ads Test"], ws)
    ok, out = run(LP + ["profile", "--motion", "self-serve", "--buyer", "consumer", "--channels", "site", "ads", "--have", "domain"], ws)
    guide = (ws / "LAUNCH_GUIDE.md").read_text(encoding="utf-8")
    weekly = guide.split("## Running it week to week")[-1]
    test("a plan with paid ads builds the ads stage, without the audit when there are no ad accounts",
         ok and "Plan built: 15 steps" in out and "## 4. Paid ads" in guide and "/ads launch --draft" in guide
         and "ads.install" in out and "ads.launch" in out and "ads.audit" not in out and "site.live" in out, out)
    test("the weekly routine for ads drafts and leaves every change to the person",
         "/ads monitor" in weekly and "/ads optimize --draft" in weekly and "--apply" not in weekly, weekly)
    ok, out = run(LP + ["profile", "--have", "domain", "ad-accounts"], ws)
    test("existing ad accounts add the audit step", ok and "Plan built: 16 steps" in out and "ads.audit" in out, out)
    ok, out = run(LP + ["profile", "--channels", "ads", "--have"], ws)
    st = json.loads((ws / ".launchpad" / "state.json").read_text(encoding="utf-8"))
    test("profile adds the website when paid ads are chosen without one",
         ok and "site" in st["profile"]["channels"] and "landing page" in out, out)

    ok, out = run(LP + ["doctor"], ws, home=home)
    test("doctor expects claude-ads in the global ~/.claude when ads are planned", ok and "MISSING" in out and "claude-ads" in out
         and "not in ~/.claude/skills/ads" in out, out)
    checkout = ws / "tools" / "claude-ads"
    (checkout / "agents").mkdir(parents=True)
    (checkout / "skills" / "ads-plan").mkdir(parents=True)
    (checkout / "agents" / "copy-writer.md").write_text("x", encoding="utf-8")
    (home / ".claude" / "agents").mkdir(parents=True)
    (home / ".claude" / "agents" / "copy-writer.md").write_text("someone else's", encoding="utf-8")
    ok, out = run(LP + ["doctor"], ws, home=home)
    test("doctor names an agent that claude-ads' installer would clash with", ok and "CLASH" in out and "copy-writer" in out, out)
    (home / ".claude" / "skills" / "ads").mkdir(parents=True)
    (home / ".claude" / "skills" / "ads" / "SKILL.md").write_text("name: ads", encoding="utf-8")
    ok, out = run(LP + ["doctor"], ws, home=home)
    test("doctor finds claude-ads installed globally and notes a skills-only install",
         ok and "(global), skills only" in out and "--no-deps" in out and "CLASH" not in out, out)
    run(LP + ["profile", "--channels", "site", "linkedin"], ws)
    ok, out = run(LP + ["doctor"], ws, home=tmp / "ads-empty-home")
    test("doctor does not ask for claude-ads when ads are not in the plan", ok and "claude-ads" not in out, out)


def main():
    skill_md = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
    desc = next((l[len("description:"):].strip() for l in skill_md.split("---")[1].splitlines() if l.startswith("description:")), "")
    test("SKILL.md has a description within the 1024-character limit", 0 < len(desc) <= 1024, f"{len(desc)} characters")
    bad_agents = []
    for f in sorted((HERE.parent / "assets" / "agents").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        head = text.split("---")[1] if text.startswith("---") else ""
        if "\nname:" not in "\n" + head or "\ndescription:" not in "\n" + head:
            bad_agents.append(f.name)
    test("every agent definition has a name and a description", not bad_agents, ", ".join(bad_agents))
    with tempfile.TemporaryDirectory(prefix="launchpad-selftest-") as tmp:
        ws = Path(tmp)
        ok, out = run(LP + ["check"], ws)
        test("step ids match between steps.json and hub.html", ok, out)
        ok, out = run(LP + ["init", "--product", "Self Test"], ws)
        test("init creates the tracker and the guide", ok and (ws / "LAUNCH_GUIDE.md").exists() and (ws / ".launchpad" / "state.json").exists(), out)
        ok, out = run(LP + ["profile", "--motion", "sales-led", "--buyer", "small", "--channels", "site", "linkedin", "--have", "domain"], ws)
        st = json.loads((ws / ".launchpad" / "state.json").read_text(encoding="utf-8"))
        guide = (ws / "LAUNCH_GUIDE.md").read_text(encoding="utf-8")
        test("profile builds a tailored plan and ticks what the person already has",
             ok and "Plan built: 12 steps" in out and "acct.domain" in st["done"] and "Sellbird" not in guide and "Not in your plan" in guide, out)
        test("a plan without paid ads has no ads steps and no ads routine",
             "ads." not in out and "Paid ads" not in guide and "/ads" not in guide, out)
        ok, out = run(LP + ["profile", "--buyer", "consumer", "--channels", "instagram", "outbound", "--have"], ws)
        st = json.loads((ws / ".launchpad" / "state.json").read_text(encoding="utf-8"))
        test("profile drops cold email for a consumer product, says why, and unticks what is no longer owned",
             ok and "outbound" not in st["profile"]["channels"] and "note:" in out and "acct.domain" not in st["done"], out)
        ok, out = run(LP + ["profile", "--buyer", "small", "--channels", "outbound", "--have"], ws)
        st = json.loads((ws / ".launchpad" / "state.json").read_text(encoding="utf-8"))
        test("profile adds the website when cold email is chosen without one", ok and "site" in st["profile"]["channels"] and "website was added" in out, out)
        ok, out = run(LP + ["profile", "--motion", "sales-led", "--buyer", "small", "--channels", "site", "linkedin", "instagram", "x", "outbound", "ads", "--have", "ad-accounts"], ws)
        test("a full plan has every step", ok and "Plan built: 33 steps" in out and "0 left out" in out, out)
        ok, out = run(LP + ["done", "brief.write"], ws)
        test("done marks a step", ok and "brief.write" in json.loads((ws / ".launchpad" / "state.json").read_text(encoding="utf-8"))["done"], out)
        ok, out = run(LP + ["done", "no.such_step"], ws, expect=1)
        test("an unknown step id is refused", ok, out)
        ok, out = run(LP + ["set", "booking_url", "https://book.test/acme"], ws)
        test("set stores a value", ok, out)
        (ws / ".launchpad" / "leads.json").write_text(json.dumps([{"email": "dana@example.com", "name": "Dana", "stage": "nonsense"}, {"x": "y"}]), encoding="utf-8")
        (ws / ".launchpad" / "posts.json").write_text(json.dumps([{"title": "Hello", "date": "2030-01-01", "platform": "LinkedIn", "status": "Drafted"}]), encoding="utf-8")
        ok, out = run(LP + ["sync"], ws)
        sync = json.loads((ws / ".launchpad" / "hub-sync.json").read_text(encoding="utf-8")) if (ws / ".launchpad" / "hub-sync.json").exists() else {}
        test("sync builds the hub file, drops bad rows and carries the plan",
             ok and len(sync.get("leads", [])) == 1 and "stage" not in sync["leads"][0] and len(sync.get("posts", [])) == 1 and len(sync.get("setup_active", [])) == 33, out)
        export = ws / "hub-data.json"
        export.write_text(json.dumps({"setup_done": ["acct.domain", "bogus"], "leads": [], "posts": []}), encoding="utf-8")
        ok, out = run(LP + ["pull", str(export)], ws)
        test("pull reads a hub export back", ok and "acct.domain" in json.loads((ws / ".launchpad" / "state.json").read_text(encoding="utf-8"))["done"], out)
        ok, out = run(LP + ["agents"], ws)
        test("agents installs four definitions", ok and len(list((ws / ".claude" / "agents").glob("*.md"))) == 4, out)
        ok, out = run(LP + ["agents", "--default"], ws)
        test("agents --default sets the session agent", ok and json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8")).get("agent") == "launch-coordinator", out)
        ok, out = run(LP + ["doctor"], ws)
        test("doctor reports without failing", ok and "Tracker" in out, out)
        ok, out = run(LP + ["status"], ws)
        test("status lists the steps", ok and "Next for" in out, out)

        ok, out = run(SC, ws, expect=1)
        test("site check refuses a missing site", ok, out)
        run(LP + ["set", "domain", "selftest.test"], ws)
        site = ws / "site"
        site.mkdir()
        (site / "index.html").write_text(GOOD, encoding="utf-8")
        (site / "copy.md").write_text("approved words\n", encoding="utf-8")
        (site / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: https://selftest.test/sitemap.xml\n", encoding="utf-8")
        (site / "sitemap.xml").write_text("<urlset><url><loc>https://selftest.test/</loc><lastmod>2030-01-01</lastmod></url></urlset>", encoding="utf-8")
        (ws / ".launchpad" / "capabilities.md").write_text(
            "Built at commit abc1234.\n\n| Capability | What a user can do | Evidence | Status |\n|---|---|---|---|\n"
            "| Recurring invoices | x | a.py | Shipped |\n| Late-payment reminders | x | b.py | Stub |\n\n"
            "## In the README but not found in code\n- \"Cash-flow forecasting\"\n", encoding="utf-8")
        ok, out = run(SC, ws)
        test("site check passes a sound page with no errors and no warnings", ok and "0 error(s), 0 warning(s)" in out, out)

        bad = GOOD.replace("<h1>", "<p>Late-payment reminders and cash-flow forecasting. Lorem ipsum.</p><h1>").replace("https://book.test/acme", "https://elsewhere.test")
        (site / "index.html").write_text(bad, encoding="utf-8")
        ok, out = run(SC, ws, expect=1)
        test("site check catches a stub claim, a README-only claim, a placeholder and a missing booking link",
             ok and "Late-payment reminders" in out and "Cash-flow forecasting" in out and "lorem ipsum" in out.lower() and "booking link" in out, out)

        bad = GOOD.replace('<meta charset="utf-8">', '<meta charset="utf-8"><meta name="robots" content="noindex">') \
                  .replace('"name": "How do people sign in?"', '"name": "Is there a free trial?"') \
                  .replace('"@type": "FAQPage"', '"@type": "FAQPage", "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.9"}')
        (site / "index.html").write_text(bad, encoding="utf-8")
        (site / "robots.txt").write_text("User-agent: *\nAllow: /\n\nUser-agent: OAI-SearchBot\nDisallow: /\n\nUser-agent: GPTBot\nDisallow: /\n", encoding="utf-8")
        ok, out = run(SC, ws, expect=1)
        test("site check catches noindex, hidden FAQ markup, an unbacked rating and a blocked answer crawler",
             ok and "noindex" in out and "Is there a free trial?" in out and "AggregateRating" in out and "blocks OAI-SearchBot" in out, out)
        test("a blocked training crawler is reported as the owner's choice, not an error",
             "GPTBot blocked" in out and "blocks GPTBot" not in out, out)

        (site / "audit.md").write_text("# Site audit\n\n## Must fix\n| # | Area | Finding | Evidence | Fix |\n|---|---|---|---|---|\n| 1 | AI search | x | y | z |\n\n## Should fix\n", encoding="utf-8")
        ok, out = run(LP + ["doctor"], ws)
        test("doctor counts open must-fix findings in the audit", ok and "1 must-fix finding(s) open" in out, out)

        ok, out = run(LP + ["seal"], ws)
        test("seal records the workspace", ok and (ws / ".launchpad" / "seal.json").exists(), out)
        ok, out = run(LP + ["seal", "--verify"], ws)
        test("verify passes when nothing changed", ok and "Nothing changed" in out, out)
        (site / "audit.md").write_text("# rewritten by the auditor\n", encoding="utf-8")
        ok, out = run(LP + ["seal", "--verify", "--allow", "site/audit.md"], ws)
        test("verify accepts a change to an allowed file", ok and "Only allowed files changed" in out, out)
        (site / "index.html").write_text(GOOD + "<!-- quietly edited -->", encoding="utf-8")
        ok, out = run(LP + ["seal", "--verify", "--allow", "site/audit.md"], ws, expect=1)
        test("verify catches an agent editing a file it should not touch", ok and "UNEXPECTED" in out and "site/index.html" in out, out)

        ads_tests(Path(tmp))

    passed = sum(results)
    print(f"\n{passed} of {len(results)} passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
