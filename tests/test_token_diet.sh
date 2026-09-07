#!/usr/bin/env bash
# Isolated apply / idempotency / rollback / unknown-key skip / clean-HOME test.
# Never touches the real $HOME configs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/scripts/token_diet.py"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

run_py() {
  # usage: run_py EXPECTED_RC args...
  local want="$1"; shift
  set +e
  OUT="$(python3 "$PY" "$@" 2>&1)"
  RC=$?
  set -e
  if [ "$RC" -ne "$want" ]; then
    fail "exit $RC want $want from: $*
$OUT"
  fi
}

# ---------------------------------------------------------------------------
# A. TOKEN_DIET_HOME sandbox
# ---------------------------------------------------------------------------
TMP="$(mktemp -d /tmp/token-diet-test.XXXXXX)"
export TOKEN_DIET_HOME="$TMP"
export TOKEN_DIET_SKIP_HERMES_CLI=1
cleanup() { rm -rf "$TMP" "${CLEAN:-}" "${HTMP:-}" "${STUB:-}"; }
trap cleanup EXIT

mkdir -p "$TMP/.claude" "$TMP/.codex" "$TMP/.hermes"

run_py 3 apply --force --skip-hermes-cli --target all
echo "$OUT" | grep -q 'would-change=' || fail "dry-run missing summary"
echo "$OUT" | grep -qE 'would-change=[1-9]' || fail "empty home dry-run should pending: $OUT"
test ! -f "$TMP/.claude/settings.json" || fail "dry-run wrote settings.json"
test ! -f "$TMP/.claude/CLAUDE.md" || fail "dry-run wrote CLAUDE.md"
test ! -f "$TMP/.codex/worker.config.toml" || fail "dry-run wrote worker overlay"
test ! -f "$TMP/.hermes/SOUL.md" || fail "dry-run wrote SOUL.md"
pass "dry-run writes nothing and exits 3"

run_py 3 apply --dry-run --force --skip-hermes-cli --target all
test "$RC" -eq 3
pass "explicit --dry-run also exits 3"

# seed a wasteful codex config + existing claude settings to merge
printf 'model = "gpt-test"\nmodel_reasoning_effort = "ultra"\n' > "$TMP/.codex/config.toml"
printf '%s\n' '{"permissions":{"allow":["Read"]},"env":{"KEEP_ME":"1"}}' > "$TMP/.claude/settings.json"
printf 'You are Hermes.\n' > "$TMP/.hermes/SOUL.md"
printf 'existing agents header\n' > "$TMP/.codex/AGENTS.md"

run_py 0 apply --yes --force --skip-hermes-cli --target all
echo "$OUT" | grep -q 'applied=' || fail "apply missing summary"
test -f "$TMP/.claude/settings.json" || fail "settings.json missing"
python3 - "$TMP" <<'PY'
import json, sys
from pathlib import Path
home = Path(sys.argv[1])
d = json.loads((home / ".claude/settings.json").read_text())
env = d["env"]
assert env["KEEP_ME"] == "1", env
assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "medium"
assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == "sonnet"
assert env["MAX_MCP_OUTPUT_TOKENS"] == "20000"
assert d["permissions"]["allow"] == ["Read"]
PY
test -f "$TMP/.claude/agents/implementer.md"
test -f "$TMP/.claude/agents/researcher.md"
test -f "$TMP/.claude/agents/reviewer.md"
grep -q 'Token diet' "$TMP/.claude/CLAUDE.md" || fail "CLAUDE snippet"
grep -q 'Token diet' "$TMP/.codex/AGENTS.md" || fail "AGENTS snippet"
grep -q 'existing agents header' "$TMP/.codex/AGENTS.md" || fail "AGENTS preserved"
grep -q 'model_reasoning_effort = "high"' "$TMP/.codex/config.toml" || fail "effort not capped"
grep -q 'model = "gpt-test"' "$TMP/.codex/config.toml" || fail "codex model preserved"
test -f "$TMP/.codex/worker.config.toml"
test -f "$TMP/.codex/reviewer.config.toml"
grep -q 'sandbox_mode = "read-only"' "$TMP/.codex/reviewer.config.toml"
grep -q 'codex --profile worker' "$TMP/.codex/worker.config.toml" || fail "worker usage comment"
grep -q 'model = "gpt-5.5"' "$TMP/.codex/worker.config.toml" || fail "cheap model example"
grep -q 'Token diet' "$TMP/.hermes/SOUL.md" || fail "SOUL snippet"
grep -q 'You are Hermes.' "$TMP/.hermes/SOUL.md" || fail "SOUL preserved"
test -f "$TMP/.claude/settings.json.bak-token-diet" || fail "settings backup"
test -f "$TMP/.codex/config.toml.bak-token-diet" || fail "codex backup"
pass "apply --yes wrote expected files and kept extras"

