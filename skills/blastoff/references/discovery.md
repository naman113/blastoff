# Capability discovery from the codebase

Everything this skill later says about the product (site copy, posts, Sellbird's product knowledge)
must come from what the code actually does. READMEs and docs describe what the builder intended;
they go stale and they oversell. So build the inventory from code first and use the README only at
the end, as a cross-check.

## Output

Write `.launchpad/capabilities.md`. One row per capability, in the user's words, not the code's.

```markdown
# Capabilities: <product>
Built from <repo path(s)> at commit <short hash> on <date>.

| Capability | What a user can do | Evidence | Status |
|---|---|---|---|
| Recurring invoices | A bookkeeper sets an invoice to send itself every month | api/invoices/recurring.py, jobs/send_recurring.py, tests/test_recurring.py | Shipped |
| Late-payment reminders | Choose when overdue clients get a reminder | ui/reminders/RuleForm.tsx (form only, save handler is a TODO) | Stub |

## Facts that help a sale
- Multi-tenant: yes (tenant_id on every model, models/base.py)
- Sign-in: email and password only (auth/); no single sign-on found

## In the README but not found in code
- "Cash-flow forecasting"

## Not in this repo (stated by the owner)
- Onboarding done by hand: importing a new client's old invoices
```

## Status, and what earns it

| Status | Rule |
|---|---|
| Shipped | Reachable from a real entry point, with real logic behind it. A test or deployment config that exercises it raises confidence. |
| Partial | Works for some cases; the code shows clear limits (one provider, one file type, hard-coded values). Say what the limit is. |
| Stub | The surface exists but the logic is a TODO, a mock or a fixed response. |
| Hidden | Built, but behind a feature flag or config that is off by default. |
| Claimed only | Mentioned in README or docs; no code found. |

Only **Shipped** rows may be stated as fact in public copy. **Partial** rows may be mentioned with
their limit, if the person agrees. Nothing else is mentioned.

## Method

1. **Explore without filling the main context.** Use Claude Code's built-in Explore subagent for
   the reading; it is read-only and built for this. On a large repo, send one pass per area
   (backend, frontend, jobs, integrations) and merge the results. Record the commit hash so the
   inventory can be refreshed later with a diff instead of a full re-read. If the folder is not
   a git repository, write "no commit: not a git repository" and the date instead.
2. **Map the surface before the depth.** Capabilities live where a user or another system touches
   the product:
   - routes, controllers, API handlers, GraphQL schema
   - pages, screens, navigation menus, forms
   - command-line commands
   - scheduled jobs, queues, workers, webhooks
   - database models and migrations (what the product remembers is what it manages)
   - roles and permissions (each role is a kind of user, and so a kind of buyer or champion)
   - third-party clients and the names of the settings they need
   - feature flags and per-tenant configuration
   - report, export and notification templates
3. **Trace each surface one level down.** A menu item is not a capability until its handler does
   real work. Follow route to handler to logic and stop when it is clearly real or clearly a stub.
4. **Use tests as evidence, not as the map.** A passing-looking test for a path is good support
   for Shipped. A capability with no test is not thereby a stub.
5. **Collect the facts that help a sale**, only where the code shows them: single or multi-tenant,
   hosting model, sign-in options, audit trail, languages, mobile or offline support, import and
   export formats, the integrations, and any limits written into the code.
6. **Translate, but do not upgrade.** Rename `sync_bank_feed` to "pulls in bank transactions".
   Do not turn it into "AI-powered finance automation". Benefits and promises belong in the brief, where
   they are marked as guesses until the market confirms them.
7. **Read the README and docs last.** List every claim there that the code does not support under
   "In the README but not found in code". That list is valuable to the owner in its own right.
8. **Ask the person one question:** what does the product include that is not in this repo? Other
   repos, hardware, set-up work, support, a human service. Add those under "Not in this repo
   (stated by the owner)". If there are more repos, run the same method on each.

## Limits to respect

- **Read only.** Do not run the product, install its dependencies, run its tests or migrations, or
  change any file in the repo.
- **No secrets.** Setting *names* are evidence of an integration; never open or print their
  values, `.env` files, key files or credentials.
- **No client data.** Tenant names, seed data, sample records and deployment notes prove a
  capability is in real use. Record that fact ("deployed for one tenant") without the name or the
  data, and keep names out of every public output until the person approves each one.
- **Implemented is not proven.** Code shows a feature exists, not that it works well in production
  or that buyers care about it. Say so when handing over the inventory.

## Keeping it current

When the person says the product changed, compare the repo's current commit with the one recorded
at the top of the file, read only what changed, and update the affected rows. Then check whether
the brief, the site or Sellbird's product knowledge cite a row whose status dropped.
