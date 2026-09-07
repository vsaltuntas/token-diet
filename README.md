# token-diet

Shareable, host-agnostic diet for **Claude Code**, **Codex CLI**, and **Hermes Agent**.

Chief plans. Workers do. No OAuth proxies. No host-specific gateways.

Paylaşılan, hesaplı ayar paketi. Şef planlar, işçiler yapar. Abonelik OAuth'u proxy'den geçirmez.

## How it works / Nasıl çalışır

**Nasıl çalışır:** Bir kodlama ajanı her turda tüm konuşmayı modele yeniden gönderir; pahalı model her işi kendi yaparsa maliyet üstel büyür. token-diet üç şey yapar: (1) ajanın talimat dosyasına "pahalı model yalnız planlar ve kabul eder; kod/araştırma/test ucuz alt ajana gider; çıktı kısa" kuralını ekler, (2) reasoning seviyesini ve araç çıktısı boyutunu sınırlar, arka plan self-review'ı kapatır, (3) ucuz işçi/denetçi profilleri oluşturur. Önce ölçer, dry-run gösterir, onayla yazar, tek komutla geri alınır.

**How it works:** A coding agent re-sends the whole conversation every turn; if the expensive model does all the work, cost compounds. token-diet does three things: (1) appends a "chief plans and accepts; code/research/tests go to a cheap sub-agent; terse output" rule to your agent's instruction file, (2) caps reasoning effort and tool-output size, turns off background self-review, (3) creates cheap worker/reviewer profiles. Measure first, dry-run, apply on approval, roll back with one command.

## Install

```bash
git clone https://github.com/vsaltuntas/token-diet.git
cd token-diet
./scripts/measure.sh            # read-only
./scripts/apply.sh              # dry-run (default); exit 3 if changes pending
./scripts/apply.sh --dry-run    # same, explicit
./scripts/apply.sh --yes        # write, with *.bak-token-diet
./scripts/rollback.sh --yes     # restore backups
```

Or tell your agent: "Read SKILL.md in this folder and apply token-diet (dry-run first)."

## Measured on one real fleet (2026-09-06)

Not a promise for your machine. One 7-day window, Hermes Mac + Codex Mac + netcup workers, after this diet (plus MCP/skill cuts that **this package does not do**):

| What | Before | After |
|---|---|---|
| Hermes self-review (`auxiliary.background_review`) | ~$20 / week | $0 (off) |
| Reasoning tokens at `xhigh` | 8.4M | capped: chief `medium` / `high`, workers `low` |
| Cache-read per call | ~97k | ~62k |
| Hermes skill-index prompt | ~14k chars | ~11.7k chars |

Independent audit of the live Mac/netcup apply: **60 PASS / 0 FAIL**.

Your `./scripts/measure.sh` is the only number that matters on a new machine.

## Second measurement

The table above is the **pre-install** 7-day window (to 6 Sep 2026). A second measurement is the same method on the **7 days after** install (total tokens, cache-read per call, reasoning, estimated $). That before/after is what makes the claim checkable.

Read-only; queries `~/.hermes/state.db`; writes nothing:

```
./scripts/second_measure.sh
```

Post-install window closes **13 Sep 2026**. Until then the script still prints a partial `after` row. Put those numbers here when the window is complete — do not invent them.

## What it does

1. **Instructions** — appends a short "delegate-first / terse / YAGNI" block to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.hermes/SOUL.md` if a token-diet marker is not already there.
2. **Settings** — Claude env: effort medium, subagent sonnet, MCP output 20k. Codex: cap `ultra`/`xhigh` → `high`; add `worker`/`reviewer` overlay files (not `[profiles.*]`). Hermes: reasoning medium, self-review off, tool output 20k, cache 1h, concise. Unknown keys are skipped (old Hermes has no `compression.*` / `background_review` — skip is success, not error).
3. **Hook** — if `rtk` is installed and no hook exists, recommends `rtk init -g`. Runs it only with `--yes --rtk`. `--auto-patch` is passed only if *that* `rtk` lists it in `--help`.

Missing CLIs are skipped. Existing files that already match are left alone.

## What it never does

- Change your default model or API keys
- Disable MCP servers or skills
- Set `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` (no subscription OAuth proxy)
- Touch LiteLLM, 9Router, OmniRoute, netcup, ZOS
- Pin Hermes auxiliary models (those are host-specific)
- Pool or share OAuth credentials
- Invent a Codex `config.toml` if you do not have one

## Codex worker (cheap model is yours)

Apply writes `~/.codex/worker.config.toml` and `~/.codex/reviewer.config.toml`. It does **not** put `[profiles.*]` inside `config.toml` (Codex 0.147+ rejects that).

```bash
codex --profile worker      # low effort; inherits default model unless you set one
codex --profile reviewer    # read-only sandbox
```

If you leave `model` unset, "low effort" still runs on your (often expensive) default model. Uncomment and pick a cheap worker in the overlay:

```toml
# ~/.codex/worker.config.toml
# model = "gpt-5.5"    # example — use whatever cheap worker you actually have
model_reasoning_effort = "low"
```

## Agent for friends (Claude / Codex / Hermes)

Copy of `templates/claude-agents/*.md` is automatic. After apply:

- Claude: `@implementer` (sonnet), `@researcher` (haiku, read-only), `@reviewer` (sonnet, no writes)
- Codex: `codex --profile worker`, `codex --profile reviewer`

## Safety

| Mode | Flag | Writes? | Exit |
|---|---|---|---|
| dry-run | (default) or `--dry-run` | no | `0` if already dieted; `3` if would-change>0 |
| apply | `--yes` | yes, backup first | `0` / `1` on error |
| rollback | `--yes` | restores `*.bak-token-diet` | `0` / `1` / `3` (dry-run) |

First backup is kept. Re-apply is idempotent (`would-change=0`, exit 0 on a machine that is already dieted).

## Tests

```bash
./tests/test_token_diet.sh
```

Uses a temp HOME (never the real `$HOME`). Proves: dry-run writes nothing and exits 3; apply writes; second apply is 0 changes; unknown Hermes keys skip; rollback restores. Does not call live `hermes config set`.

## License

MIT
