---
name: token-diet
description: Apply frugal token settings to Claude, Codex, Hermes.
version: 0.2.0
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

## Agent must (do not skip)

Run from this directory, via `terminal`, in this order. Do not jump to `--yes`.

1. **Measure** — `./scripts/measure.sh`. Record `verdict=already-dieted` vs `needs-apply`.
2. **Dry-run** — `./scripts/apply.sh` or `./scripts/apply.sh --dry-run`. Exit `3` means changes are pending (not a crash). Show the user **every** `would-change` line. Exit `0` + `would-change=0` means already dieted; stop.
3. **Approve** — stop if they do not approve. Do **not** pass `--yes` yourself. Do not run `rtk init` yourself.
4. **Apply** — only after they say yes: `./scripts/apply.sh --yes`.
5. **RTK (optional)** — only if measure shows `claude.rtk_hook` missing **and** `rtk` is on PATH **and** they asked: `./scripts/apply.sh --yes --rtk`. The script probes `rtk init --help`; it will not pass `--auto-patch` unless that rtk lists it.
6. **Verify** — `./scripts/measure.sh` again. Success = no `drift`/`missing` on targets that exist. Then `./scripts/apply.sh --dry-run` → `would-change=0`, exit 0.
7. **Rollback** — if they ask: `./scripts/rollback.sh` (dry-run) then `--yes`.

`--target claude|codex|hermes` limits scope. `TOKEN_DIET_HOME=/tmp/fake` redirects all homes (tests).

## Prerequisites

- `python3` (3.9+).
- Optional CLIs: `claude`, `codex`, `hermes`, `rtk`. Missing CLIs are skipped.
- Write access to `~/.claude`, `~/.codex`, `~/.hermes` only when the user passes `--yes`.

## How to Run

```
./scripts/measure.sh
./scripts/apply.sh
./scripts/apply.sh --dry-run
./scripts/apply.sh --yes
./scripts/rollback.sh --yes
```

Default for apply/rollback is dry-run. `--yes` writes. Each overwritten file gets a sibling `*.bak-token-diet` (first backup is kept). Dry-run with pending changes exits 3 (CI-friendly).

## What it changes

| Target | Change | Idempotent when |
|---|---|---|
| Claude `settings.json` `env` | effort=medium, subagent=sonnet, MAX_MCP_OUTPUT_TOKENS=20000 | values already match (other keys kept) |
| `~/.claude/agents/{implementer,researcher,reviewer}.md` | create if missing | file exists |
| `~/.claude/CLAUDE.md` | append template | already contains Token diet / Token disiplini |
| Codex `config.toml` effort | `ultra`/`xhigh`/`max` → `high` | already high/medium/low |
| `~/.codex/{worker,reviewer}.config.toml` | create overlays (not `[profiles.*]`) | file exists |
| `~/.codex/AGENTS.md` | append template | marker present |
| Hermes `config` via CLI | reasoning medium, tier normal, background_review false, tool_output 20k/800, compress protect_last_n=10 + in_place + prune 48k, cache 1h, tool_search 5%, personality concise | `hermes config get` already equals target; **unknown keys skipped** (old Hermes) |
| `~/.hermes/SOUL.md` | append Delege-önce | marker present |

## Pitfalls

- Protected instruction files (`CLAUDE.md`, `AGENTS.md`) may block agent writes. If apply cannot write, give the user `./scripts/apply.sh --yes` to run in their own terminal.
- Codex 0.147+ errors if `[profiles.worker]` is inside `config.toml`. This skill only writes overlay files. Overlay `model` is commented; friends must set a cheap worker or they inherit the expensive default.
- Do not run `rtk init` unless asked (`--rtk`). It patches Claude hooks; existing Stop/Notification hooks must stay.
- `hermes config set` talks to the real Hermes home even if `TOKEN_DIET_HOME` is set. Tests pass `--skip-hermes-cli` or a stub `HERMES_BIN`. Never point `--yes` at a live Hermes config in a test.
- Auxiliary *model* pinning is host-specific (Grok vs Flash vs Haiku). This package does not pin aux models.
- Claude/Codex subscription OAuth must stay on the native CLI. No `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL`.

## Verification

- `./scripts/apply.sh --dry-run` on an already-dieted machine prints `would-change=0` and exits 0.
- `tests/test_token_diet.sh` applies in a temp HOME, checks files, proves unknown-key skip, proves idempotency, then rollback. Exit 0 required.