grep -q 'disallowedTools: Write, Edit' "$TMP/.claude/agents/researcher.md"
grep -q 'disallowedTools: Write, Edit' "$TMP/.claude/agents/reviewer.md"
grep -q 'model: haiku' "$TMP/.claude/agents/researcher.md"
grep -q 'model: sonnet' "$TMP/.claude/agents/implementer.md"
pass "agent templates"

run_py 0 apply --yes --force --skip-hermes-cli --target all
echo "$OUT" | grep -qE 'applied=0' || fail "second apply should apply=0: $OUT"
echo "$OUT" | grep -qE 'would-change=0' || fail "second apply should would-change=0: $OUT"
grep -q 'ultra' "$TMP/.codex/config.toml.bak-token-diet" || fail "first backup overwritten"
pass "idempotent re-apply; first backup kept"

run_py 0 apply --force --skip-hermes-cli
echo "$OUT" | grep -q 'would-change=0' || fail "dieted dry-run not zero: $OUT"
pass "dieted dry-run would-change=0 exit 0"

mout="$(python3 "$PY" measure --target all)"
echo "$mout" | grep -q 'verdict=already-dieted' || fail "measure verdict: $mout"
pass "measure already-dieted"

# rtk must not hardcode --auto-patch as the only argv
grep -q 'def rtk_init_cmd' "$PY" || fail "rtk_init_cmd missing"
if grep -n 'cmd = "rtk init -g --auto-patch"' "$PY"; then
  fail "hardcoded rtk --auto-patch still present"
fi
pass "rtk flags are probed, not hardcoded"

# ---------------------------------------------------------------------------
# B. Hermes stub: unknown keys skip, known keys apply (never the live CLI)
# ---------------------------------------------------------------------------
HTMP="$(mktemp -d /tmp/token-diet-hermes.XXXXXX)"
STUB="$(mktemp -d /tmp/token-diet-stub.XXXXXX)"
cat > "$STUB/hermes" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
LOG="${FAKE_HERMES_LOG:-/tmp/fake-hermes.log}"
if [[ "${1:-}" == "config" && "${2:-}" == "get" ]]; then
  case "${3:-}" in
    agent.reasoning_effort) echo high; exit 0 ;;
    agent.service_tier) echo normal; exit 0 ;;
    auxiliary.background_review.enabled) echo true; exit 0 ;;
    tool_output.max_bytes) echo 20000; exit 0 ;;
    tool_output.max_lines) echo 800; exit 0 ;;
    prompt_caching.cache_ttl) echo 1h; exit 0 ;;
    tools.tool_search.threshold_pct) echo 5; exit 0 ;;
    display.personality) echo concise; exit 0 ;;
    compression.*) echo "Unknown config key: $3" >&2; exit 1 ;;
    *) echo "Unknown config key: $3" >&2; exit 1 ;;
  esac
fi
if [[ "${1:-}" == "config" && "${2:-}" == "set" ]]; then
  printf '%s=%s\n' "${3:-}" "${4:-}" >> "$LOG"
  exit 0
fi
echo "unexpected: $*" >&2
exit 2
STUB
chmod +x "$STUB/hermes"
: > "$STUB/log"
mkdir -p "$HTMP/.hermes"
printf 'You are Hermes.\n' > "$HTMP/.hermes/SOUL.md"

set +e
HOUT="$(
  env -u TOKEN_DIET_SKIP_HERMES_CLI \
    TOKEN_DIET_HOME="$HTMP" \
    HERMES_BIN="$STUB/hermes" \
    FAKE_HERMES_LOG="$STUB/log" \
    python3 "$PY" apply --yes --force --target hermes 2>&1
)"
HRC=$?
set -e
[ "$HRC" -eq 0 ] || fail "hermes stub apply exit $HRC: $HOUT"
echo "$HOUT" | grep -q 'hermes.compression.protect_last_n' || fail "missing compression key row: $HOUT"
echo "$HOUT" | grep -qE 'hermes.compression.protect_last_n +skip' || fail "compression.protect_last_n not skipped: $HOUT"
echo "$HOUT" | grep -qE 'hermes.compression.in_place +skip' || fail "compression.in_place not skipped: $HOUT"
echo "$HOUT" | grep -qE 'hermes.compression.proactive_prune_tokens +skip' || fail "compression.prune not skipped: $HOUT"
echo "$HOUT" | grep -qE 'hermes.agent.reasoning_effort +applied' || fail "reasoning not applied: $HOUT"
echo "$HOUT" | grep -qE 'hermes.auxiliary.background_review.enabled +applied' || fail "background_review not applied: $HOUT"
grep -q 'agent.reasoning_effort=medium' "$STUB/log" || fail "stub did not set reasoning: $(cat "$STUB/log")"
grep -q 'compression.' "$STUB/log" && fail "stub must not set compression keys: $(cat "$STUB/log")"
pass "unknown Hermes keys skip; known keys apply (stub, not live CLI)"

