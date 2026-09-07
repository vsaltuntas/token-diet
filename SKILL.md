---
name: token-diet
description: Apply frugal token settings to Claude, Codex, Hermes.
version: 0.1.0
author: Volkan Heingart, Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [tokens, cost, claude-code, codex, hermes, frugal]
---

# token-diet

Shareable, host-agnostic diet for coding agents. It appends a "chief plans, workers do" rule, caps reasoning waste, and adds cheap-worker overlays. It does **not** touch MCP lists, default models, OAuth, proxies, LiteLLM, or any host-specific gateway.

## When to Use

- User says "token-diet kur", "apply token diet", or "cut token spend on Claude/Codex/Hermes".
- A friend cloned this folder and asked their agent to install it.

Don't use for: routing subscription OAuth through a proxy (ToS/ban), disabling MCP servers, changing the user's default model, or netcup/ZOS/LiteLLM cutovers.

## Prerequisites

- `python3` (3.9+).
- Optional CLIs: `claude`, `codex`, `hermes`, `rtk`. Missing CLIs are skipped.
- Write access to `~/.claude`, `~/.codex`, `~/.hermes` only when the user passes `--yes`.

## How to Run

From this directory, via `terminal`:

```
./scripts/measure.sh
./scripts/apply.sh
./scripts/apply.sh --yes
./scripts/rollback.sh --yes
```

Default for apply/rollback is dry-run. `--yes` writes. Each overwritten file gets a sibling `*.bak-token-diet` (first backup is kept).

## Procedure

1. Run `./scripts/measure.sh`. Record verdict (`already-dieted` vs `needs-apply`).
2. Run `./scripts/apply.sh` (dry-run). Show the user every `would-change` line.
3. Stop if they do not approve. Do not pass `--yes` yourself.
4. After approval: `./scripts/apply.sh --yes`.
5. Optional RTK hook: only if measure shows `claude.rtk_hook missing` and `rtk` is on PATH, ask, then `./scripts/apply.sh --yes --rtk`.
6. Re-run `./scripts/measure.sh`. Success = no `drift`/`missing` on targets that exist.
7. Rollback: `./scripts/rollback.sh` then `--yes`.

`--target claude|codex|hermes` limits scope. `TOKEN_DIET_HOME=/tmp/fake` redirects all homes (tests).

## What it changes

| Target | Change | Idempotent when |
|---|---|---|
| Claude `settings.json` `env` | effort=medium, subagent=sonnet, MAX_MCP_OUTPUT_TOKENS=20000 | values already match (other keys kept) |
| `~/.claude/agents/{implementer,researcher,reviewer}.md` | create if missing | file exists |
| `~/.claude/CLAUDE.md` | append template | already contains Token diet / Token disiplini |
| Codex `config.toml` effort | `ultra`/`xhigh`/`max` → `high` | already high/medium/low |
| `~/.codex/{worker,reviewer}.config.toml` | create overlays (not `[profiles.*]`) | file exists |
| `~/.codex/AGENTS.md` | append template | marker present |
| Hermes `config` via CLI | reasoning medium, tier normal, background_review false, tool_output 20k/800, compress protect_last_n=10 + in_place + prune 48k, cache 1h, tool_search 5%, personality concise | `hermes config get` already equals target; unknown keys skipped |
| `~/.hermes/SOUL.md` | append Delege-önce | marker present |

## Pitfalls

- Protected instruction files (`CLAUDE.md`, `AGENTS.md`) may block agent writes. If apply cannot write, give the user `./scripts/apply.sh --yes` to run in their own terminal.
- Codex 0.147+ errors if `[profiles.worker]` is inside `config.toml`. This skill only writes overlay files.
- Do not run `rtk init` unless asked (`--rtk`). It patches Claude hooks; existing Stop/Notification hooks must stay.
- `hermes config set` talks to the real Hermes home even if `TOKEN_DIET_HOME` is set. Tests pass `--skip-hermes-cli`. Never point `--yes` at a live Hermes config in a test.
- Auxiliary *model* pinning is host-specific (Grok vs Flash vs Haiku). This package does not pin aux models.
- Claude/Codex subscription OAuth must stay on the native CLI. No `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL`.

## Verification

- `./scripts/apply.sh` on an already-dieted machine prints `would-change=0`.
- `tests/test_token_diet.sh` applies in a temp HOME, checks files, proves idempotency, then rollback. Exit 0 required.
