#!/usr/bin/env bash
# Isolated apply / idempotency / rollback test. Never touches the real $HOME configs.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/scripts/token_diet.py"
TMP="$(mktemp -d /tmp/token-diet-test.XXXXXX)"
export TOKEN_DIET_HOME="$TMP"
export TOKEN_DIET_SKIP_HERMES_CLI=1
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

mkdir -p "$TMP/.claude" "$TMP/.codex" "$TMP/.hermes"

# --- empty home: dry-run must not write ---
out="$(python3 "$PY" apply --force --skip-hermes-cli --target all)"
echo "$out" | grep -q 'would-change=' || fail "dry-run missing summary"
test ! -f "$TMP/.claude/settings.json" || fail "dry-run wrote settings.json"
test ! -f "$TMP/.claude/CLAUDE.md" || fail "dry-run wrote CLAUDE.md"
test ! -f "$TMP/.codex/worker.config.toml" || fail "dry-run wrote worker overlay"
test ! -f "$TMP/.hermes/SOUL.md" || fail "dry-run wrote SOUL.md"
pass "dry-run writes nothing"

# seed a wasteful codex config + existing claude settings to merge
printf 'model = "gpt-test"\nmodel_reasoning_effort = "ultra"\n' > "$TMP/.codex/config.toml"
printf '%s\n' '{"permissions":{"allow":["Read"]},"env":{"KEEP_ME":"1"}}' > "$TMP/.claude/settings.json"
printf 'You are Hermes.\n' > "$TMP/.hermes/SOUL.md"
printf 'existing agents header\n' > "$TMP/.codex/AGENTS.md"

# --- apply --yes ---
out="$(python3 "$PY" apply --yes --force --skip-hermes-cli --target all)"
echo "$out" | grep -q 'applied=' || fail "apply missing summary"
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

# --- idempotent second apply ---
out2="$(python3 "$PY" apply --yes --force --skip-hermes-cli --target all)"
echo "$out2" | grep -E 'applied=0' || fail "second apply should apply=0: $out2"
echo "$out2" | grep -E 'would-change=0' || fail "second apply should would-change=0: $out2"
grep -q 'ultra' "$TMP/.codex/config.toml.bak-token-diet" || fail "first backup overwritten"
pass "idempotent re-apply; first backup kept"

out3="$(python3 "$PY" apply --force --skip-hermes-cli)"
echo "$out3" | grep -q 'would-change=0' || fail "dieted dry-run not zero: $out3"
pass "dieted dry-run would-change=0"

mout="$(python3 "$PY" measure --target all)"
echo "$mout" | grep -q 'verdict=already-dieted' || fail "measure verdict: $mout"
pass "measure already-dieted"

# --- rollback ---
python3 "$PY" rollback --yes --target all >/dev/null
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