# ---------------------------------------------------------------------------
# C. Clean HOME (friend-machine sim): no TOKEN_DIET_HOME, fake ~/.claude etc.
# ---------------------------------------------------------------------------
CLEAN="$(mktemp -d /tmp/token-diet-clean-home.XXXXXX)"
mkdir -p "$CLEAN/.claude" "$CLEAN/.codex" "$CLEAN/.hermes"
printf 'model = "gpt-test"\nmodel_reasoning_effort = "xhigh"\n' > "$CLEAN/.codex/config.toml"

clean_env() {
  env -u TOKEN_DIET_HOME -u CLAUDE_HOME -u CODEX_HOME -u HERMES_HOME -u HERMES_BIN \
    HOME="$CLEAN" TOKEN_DIET_SKIP_HERMES_CLI=1 "$@"
}

set +e
COUT="$(clean_env python3 "$PY" apply --force --skip-hermes-cli --target all 2>&1)"
CRC=$?
set -e
[ "$CRC" -eq 3 ] || fail "clean-home dry-run exit $CRC: $COUT"
test ! -f "$CLEAN/.codex/worker.config.toml" || fail "clean-home dry-run wrote overlay"
pass "clean HOME dry-run exits 3 and writes nothing"

set +e
COUT="$(clean_env python3 "$PY" apply --yes --force --skip-hermes-cli --target all 2>&1)"
CRC=$?
set -e
[ "$CRC" -eq 0 ] || fail "clean-home apply exit $CRC: $COUT"
echo "$COUT" | grep -qE 'applied=[1-9]' || fail "clean-home first apply should change: $COUT"
grep -q 'model_reasoning_effort = "high"' "$CLEAN/.codex/config.toml" || fail "clean-home effort"
test -f "$CLEAN/.codex/worker.config.toml" || fail "clean-home worker overlay"
test -f "$CLEAN/.claude/CLAUDE.md" || fail "clean-home CLAUDE.md"
test -f "$CLEAN/.hermes/SOUL.md" || fail "clean-home SOUL.md"
pass "clean HOME first apply writes"

set +e
COUT2="$(clean_env python3 "$PY" apply --yes --force --skip-hermes-cli --target all 2>&1)"
CRC2=$?
set -e
[ "$CRC2" -eq 0 ] || fail "clean-home second apply exit $CRC2: $COUT2"
echo "$COUT2" | grep -qE 'applied=0' || fail "clean-home second apply not 0: $COUT2"
echo "$COUT2" | grep -qE 'would-change=0' || fail "clean-home second would-change not 0: $COUT2"
pass "clean HOME second apply 0 changes"

# ---------------------------------------------------------------------------
# D. Rollback of TOKEN_DIET_HOME sandbox
# ---------------------------------------------------------------------------
run_py 0 rollback --yes --target all
grep -q 'ultra' "$TMP/.codex/config.toml" || fail "rollback did not restore ultra"
python3 - "$TMP" <<'PY'
import json, sys
from pathlib import Path
d = json.loads((Path(sys.argv[1]) / ".claude/settings.json").read_text())
assert "CLAUDE_CODE_EFFORT_LEVEL" not in d.get("env", {})
assert d["env"]["KEEP_ME"] == "1"
PY
test ! -f "$TMP/.claude/agents/implementer.md" || fail "agent not removed"
test ! -f "$TMP/.codex/worker.config.toml" || fail "worker overlay not removed"
grep -q 'You are Hermes.' "$TMP/.hermes/SOUL.md"
if grep -q 'Token diet' "$TMP/.hermes/SOUL.md"; then
  fail "SOUL snippet not rolled back"
fi
test ! -f "$TMP/.claude/CLAUDE.md" || fail "created CLAUDE.md not removed"
pass "rollback restored originals"

echo "ALL TESTS PASSED"
