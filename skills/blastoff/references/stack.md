# The stack this skill calls

Nothing here is bundled. Each item is someone else's project, installed from its own source at run
time, so the person always gets the current version. Last verified: 2026-11-12. These projects move
quickly: when a command fails, trust the tool's own `--help` and README over this file.

## Skill packs (markdown instructions for the agent)

### marketingskills
- **Source:** github.com/coreyhaines31/marketingskills (MIT)
- **Used for:** the product brief, site copy, site review, search and AI visibility, post planning.
- **Install (project-level, into `.claude/skills/`), on one line:**
  ```
  npx -y skills add coreyhaines31/marketingskills -a claude-code -y --copy -s product-marketing competitor-profiling customer-research pricing site-architecture copywriting cro offers seo-audit ai-seo schema content-strategy social launch
  ```
- **List everything in the pack:** `npx -y skills add coreyhaines31/marketingskills --list`
- **How it fits:** its `product-marketing` skill writes `.agents/product-marketing.md`, and every
  other skill in the pack reads that file first. This skill relies on the same file.
- **Other skills in the pack worth offering when relevant:** `cold-email`, `prospecting`,
  `directory-submissions`, `emails`, `customer-research`, `competitors`,
  `sales-enablement`, `lead-magnets`, `video`, `image`.

| Stage | Skill to call |
|---|---|
| Brief | `product-marketing` (its auto-draft from codebase path) |
| Market research for the brief | `competitor-profiling`, `customer-research`, `pricing` |
| Site sections | `site-architecture` |
| Site design and build | `frontend-design` (from anthropics/skills, below) |
| Site words | `copywriting`, then `cro` to review |
| Offer wording | `offers` |
| Search and AI search, at build time | `ai-seo` content patterns, `schema`, plus `seo` from web-quality-skills |
| Search and AI search, audit | `seo-audit`, `ai-seo`, `schema`, plus `seo-geo` and the web-quality pack |
| Post plan | `content-strategy` |
| Post drafts, profile text | `social` |
| Launch day, if self-serve | `launch` |

### anthropics/skills
- **Source:** github.com/anthropics/skills (frontend-design and webapp-testing are Apache-2.0)
- **Used for:** `frontend-design` designs and builds the site so it does not look templated.
  `webapp-testing` drives a local browser with Playwright so the coordinator can look at the
  built page at desktop and phone widths.
- **Install:**
  ```
  npx -y skills add anthropics/skills -a claude-code -y --copy -s frontend-design webapp-testing
  ```
- **Note:** `webapp-testing` needs Python Playwright and a browser (`pip install playwright`, then
  `playwright install chromium`). If the person does not want that installed, skip the browser
  look and have them open `site/index.html` themselves.

### addyosmani/web-quality-skills
- **Source:** github.com/addyosmani/web-quality-skills (MIT)
- **Used for:** building and auditing the site to Lighthouse-era practice. `seo`,
  `accessibility` and `performance` are applied while building; `web-quality-audit`,
  `core-web-vitals` and `best-practices` are used by the site-auditor agent.
- **Install:**
  ```
  npx -y skills add addyosmani/web-quality-skills -a claude-code -y --copy -s web-quality-audit seo accessibility performance core-web-vitals best-practices
  ```
- **Notes:** a real Lighthouse run needs Chrome or Chromium on the machine. The pack's static
  analyzer (`web-quality-audit/scripts/analyze.sh`) needs bash and `jq`; skip it if either is
  missing, since `site_check.py` covers the same ground.

### AgriciDaniel/claude-seo (one skill, plus an optional plugin)
- **Source:** github.com/AgriciDaniel/claude-seo (MIT)
- **Used for:** `seo-geo` is the AI search audit: which crawlers do what, what makes a passage
  quotable, what is myth. It is kept current against Google's and the AI vendors' own guidance.
- **Install the one skill:**
  ```
  npx -y skills add AgriciDaniel/claude-seo -a claude-code -y --copy -s seo-geo
  ```
- **Do not install its other skills this way.** `seo-technical`, `seo-page` and `seo-schema`
  call scripts that only exist when the project is installed as a plugin, and its `seo` and
  `seo-audit` share names with skills from other packs.
- **The full plugin, optional, for a deep audit of the live site:** the person types
  `/plugin marketplace add AgriciDaniel/claude-seo` and
  `/plugin install claude-seo@agricidaniel-claude-seo` in Claude Code. Plugin skills are
  namespaced, so they do not collide.

