# Sellbird: Stage 5 in full

Sellbird (github.com/ethanplusai/sellbird, AGPL-3.0) is an open-source outbound tool that runs on
the person's machine and thinks through their Claude plan by calling `claude -p`. It finds
companies, reads their websites for buying signals, finds a decision-maker, verifies one email
address, writes a short sequence, sends from the person's mailbox and drafts answers to replies.

Commands below were checked against Sellbird's CLI on 2026-11-12. The project ships changes most
days. If a command fails, run `sellbird <command> --help` and read `tools/sellbird/README.md`.

Sellbird ships its own `CLAUDE.md`, a setup guide written for Claude Code. Read
`tools/sellbird/CLAUDE.md` and `tools/sellbird/docs/` for detail on any step. Where it and this
skill's rules disagree (for example on who turns on autopilot), this skill's rules win.

## Contents

1. What Sellbird needs before it can send
2. Install and train
3. Signals
4. The connector (what Claude Code can and cannot do)
5. List-only run
6. Mailbox and first send
7. Daily running
8. When discovery does not fit

## 1. What Sellbird needs before it can send

| Need | Who | Without it |
|---|---|---|
| Python 3.11+, the `claude` CLI signed in | checked by preflight | Sellbird cannot run or think |
| A live product website | Stage 3 | Training has nothing to read |
| A mailbox on a separate sending domain, with SPF, DKIM, DMARC | person | Mail lands in spam, or the main domain is put at risk |
| 14 days of warmup on that mailbox | person | Cold mail from a new mailbox lands in spam |
| An email verifier key (Reoon, ZeroBounce or Hunter) | person | Every address stays a "guess" and nothing is ever sent |
| A postal address in the config | person | Sellbird warns on every run until the email footer has one |

Sellbird's thinking draws on the Claude plan's allowance for non-interactive use, which is a capped
monthly pool. `sellbird usage` shows what Sellbird has used. Mention this once so a cap is not a
surprise.

## 2. Install and train

`SB` below means the Sellbird command inside its own environment:
`tools/sellbird/.venv/bin/sellbird` on macOS and Linux, `tools\sellbird\.venv\Scripts\sellbird` on
Windows. Run Sellbird commands from `tools/sellbird`.

```bash
git clone https://github.com/ethanplusai/sellbird.git tools/sellbird
cd tools/sellbird
python3 -m venv .venv            # use the Python 3.11+ that preflight found
.venv/bin/pip install -e .
cp .env.example .env             # Windows: copy .env.example .env   (the person fills it in)
```

Do not run `python -m playwright install`: that is only for LinkedIn automation, which this skill
leaves off because it drives the person's LinkedIn login with a browser robot and puts their
account at risk.

`LP done out.install`.

Train on the live site:

```bash
SB train https://<live-site>
```

This crawls the site and writes `sellbird.local.yaml` (product, offer, ideal customer) plus
`skills/product_knowledge.md` and `skills/competitive_intel.md`. It makes several `claude -p`
calls. If it fails when launched from inside a Claude Code session, ask the person to run the same
command in their own terminal.

Then correct the result against `.agents/product-marketing.md`:

- Edit `sellbird.local.yaml` only, never the tracked `sellbird.yaml`.
- Set `product.offer` (entry offer, `booking_url`, meeting length), `icp` (industries, titles,
  size, geography), `persona`, and `compliance.postal_address` (ask the person for it).
- Rewrite `skills/product_knowledge.md` and `skills/competitive_intel.md` in buyer language. Every
  claim must trace to the repo or the brief.
- Leave `channels.email.require_approval: true` and `channels.linkedin.enabled: false`.

`LP done out.train`.

## 3. Signals

```bash
SB signals                 # lists every signal, what it costs, which are confirmed
```

Compare the list with the "Observable signals" section of the brief and recommend the ones that
show a company needs this product, with one line of why each. The person decides. When they have:

```bash
SB signals --confirm <CODE,CODE>     # or: --confirm free
```

Run the confirm command only on the person's explicit say-so, with the codes they chose. Then
`LP done out.signals`.

Sellbird's built-in signals lean toward selling marketing, web and booking services to local small
businesses (no website, unclaimed listing, running ads, no online booking, stale blog) plus tech
stack, open roles and funding. If almost none match the brief, say so and see section 8.

