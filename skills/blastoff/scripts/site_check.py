#!/usr/bin/env python3
"""Check the built site against what can be verified without a browser. Standard library only.
Changes nothing.

Run from the go-to-market workspace:

  site_check.py                 check site/index.html and the files next to it
  site_check.py --dir other/    check a different folder
  site_check.py --area ai       show one area only: claims, onpage, data, ai, access, speed

It covers the parts of search, AI search, accessibility and speed practice that are mechanical:
tags, files, structured data, crawler rules, and claims that contradict the capability inventory.
It cannot judge contrast, layout, tap targets, real load speed or how the page reads. Those belong
to the site-auditor agent and a browser.

Exit code 1 if anything is marked ERROR. WARN lines are judgement calls to read, not blockers.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

PLACEHOLDERS = [
    r"lorem ipsum", r"\bTODO\b", r"\bTBD\b", r"\bFIXME\b", r"your[- ]company", r"your[- ]product",
    r"\{\{.*?\}\}", r"\[(?:insert|add|your|placeholder)[^\]]*\]", r"example\.com", r"\bxxx+\b",
    r"placeholder", r"coming soon",
]
OVERCLAIMS = [
    r"\b#1\b", r"world[- ]class", r"best[- ]in[- ]class", r"industry[- ]leading", r"revolutionary",
    r"guaranteed", r"trusted by (?:thousands|hundreds|leading)", r"\b\d{2,3}% (?:faster|more|less|cheaper)\b",
]
VAGUE_LINKS = {"click here", "here", "read more", "learn more", "more", "link", "this"}
# Crawlers that decide whether the page can be found and cited. Blocking one is almost never meant.
SEARCH_BOTS = ["Googlebot", "Bingbot", "OAI-SearchBot", "Claude-SearchBot", "PerplexityBot"]
# Crawlers that collect training data. Allowing or blocking these is the owner's choice.
TRAINING_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "Applebot-Extended"]

def _safe_console():
    """Windows consoles and piped output often cannot print every character. Never crash on that."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


_safe_console()