### vercel-labs/agent-skills
- **Source:** github.com/vercel-labs/agent-skills
- **Used for:** `web-design-guidelines` audits the page against Vercel's Web Interface
  Guidelines, which it fetches fresh each time, so it needs web access.
- **Install:**
  ```
  npx -y skills add vercel-labs/agent-skills -a claude-code -y --copy -s web-design-guidelines
  ```

### Where the packs disagree
`llms.txt`: marketingskills treats it as worth having for non-Google engines; claude-seo and
web-quality-skills call it optional with no confirmed effect. This skill takes the cautious
reading: write a short one because it is cheap, never count it as an SEO measure, never fail a
check for lacking it.

### postiz-agent
- **Source:** github.com/gitroomhq/postiz-agent (AGPL-3.0)
- **Used for:** scheduling posts to LinkedIn, Instagram and other channels through Postiz.
- **Install:**
  ```
  npx -y skills add gitroomhq/postiz-agent -a claude-code -y --copy
  npm install -g postiz
  ```
- **Auth:** the person sets `POSTIZ_API_KEY` in their own terminal (Postiz, Settings, Developers,
  Public API), or runs `postiz auth:login`. For a self-hosted Postiz they also set
  `POSTIZ_API_URL`.
- **Prove it works:** `postiz integrations:list`
- **Posting:** follow the installed `postiz` skill; it documents `postiz posts:create` and media
  upload. Keep a person in the loop for every publish.
- **Alternative without the CLI:** Postiz also runs a hosted connector at
  `https://mcp.postiz.com/mcp-oauth-dynamic`. Check `claude mcp add --help` for the current syntax
  before adding it.

## Tools (running software)

### Sellbird
- **Source:** github.com/ethanplusai/sellbird (AGPL-3.0; formerly "Harvey")
- **Used for:** outbound. See `sellbird.md` for the full sequence.
- **Install:** clone into `tools/sellbird`, `python -m venv .venv`, `pip install -e .`
- **License note:** AGPL means it is fine to run and to call. Do not copy its code into the
  person's own product.

### Postiz (the service)
- **Source:** postiz.com, or self-host from github.com/gitroomhq/postiz-app (AGPL-3.0)
- **Used for:** the one place posts are scheduled from. The hosted service handles each platform's
  sign-in flow; self-hosting means the person applies for each platform's developer access, which
  is not worth it for one founder.

### Claude Code's built-in tools
- **Explore agent:** read-only codebase search, used for the capability inventory.
- **Artifact tool:** publishes one HTML file to a private page on claude.ai. Used for the site
  preview and for publishing the hub. It needs a session signed in with a claude.ai account on a
  paid plan, in the CLI or desktop app; if it is not available, the skill falls back to opening
  files locally and to publishing the hub from the Claude app.

### skills CLI
- **Source:** the `skills` package on npm, run as `npx skills`
- **Used for:** installing the packs above. Useful flags: `-a claude-code` (target agent),
  `-s <names>` (pick skills), `-y` (no prompts), `--copy` (copy files, no symlinks, safest on
  Windows), `-g` (install for every project instead of this one), `--list`.

## Services the person signs up for themselves

The skill never creates these. It tells the person what each is for and waits.

| Need | Options | Notes |
|---|---|---|
| Domains | any registrar | Two: the main one and a sending one |
| Sending mailbox | Google Workspace, Microsoft 365, any SMTP/IMAP | Workspace is the path Sellbird documents best |
| Warmup | any warmup service | Sellbird's docs link TrulyInbox with an affiliate link |
| Email verifier | Reoon, ZeroBounce, Hunter | Free tiers exist; needed before anything sends |
| Static hosting | Cloudflare Pages, Netlify, GitHub Pages | Free tiers are enough for one page |
| Booking link | any scheduler | Cal.com's open code now lives on as Cal.diy (MIT) if they want to self-host |
| Social scheduler | Postiz | See above |

## If the person already has their own skills

Prefer a more specific installed skill over the general one for the same job: a dedicated LinkedIn
post or profile skill over `social`, a house proposal or brand skill over generic copy, a
frontend-design skill for the site's look. Check the available skills list at the start of each
stage.

## Swapping a layer

Each layer has one contract with the rest:

- **Brief:** anything that keeps `.agents/product-marketing.md` current.
- **Scheduler:** anything that can post; update `.launchpad/posts.json` statuses.
- **Outbound:** anything that yields replies; write them to `.launchpad/leads.json`.
- **Hub:** reads only `.launchpad/hub-sync.json`.
