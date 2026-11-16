# Blastoff

A Claude Code skill that takes a product you have already built and sets up what it needs to
sell online: a website, a LinkedIn and Instagram presence, cold outbound, paid ads planned and
drafted for you to launch, and a small hub to track leads and posts.

It does not reinvent any of that. It asks a few questions, builds a checklist that fits your
answers, then installs and drives existing open-source skills and tools in the right order. You
keep every decision that spends money, uses your name or reaches a customer.

## Status

Early, and honest about it.

| | |
|---|---|
| The scripts (tracker, planner, site checker, seal) | 36 self-tests pass on Windows (Python 3.12). The workflow in this repo runs them on Linux, macOS and Windows on every push; check the Actions tab for the current result |
| Every `npx skills add` install command in the skill | Run in a clean folder on 12 Nov 2026 |
| The claude-ads install (paid ads) | **Not run.** Its installer writes to your real global `~/.claude`, so it was checked against the v2.1.0 installer and uninstaller source on 15 Nov 2026 but not executed |
| The Sellbird commands | Checked against Sellbird's own command-line help on 12 Nov 2026 |
| The skill driven by Claude Code, end to end | **Not yet run.** `skills/blastoff/evals/` has seven cases to run it |
| The four agents and their tool limits | Written to Claude Code's subagent docs; not yet run |

The projects this calls change often. When a command fails, the tool's own `--help` wins over
this repo.

## Install

```
npx skills add naman113/blastoff -a claude-code -g -y
```

That puts the skill in `~/.claude/skills/blastoff`. Then check the scripts work on your machine:

```
python ~/.claude/skills/blastoff/scripts/selftest.py
```

You need git, Python 3.9 or newer and Node.js 18 or newer. Cold outbound also needs Python 3.11
or newer and the Claude Code CLI signed in, because Sellbird runs on it. Paid ads work best with
Python 3.11 or 3.12, which claude-ads' own helpers need; without it they install as skills only.

## Use

Open a new, empty folder next to your product's repo in Claude Code (not the repo itself) and say:

> launch my product

It starts with six questions, one at a time:

1. What the product is called and where its code is
2. How people buy it: by themselves, or after talking to you
3. Who buys it: small businesses, teams in larger companies, or consumers
4. Which channels you want: website, LinkedIn, Instagram, X, cold email, paid ads
5. What you already have: a domain, a live site, a booking link, a LinkedIn page, ad accounts
6. The addresses of whatever you have

From those it builds your checklist and shows it to you before anything is installed. A consumer
product gets no cold email. A product with a live site gets an audit, not a rebuild. Choosing
cold email or paid ads without a site adds the site, and says why. Ad accounts you already run
get a read-only audit. The checklist is written to
`LAUNCH_GUIDE.md` with the how-to for every step that only you can do.

Then it works through the plan, stopping for your go-ahead between stages:

| Stage | What happens | Built on |
|---|---|---|
| Discovery | A capability list built from your code, each item traced to files and marked shipped, partial or stub. The README is only a cross-check. | Claude Code's Explore agent |
| Brief | Market research and a product brief with two or three positioning angles. You answer at most five questions it cannot look up. | [marketingskills](https://github.com/coreyhaines31/marketingskills) |
| Website | One self-contained page, written and built by skills with search and AI search practice built in, checked mechanically, then audited by an agent that did not build it. | marketingskills, [anthropics/skills](https://github.com/anthropics/skills), [web-quality-skills](https://github.com/addyosmani/web-quality-skills), [claude-seo](https://github.com/AgriciDaniel/claude-seo), [agent-skills](https://github.com/vercel-labs/agent-skills) |
| Social | Profile text, two weeks of drafted posts, scheduling of the ones you name. | marketingskills, [Postiz](https://github.com/gitroomhq/postiz-agent) |
| Outbound | Prospect finding, cold email from your own mailbox, reply handling. You approve every email. | [Sellbird](https://github.com/ethanplusai/sellbird) |
| Paid ads | An ads profile, a plan with competitors and a test budget, a landing-page audit, ad copy and briefs, an audit of accounts you already run, and a drafted launch plan. You open the accounts, set the budget and turn campaigns on. | [claude-ads](https://github.com/AgriciDaniel/claude-ads), pinned to v2.1.0 |
| Hub | A Claude artifact with your pipeline, content calendar and checklist. | `assets/hub.html` in this repo |

Nothing from those projects is bundled here. Each is installed from its own source when the
skill runs, under its own license. claude-ads is the one that installs globally: its installer
puts its skills, 25 agents and a Python environment in your `~/.claude`, for every project on
the machine. Claude Code checks for name clashes and asks you before running it, and
`references/stack.md` has the uninstall command and a plugin install you can use instead.

## What it will not do

- Create accounts, buy domains, change DNS or sign in anywhere
- Approve or send an email, publish a post you have not named, or turn on any autopilot
- Set or change an ad budget, touch billing, turn a campaign on, or run any claude-ads command
  with `--apply`: launches and optimizations are drafts for you to make in the ad platform
- Ask for, read or print keys, passwords or tokens
- Change anything in your product's repo
- State a capability your code does not have: the site checker fails the build if the page
  mentions one

## Four agents

The work is split by what each agent may touch.

| Agent | Does | Cannot |
|---|---|---|
| launch-coordinator | Plan, installs, discovery, brief, checks, paid-ads drafts, talking to you | Use Sellbird's connector, apply any ad change |
| content-writer | Writes and builds the site, posts and profile text through skills | Run commands, use the web, publish |
| site-auditor | Audits the build and the live site, writes `site/audit.md` | Fix what it finds |
| outbound-operator | Reads Sellbird: morning check, replies, health, pause | Approve, send, spend, resume |

Some of those limits are tool restrictions and some are instructions. `launchpad.py seal` makes
the instructed ones checkable: it records every file before work is handed to an agent and lists
what changed afterwards, in the workspace and in your product repo.

## Test it

The scripts:

```
python skills/blastoff/scripts/selftest.py
```

The skill itself, driven by Claude Code (these are real, billed model runs):

```
cd skills/blastoff
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold
```

The seven cases cover the intake and tailored checklist, an intake that picks paid ads,
capability discovery from code, catching a claim the code does not back, an audit that reports
without fixing, refusing to approve email or switch on autopilot, and refusing to set an ad
budget, launch a campaign or apply an optimization.

## Layout

```
skills/blastoff/
├── SKILL.md              the playbook Claude Code follows
├── references/           discovery, the stack it calls (claude-ads included), Sellbird, the hub
├── assets/
│   ├── steps.json        every step, who does it, how, and when it is in a plan
│   ├── hub.html          the hub page
│   └── agents/           the four agent definitions
├── scripts/              tracker and planner, site checker, preflight, self-test
└── evals/                test cases with a small sample product
```

## Credits

Blastoff is glue. The work is done by the projects linked above and their authors.

## License

MIT. See [LICENSE](LICENSE).