VOID = {"meta", "link", "img", "br", "hr", "input", "source", "area", "base", "col", "embed", "track", "wbr"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.lang = None
        self.charset = False
        self.metas = {}
        self.rels = {}            # rel -> [href]
        self.headings = []        # (level, text)
        self.anchors = []         # {href, text, target, rel, aria}
        self.imgs = []            # attrs
        self.scripts = []         # {src, in_head, defer, async, type}
        self.jsonld = []
        self.landmarks = set()
        self.inputs = []          # attrs
        self.labels_for = set()
        self.buttons = []         # text / aria
        self.css = []
        self.text = []
        self.after_h1 = None      # first paragraph after the h1
        self.questions = []       # visible questions (dt or headings ending in ?)
        self.footer_text = []
        self._stack = []
        self._cap = None          # (kind, buffer)
        self._skip = 0
        self._seen_h1 = False
        self._in_head = False
        self._in_footer = 0
        self._in_label = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag not in VOID:
            self._stack.append(tag)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "head":
            self._in_head = True
        elif tag == "meta":
            if "charset" in a:
                self.charset = True
            key = a.get("name") or a.get("property")
            if key:
                self.metas[key.lower()] = a.get("content", "")
        elif tag == "link":
            for rel in a.get("rel", "").lower().split():
                self.rels.setdefault(rel, []).append(a.get("href", ""))
        elif tag == "title":
            self._cap = ("title", [])
        elif re.fullmatch(r"h[1-6]", tag):
            self._cap = (tag, [])
        elif tag == "p" and self._seen_h1 and self.after_h1 is None and self._cap is None:
            self._cap = ("p1", [])
        elif tag == "dt":
            self._cap = ("dt", [])
        elif tag == "summary":
            self._cap = ("summary", [])
        elif tag == "a":
            self.anchors.append({"href": a.get("href", ""), "text": "", "target": a.get("target", ""),
                                 "rel": a.get("rel", ""), "aria": a.get("aria-label", "")})
            self._cap = self._cap or ("a", [])
        elif tag == "button":
            self.buttons.append({"text": "", "aria": a.get("aria-label", "")})
            self._cap = self._cap or ("button", [])
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "script":
            if (a.get("type") or "").lower() == "application/ld+json":
                self._cap = ("jsonld", [])
            else:
                self.scripts.append({"src": a.get("src", ""), "in_head": self._in_head, "defer": "defer" in a,
                                     "async": "async" in a, "module": a.get("type") == "module"})
                self._skip += 1
        elif tag == "style":
            self._cap = ("style", [])
        elif tag in ("main", "nav", "header", "footer"):
            self.landmarks.add(tag)
            if tag == "footer":
                self._in_footer += 1
        elif tag in ("input", "select", "textarea"):
            if a.get("type") not in ("hidden", "submit", "button"):
                a["_in_label"] = self._in_label > 0
                self.inputs.append(a)
        elif tag == "label":
            self._in_label += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        if a.get("role") in ("main", "navigation", "banner", "contentinfo"):
            self.landmarks.add({"navigation": "nav", "banner": "header", "contentinfo": "footer"}.get(a["role"], a["role"]))

    def handle_endtag(self, tag):
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass
        if tag == "head":
            self._in_head = False
        if tag == "footer" and self._in_footer:
            self._in_footer -= 1
        if tag == "label" and self._in_label:
            self._in_label -= 1
        if tag == "script" and self._skip and not (self._cap and self._cap[0] == "jsonld"):
            self._skip -= 1
        if not self._cap:
            return
        kind, buf = self._cap
        text = re.sub(r"\s+", " ", "".join(buf)).strip()
        if kind == "title" and tag == "title":
            self.title = text
        elif kind == tag and re.fullmatch(r"h[1-6]", tag):
            self.headings.append((int(tag[1]), text))
            if tag == "h1":
                self._seen_h1 = True
            if text.endswith("?"):
                self.questions.append(text)
        elif kind == "p1" and tag == "p":
            self.after_h1 = text
        elif kind in ("dt", "summary") and tag == kind:
            if text.endswith("?"):
                self.questions.append(text)
        elif kind == "a" and tag == "a":
            self.anchors[-1]["text"] = text
        elif kind == "button" and tag == "button":
            self.buttons[-1]["text"] = text
        elif kind == "jsonld" and tag == "script":
            self.jsonld.append("".join(buf))
        elif kind == "style" and tag == "style":
            self.css.append("".join(buf))
        else:
            if tag == "a" and self.anchors and not self.anchors[-1]["text"]:
                self.anchors[-1]["text"] = "\x00"   # filled below from running text
            return
        self._cap = None

    def handle_data(self, data):
        if self._cap:
            self._cap[1].append(data)
            if self._cap[0] in ("jsonld", "style", "title"):
                return
        if self._skip:
            return
        self.text.append(data)
        if self._in_footer:
            self.footer_text.append(data)
        if self.anchors and "a" in self._stack and self._cap and self._cap[0] != "a":
            cur = self.anchors[-1]
            cur["text"] = (cur["text"].replace("\x00", "") + " " + data).strip()
        if self.buttons and "button" in self._stack and self._cap and self._cap[0] != "button":
            self.buttons[-1]["text"] = (self.buttons[-1]["text"] + " " + data).strip()


def non_shipped(cap_file):
    """Capabilities the inventory does not mark Shipped, plus README-only claims."""
    names = []
    if not cap_file.exists():
        return names
    in_readme_list = False
    for line in cap_file.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("#"):
            in_readme_list = "readme" in s.lower() and "not found" in s.lower()
            continue
        if s.startswith("|") and not re.match(r"^\|\s*-", s):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 4 and cells[0].lower() != "capability":
                status = cells[-1].lower()
                if status and not status.startswith("shipped"):
                    names.append((cells[0], cells[-1]))
        elif in_readme_list and s.startswith("-"):
            claim = s.lstrip("- ").strip().strip('"\u201c\u201d')
            if claim:
                names.append((claim, "Claimed only"))
    return names


def walk_types(node, found):
    """Collect every @type (and the node carrying it) from a JSON-LD value."""
    if isinstance(node, dict):
        t = node.get("@type")
        for name in (t if isinstance(t, list) else [t]):
            if isinstance(name, str):
                found.setdefault(name, []).append(node)
        for v in node.values():
            walk_types(v, found)
    elif isinstance(node, list):
        for v in node:
            walk_types(v, found)


def robots_groups(text):
    """Parse robots.txt into {agent_lower: [disallow paths]}; also return sitemap lines."""
    groups, agents, sitemaps, last_was_agent = {}, [], [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = [x.strip() for x in line.split(":", 1)]
        key = key.lower()
        if key == "user-agent":
            if not last_was_agent:
                agents = []
            agents.append(val.lower())
            groups.setdefault(val.lower(), [])
            last_was_agent = True
        else:
            last_was_agent = False
            if key == "disallow":
                for ag in agents:
                    groups[ag].append(val)
            elif key == "sitemap":
                sitemaps.append(val)
    return groups, sitemaps


def blocked(groups, bot):
    """True when the bot's own group, or the catch-all group if it has none, shuts out the whole site."""
    rules = groups.get(bot.lower(), groups.get("*", []))
    return any(r.strip() in ("/", "/*", "*") for r in rules)


def main():
    ap = argparse.ArgumentParser(description="Check the built site")
    ap.add_argument("--dir", default="site")
    ap.add_argument("--area", choices=["claims", "onpage", "data", "ai", "access", "speed"])
    ap.add_argument("--seo", action="store_true", help=argparse.SUPPRESS)   # accepted for older instructions
    a = ap.parse_args()

    root = Path.cwd()
    site = root / a.dir
    index = site / "index.html"
    if not index.exists():
        print(f"ERROR  {index} does not exist. Build the site first.")
        sys.exit(1)
    if index.stat().st_size == 0:
        print(f"ERROR  {index} is empty.")
        sys.exit(1)

    out = {k: [] for k in ("claims", "onpage", "data", "ai", "access", "speed")}
    names = {"claims": "Claims and leftovers", "onpage": "Search: on-page and files", "data": "Structured data",
             "ai": "AI search", "access": "Accessibility (what is checkable without a browser)",
             "speed": "Speed (what is checkable without a browser)"}

    def E(area, msg): out[area].append(("ERROR", msg))
    def W(area, msg): out[area].append(("WARN", msg))
    def I(area, msg): out[area].append(("info", msg))

    raw = index.read_text(encoding="utf-8", errors="replace")
    page = Page()
    try:
        page.feed(raw)
        page.close()
    except Exception as e:   # html.parser is forgiving, but never let a strange page crash the check
        print(f"ERROR  site/index.html could not be parsed: {e}")
        sys.exit(1)
    text = re.sub(r"\s+", " ", " ".join(page.text)).strip()
    low = text.lower()
    words = len(text.split())
    css = "\n".join(page.css)

    state = {}
    sf = root / ".launchpad" / "state.json"
    if sf.exists():
        try:
            state = json.loads(sf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            W("claims", ".launchpad/state.json is not valid JSON; tracker values were not used")
    product = (state.get("product") or "").strip()
    domain = (state.get("domain") or state.get("site") or "").strip()
    host = urlparse(domain if "//" in domain else "https://" + domain).netloc.lower() if domain else ""
    booking = (state.get("booking_url") or "").strip()

    # ---------------- claims and leftovers
    cap_file = root / ".launchpad" / "capabilities.md"
    if cap_file.exists():
        for name, status in non_shipped(cap_file):
            if len(name) >= 6 and name.lower() in (low + " " + " ".join(page.jsonld).lower()):
                E("claims", f"The page mentions \"{name}\", which the capability inventory marks {status}.")
    else:
        W("claims", "No .launchpad/capabilities.md, so claims were not checked against the code.")
    for pat in PLACEHOLDERS:
        m = re.search(pat, text, re.I)
        if m:
            E("claims", f"Placeholder text left in the page: \"{m.group(0)}\"")
    for pat in OVERCLAIMS:
        m = re.search(pat, text, re.I)
        if m:
            W("claims", f"Claim that needs a source or should go: \"{m.group(0)}\"")
    hrefs = [x["href"] for x in page.anchors]
    if booking:
        if any(h.rstrip("/") == booking.rstrip("/") for h in hrefs):
            I("claims", "main button links to the booking link")
        else:
            E("claims", f"No link to the booking link ({booking}). The page has no way to act on the offer.")
    elif any(h in ("#book", "#") for h in hrefs):
        W("claims", "The main button is still a stand-in (#book). Run 'launchpad.py set booking_url <url>' and rebuild before deploying.")
    elif not any(urlparse(h).scheme in ("http", "https", "mailto") for h in hrefs):
        E("claims", "No link a visitor can act on, and no booking link is set in the tracker.")
    if not (site / "copy.md").exists():
        W("claims", f"No {a.dir}/copy.md; keep the approved words next to the build.")

    # ---------------- on-page search basics
    t = page.title
    if not t:
        E("onpage", "No <title>.")
    else:
        if not 30 <= len(t) <= 60:
            W("onpage", f"Title is {len(t)} characters; 30 to 60 displays fully in results.")
        if product and product.lower() not in t.lower():
            W("onpage", f"Title does not contain the product name ({product}).")
        I("onpage", f"title: {t}")
    d = page.metas.get("description", "").strip()
    if not d:
        E("onpage", 'No <meta name="description">.')
    elif not 70 <= len(d) <= 160:
        W("onpage", f"Meta description is {len(d)} characters; 70 to 160 displays fully.")
    if "viewport" not in page.metas:
        E("onpage", 'No <meta name="viewport">; the page will not fit phones.')
    if not page.charset:
        W("onpage", 'No <meta charset>.')
    if not page.lang:
        E("onpage", "<html> has no lang attribute.")
    robots_meta = (page.metas.get("robots", "") + " " + page.metas.get("googlebot", "")).lower()
    if "noindex" in robots_meta:
        E("onpage", "The page carries a noindex tag, so search engines will drop it.")
    h1s = [h for h in page.headings if h[0] == 1]
    if not h1s:
        E("onpage", "No <h1>.")
    elif len(h1s) > 1:
        W("onpage", f"{len(h1s)} <h1> elements; a page should have one.")
    prev = 0
    for level, htext in page.headings:
        if prev and level > prev + 1:
            W("onpage", f"Heading levels skip from h{prev} to h{level} at \"{htext[:50]}\".")
            break
        prev = level
    canon = (page.rels.get("canonical") or [""])[0]
    if host:
        if not canon:
            E("onpage", 'No <link rel="canonical"> although the domain is known.')
        elif host not in canon.lower():
            E("onpage", f"The canonical link ({canon}) does not point at {host}.")
        elif not canon.lower().startswith("https://"):
            W("onpage", "The canonical link is not https.")
    else:
        W("onpage", "No domain set, so the canonical link, og:url and sitemap.xml cannot be finished. Run 'launchpad.py set domain <address>'.")
    for og in ("og:title", "og:description", "og:type"):
        if og not in page.metas:
            W("onpage", f"No {og} tag; shared links will preview poorly.")
    if host and host not in page.metas.get("og:url", "").lower():
        W("onpage", "No og:url pointing at the domain.")
    if "og:image" not in page.metas:
        W("onpage", "No og:image. Shared links show no picture; it needs a real image file (1200x630) next to the page.")
    if "twitter:card" not in page.metas:
        W("onpage", "No twitter:card tag.")
    if not page.rels.get("icon"):
        W("onpage", "No favicon link.")
    ext_imgs = 0
    for tag, urls in (("link", [h for hs in page.rels.values() for h in hs]), ("img", [i.get("src", "") for i in page.imgs]),
                      ("script", [s["src"] for s in page.scripts]), ("a", hrefs)):
        for url in urls:
            u = urlparse(url)
            if not url or u.scheme in ("http", "https", "mailto", "tel", "data", "javascript") or url.startswith("#") or not u.path:
                ext_imgs += 1 if (tag == "img" and u.scheme in ("http", "https")) else 0
                continue
            target = (site / u.path.lstrip("/")) if u.path.startswith("/") else (index.parent / u.path)
            if not target.exists():
                E("onpage", f"Broken local link in <{tag}>: {url}")
    if ext_imgs:
        W("onpage", f"{ext_imgs} image(s) load from other sites; they will not show in an artifact preview and can break later.")
    for x in page.anchors:
        label = (x["text"] or x["aria"]).strip().lower().rstrip(".")
        if label in VAGUE_LINKS:
            W("onpage", f"Link text \"{label}\" says nothing about where it goes.")
            break
    robots_file = site / "robots.txt"
    groups, sitemaps = ({}, [])
    if not robots_file.exists():
        E("onpage", f"Missing {a.dir}/robots.txt.")
    else:
        groups, sitemaps = robots_groups(robots_file.read_text(encoding="utf-8", errors="replace"))
        if host and not any(host in s.lower() for s in sitemaps):
            W("onpage", "robots.txt has no Sitemap line pointing at the domain.")
    sm = site / "sitemap.xml"
    if host:
        if not sm.exists():
            E("onpage", f"Missing {a.dir}/sitemap.xml.")
        else:
            smt = sm.read_text(encoding="utf-8", errors="replace").lower()
            if host not in smt:
                E("onpage", f"sitemap.xml does not list an address on {host}.")
            if "<lastmod>" not in smt:
                W("onpage", "sitemap.xml has no <lastmod>.")

    # ---------------- structured data
    types = {}
    for n, block in enumerate(page.jsonld, 1):
        try:
            walk_types(json.loads(block), types)
        except json.JSONDecodeError as e:
            E("data", f"Structured data block {n} is not valid JSON: {e}")
    if not page.jsonld:
        E("data", "No structured data (JSON-LD) on the page.")
    else:
        orgs = types.get("Organization", []) + types.get("LocalBusiness", []) + types.get("Corporation", [])
        if not orgs:
            E("data", "No Organization in the structured data. Search and AI systems use it to know who is behind the page.")
        else:
            o = orgs[0]
            if not o.get("name") or not o.get("url"):
                W("data", "Organization is missing name or url.")
            if not o.get("sameAs"):
                W("data", "Organization has no sameAs links. Add the LinkedIn page and other profiles once they exist; they tie the brand together.")
        if not any(k in types for k in ("SoftwareApplication", "WebApplication", "Product", "Service")):
            W("data", "Nothing describes the product itself (SoftwareApplication, Product or Service).")
        if "WebSite" not in types:
            W("data", "No WebSite entry.")
        faq = types.get("FAQPage", [])
        if page.questions and not faq:
            W("data", f"The page shows {len(page.questions)} question(s) but has no FAQPage structured data.")
        for f in faq:
            ents = f.get("mainEntity", [])
            ents = [ents] if isinstance(ents, dict) else ents if isinstance(ents, list) else []
            if not ents:
                W("data", "FAQPage has no questions in mainEntity.")
            for q in ents:
                if not isinstance(q, dict):
                    continue
                name = str(q.get("name") or "").strip()
                if name and name.lower() not in low:
                    E("data", f"FAQ structured data asks \"{name[:70]}\" but the page does not show that question. Marked-up content must be visible.")
        for bad in ("AggregateRating", "Review"):
            if bad in types:
                E("data", f"Structured data contains {bad}. Ratings and reviews may only be marked up when real ones are shown on the page and approved for public use.")
        if not any(isinstance(n, dict) and n.get("dateModified") for nodes in types.values() for n in nodes):
            W("data", "No dateModified anywhere in the structured data; freshness is a signal for search and AI answers.")

    # ---------------- AI search
    if robots_file.exists():
        shut = [b for b in SEARCH_BOTS if blocked(groups, b)]
        if len(shut) == len(SEARCH_BOTS) and blocked(groups, "*"):
            E("ai", "robots.txt disallows the whole site for every crawler. Nothing can find or quote the page.")
        else:
            for b in shut:
                E("ai", f"robots.txt blocks {b}. That removes the page from the search or answer engine it serves.")
        states = [f"{b} {'blocked' if blocked(groups, b) else 'allowed'}" for b in TRAINING_BOTS]
        I("ai", "training crawlers (the owner's choice, not a ranking matter): " + ", ".join(states))
    if words < 250:
        (E if words < 120 else W)("ai", f"Only {words} words are in the HTML itself. Many AI crawlers do not run scripts, and a thin page gives them nothing to quote.")
    else:
        I("ai", f"{words} words readable without running scripts")
    if page.after_h1 is None:
        W("ai", "No paragraph follows the <h1>. The first lines should say plainly what the product is and who it is for.")
    else:
        n = len(page.after_h1.split())
        if not 15 <= n <= 70:
            W("ai", f"The paragraph after the <h1> is {n} words. An answer block of roughly 40 to 60 words is what gets quoted.")
        if product and product.lower() not in page.after_h1.lower() and product.lower() not in " ".join(text.split()[:120]).lower():
            W("ai", f"The opening does not name {product}. State what it is in the first lines so the page can be quoted on its own.")
    if len(page.questions) < 3:
        W("ai", f"{len(page.questions)} visible question(s). A short FAQ in the buyer's own words is one of the most quoted formats.")
    if not (re.search(r"last updated|updated on|updated:", low) or re.search(r"<time\b", raw, re.I)):
        W("ai", "No visible 'last updated' date.")
    footer = " ".join(page.footer_text)
    if not any(h.startswith("mailto:") for h in hrefs) and not re.search(r"contact", low):
        W("ai", "No contact route on the page. A named business with a way to reach it is a trust signal for people and for AI answers.")
    if product and product.lower() not in footer.lower():
        W("ai", "The footer does not name the business.")
    if (site / "llms.txt").exists():
        I("ai", "llms.txt present (optional; no major engine has confirmed using it)")
    else:
        I("ai", "no llms.txt (optional; cheap to add, not known to affect ranking)")

    # ---------------- accessibility proxies
    for lm in ("main", "header", "footer"):
        if lm not in page.landmarks:
            W("access", f"No <{lm}> landmark.")
    missing_alt = sum(1 for i in page.imgs if "alt" not in i)
    if missing_alt:
        E("access", f"{missing_alt} image(s) without an alt attribute.")
    for x in page.anchors:
        if not (x["text"].replace("\x00", "").strip() or x["aria"].strip()):
            E("access", f"A link has no text or label (href={x['href'][:60]}).")
            break
    for b in page.buttons:
        if not (b["text"].strip() or b["aria"].strip()):
            E("access", "A button has no text or label.")
            break
    for i in page.inputs:
        if not (i.get("_in_label") or i.get("aria-label") or i.get("aria-labelledby") or i.get("id") in page.labels_for):
            E("access", f"A form field has no label (name={i.get('name', '?')}).")
            break
    if css and not re.search(r":focus", css):
        W("access", "No :focus or :focus-visible style; keyboard users cannot see where they are.")
    if re.search(r"animation\s*:|@keyframes|transition\s*:", css) and "prefers-reduced-motion" not in css:
        W("access", "The page animates but never checks prefers-reduced-motion.")
    if re.search(r"outline\s*:\s*(none|0)\b", css) and not re.search(r":focus-visible", css):
        W("access", "outline is removed without a :focus-visible replacement.")
    I("access", "not checkable here: colour contrast, tap target size, reading order, zoom to 200%")

    # ---------------- speed proxies
    size = len(raw.encode("utf-8"))
    if size > 300_000:
        W("speed", f"index.html is {size // 1000} kB; inline images are probably too large.")
    else:
        I("speed", f"index.html is {size // 1000} kB")
    blocking = [s["src"] for s in page.scripts if s["src"] and s["in_head"] and not (s["defer"] or s["async"] or s["module"])]
    if blocking:
        W("speed", f"{len(blocking)} script(s) in <head> block rendering; add defer.")
    ext_scripts = [s["src"] for s in page.scripts if urlparse(s["src"]).scheme in ("http", "https")]
    if ext_scripts:
        W("speed", f"{len(ext_scripts)} script(s) from other sites: {', '.join(ext_scripts[:3])}")
    fonts = [h for h in page.rels.get("stylesheet", []) if "fonts.googleapis.com" in h]
    for f in fonts:
        if "display=swap" not in f:
            W("speed", "Google Fonts is loaded without display=swap; text stays invisible while fonts load.")
        if f.count("family=") > 2:
            W("speed", f"{f.count('family=')} font families; two is plenty.")
    if fonts and not page.rels.get("preconnect"):
        W("speed", "Fonts load from another site with no preconnect hint.")
    for i in page.imgs:
        if not (i.get("width") and i.get("height")):
            W("speed", "An image has no width and height, so the layout jumps when it loads.")
            break
    I("speed", "not checkable here: real load time, layout shift, responsiveness; these need Lighthouse in a browser")

    # ---------------- report
    errors = warns = 0
    for area in out:
        if a.area and area != a.area:
            continue
        rows = out[area]
        print(f"\n{names[area]}")
        if not [r for r in rows if r[0] != "info"]:
            print("  ok")
        for level, msg in rows:
            print(f"  {level:<6} {msg}")
            errors += level == "ERROR"
            warns += level == "WARN"
    print(f"\n{errors} error(s), {warns} warning(s).")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
