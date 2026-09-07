# token-diet

Frugal, shareable settings for **Claude Code**, **Codex CLI**, and **Hermes Agent**.
Chief plans. Workers do. No OAuth proxies. No host-specific gateways.

Paylaşılan, hesaplı ayar paketi. Şef planlar, işçiler yapar. Abonelik OAuth'u proxy'den geçirmez.

## Install

```bash
git clone <this-repo> token-diet
cd token-diet
./scripts/measure.sh          # read-only
./scripts/apply.sh            # dry-run (default)
./scripts/apply.sh --yes      # write, with *.bak-token-diet
./scripts/rollback.sh --yes   # restore backups
```

Or tell your agent: "Read SKILL.md in this folder and apply token-diet (dry-run first)."

## What it does

1. **Instructions** — appends a short "delegate-first / terse / YAGNI" block to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.hermes/SOUL.md` if a token-diet marker is not already there.
2. **Settings** — Claude env: effort medium, subagent sonnet, MCP output 20k. Codex: cap `ultra`/`xhigh` → `high`; add `worker`/`reviewer` overlay files (not `[profiles.*]`). Hermes: reasoning medium, self-review off, tool output 20k, cache 1h, concise. Unknown keys are skipped.
3. **Hook** — if `rtk` is installed and no hook exists, recommends `rtk init -g`. Runs it only with `--yes --rtk`.

Missing CLIs are skipped. Existing files that already match are left alone.

## What it never does

- Change your default model or API keys
- Disable MCP servers or skills
- Set `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL`
- Touch LiteLLM, 9Router, OmniRoute, netcup, ZOS
- Pin Hermes auxiliary models (those are host-specific)

## Agent for friends (Claude / Codex / Hermes)

Copy `templates/claude-agents/*.md` is automatic. After apply:

- Claude: `@implementer` (sonnet), `@researcher` (haiku, read-only), `@reviewer` (sonnet, no writes)
- Codex: `codex --profile worker` (low effort), `codex --profile reviewer` (read-only)

Set the worker `model` yourself if you want a specific cheap model — the overlay only sets effort/sandbox.

## Safety

| Mode | Flag | Writes? |
|---|---|---|
| dry-run | (default) | no |
| apply | `--yes` | yes, backup first |
| rollback | `--yes` | restores `*.bak-token-diet` |

First backup is kept. Re-apply is idempotent (`would-change=0` on a machine that is already dieted).

## Tests

```bash
./tests/test_token_diet.sh
```

Uses a temp `TOKEN_DIET_HOME`. Does not call live `hermes config set`.

## License

MIT
