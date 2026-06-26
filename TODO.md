# cli-hub — TODO

Open items, roughly by priority. Guiding principle: **keep it simple and
comfortable for the user** — automatic by default, tiny command surface,
no hardcoded tools, no bound search engine, zero network at runtime.

## Release / infra
- [ ] **Fix ClawHub auto-publish auth.** The workflow now runs `clawhub sync --all`
  (the removed `--yes` flag is gone) but fails with `Not logged in`. The
  `CLAWHUB_TOKEN` repo secret is invalid for clawhub v0.23. Action: run
  `clawhub login` locally to see the current auth, then refresh the secret
  (repo Settings → Secrets → `CLAWHUB_TOKEN`). Note: `npx skills add
  dull-bird/cli-hub` installs straight from GitHub and is unaffected.

## UX / docs
- [ ] **Shrink the perceived command surface.** ~13 commands exist, but a user
  only ever needs `install-hooks` (once) and `flag`/`--off`. Add a "you only
  need these" callout at the top of SKILL.md / README, and mark the rest as
  automatic/internal.
- [ ] **Add a `prune` command for registry hygiene.** `discover --scan` (or an old
  full scan) registers hundreds of system binaries. Add
  `cli-registry.py prune` to drop entries that are NOT surfaced, NOT in the KB,
  and live outside `$HOME` (system dirs). (Dev machine currently has ~274
  mostly-noise entries from an early full scan.)

## Maybe later
- [ ] **External (non-session) reminders.** Deferred — we chose in-session reminders
  only. If wanted: a cron runs `skills-check --search --json` and pipes the
  result to the user's own channel (email/Feishu). cli-hub emits the data, not
  the channel (provider-agnostic).
- [ ] **Rename?** Keeping `cli-hub` for now. `clik` is taken (PyPI CLI-building
  library + crowded `clik*` namespace + unsearchable). Only revisit with a
  full collision check (npm / PyPI / skill registries / GitHub).
- [ ] **Improve PreToolUse hint parsing.** `_parse_subcommands` sometimes grabs odd
  tokens (e.g. the opencli hint listed "violations, wait, connectivity").
  Tighten the parser if hint quality matters.
- [ ] **(No action) skills-check version match.** Skills rarely declare CLI-version
  compatibility, so a CLI↔skill version match isn't expressible — we only
  record the skill's own version. Documented here so future-me doesn't retry.

## Done (this session, on master)
- Proactive Claude Code hooks: UserPromptSubmit manifest + PreToolUse usage hint;
  opt-in `flag`; commands `non-standard` / `hint` / `autodiscover` /
  `skills-check` / `skill-pending`; `install-hooks.py`.
- Researched, collision-checked descriptions for mmx / opencli / kimi / codex
  (removed maintainer tools from the built-in KB).
- Incremental autodiscover + light extraction + anti-flood (small deliberate
  install auto-surfaces; a big batch is registered and listed as candidates).
- Daily `check-stale` refresh that preserves curated descriptions; once-only
  "installable skill" reminder to the user.
- READMEs rewritten (EN + 中文); GitHub Pages landing site
  (https://dull-bird.github.io/cli-hub/).