## 4. The connector

```bash
SB mcp install claude --print     # show the change without making it
SB mcp install claude             # shows the change, asks yes or no
```

Let the person answer the prompt. Do not pass `--yes`. The connector talks to Sellbird's running
dashboard, so its tools only answer while `sellbird dashboard` is running. The person may need to
reload Claude Code before the tools appear. `LP done out.mcp`.

What the connector allows, enforced by Sellbird in code:

| Claude Code can | Claude Code cannot |
|---|---|
| Read: `today`, `setup_status`, `stats`, `activity`, `usage`, `campaigns_list`, `prospects_list`, `companies_list`, `company_contacts`, `company_profile`, `conversations_list`, `outbox_list`, `signals_list`, `sending_status`, `company` | Approve or reject an email |
| Estimate a discovery run's cost: `discover_providers`, `discover_estimate` | Start a paid discovery or spend anything |
| Pause all sending: `sending_pause` | Resume sending |
| Suggest a first-email offer for the person to confirm | Change settings, keys or autopilot |

In this skill only the **outbound-operator** agent uses the connector, because what it returns
includes replies and website text written by strangers.

That boundary is the design, not a limitation to work around. Never try to reach the same actions
another way (the dashboard token, the database file, `SB outbox --approve`).

## 5. List-only run

Until a mailbox is connected nothing can send, so this is safe to run early.

```bash
SB discover --estimate            # shows what a run would cost; the default source is free
SB discover                       # OpenStreetMap, no account, about 100 records per query
```

`SB discover --providers` lists the paid sources and their prices. Only use one if the person asks,
names it, and has put its key in `.env`; keep `--max-spend` at its default of 1 dollar unless they
give a number.

Finding people and checking addresses happens inside Sellbird's loop. Ask the person to start it in
their own terminal and leave it for a few cycles:

```bash
SB run
```

Then export and review:

```bash
SB export --out ../../.launchpad/prospects.csv
SB companies --out ../../.launchpad/companies.csv    # every company and why it fits or was skipped
```

Show the person 30 rows of `prospects.csv` (name, title, company, website, score, email status) and
ask one question: would you call these people? If not, fix the brief, the ideal-customer settings
or the signals, and run it again. `LP done out.list` when they say the list is right.

If the export is empty or every address is a guess, the verifier key is missing or out of credit.

## 6. Mailbox and first send

All of this is the person's, in their own terminal:

```bash
SB warmup                         # free check of SPF, DKIM, DMARC, blocklists, domain age
SB gmail auth                     # or see docs/microsoft365.md; opens a browser sign-in
SB dashboard                      # prints a private link; do not read or repeat its token
SB run
```

Do not start sending until warmup has run 14 days and `SB warmup` comes back clean. Every email
then waits in the dashboard's Outbox for the person's approval. `LP done out.mailbox` and
`LP done out.approve` when they report each one done.

Autopilot (sending without approval) is the person's switch in the dashboard's settings. Never turn
it on, and if they ask about it, suggest approving several batches by hand first.

## 7. Daily running

- Sellbird's loop wakes every 15 minutes while `SB run` is running. It stops when the machine
  sleeps.
- Morning check: the **outbound-operator** agent reads Sellbird through the connector and reports
  what is waiting on the person. The coordinator does not read Sellbird itself.
- `SB status --check` shows pipeline state and checks the Claude CLI.
- `SB sending pause` (or the `sending_pause` tool) stops everything. Bounces above 5 percent make
  Sellbird pause itself.

## 8. When discovery does not fit

Sellbird finds companies through map listings and web search, and finds the decision-maker by
reading the company's own website. That works for small, owner-run businesses and poorly for large
companies, where the buyer is rarely named on the site. If the brief's buyer is a manager inside a
large company, or the need is not visible from outside:

- Say so plainly before the person spends two weeks on warmup expecting leads.
- Offer the other use: the person builds a small target list by hand, and Sellbird is used only for
  its writing rules, sending limits, reply handling and opt-out handling.
- Lean on Stage 4 (content and LinkedIn) and warm introductions as the main channels.
