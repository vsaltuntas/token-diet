#!/usr/bin/env bash
# Read-only before/after token comparison from Hermes state.db.
# Writes nothing. Default cutoff = 2026-09-06 (token-diet install), 7-day windows.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
from __future__ import print_function

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # py<3.9
    ZoneInfo = None

CUTOFF_DEFAULT = "2026-09-06"
WINDOW_DAYS = 7
TZ_NAME = "Europe/Istanbul"


def die(msg, code=1):
    print("error=" + msg, file=sys.stderr)
    sys.exit(code)


def hermes_home():
    if os.environ.get("TOKEN_DIET_HOME"):
        return os.path.join(os.path.expanduser(os.environ["TOKEN_DIET_HOME"]), ".hermes")
    if os.environ.get("HERMES_HOME"):
        return os.path.expanduser(os.environ["HERMES_HOME"])
    return os.path.join(os.path.expanduser("~"), ".hermes")


def parse_cutoff(raw):
    try:
        y, m, d = (int(p) for p in raw.split("-"))
        return y, m, d
    except Exception:
        die("cutoff must be YYYY-MM-DD, got %r" % (raw,))


def tzinfo():
    if ZoneInfo is not None:
        try:
            return ZoneInfo(TZ_NAME)
        except Exception:
            pass
    return timezone(timedelta(hours=3), name="+03")


def epoch(y, m, d, tz):
    return datetime(y, m, d, 0, 0, 0, tzinfo=tz).timestamp()


def iso(ts, tz):
    return datetime.fromtimestamp(ts, tz=tz).strftime("%Y-%m-%dT%H:%M:%S%z")


def db_path():
    override = os.environ.get("TOKEN_DIET_STATE_DB")
    if override:
        return os.path.expanduser(override)
    return os.path.join(hermes_home(), "state.db")


def connect_ro(path):
    if not os.path.isfile(path):
        die("state.db not found: %s" % path, 2)
    uri = "file:%s?mode=ro" % path.replace("?", "%3F")
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        die("cannot open read-only: %s" % e, 2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


SQL = """
SELECT
  COALESCE(SUM(u.input_tokens), 0) AS input_tokens,
  COALESCE(SUM(u.output_tokens), 0) AS output_tokens,
  COALESCE(SUM(u.cache_read_tokens), 0) AS cache_read_tokens,
  COALESCE(SUM(u.cache_write_tokens), 0) AS cache_write_tokens,
  COALESCE(SUM(u.reasoning_tokens), 0) AS reasoning_tokens,
  COALESCE(SUM(u.api_call_count), 0) AS api_calls,
  COALESCE(SUM(u.estimated_cost_usd), 0) AS estimated_usd
FROM session_model_usage u
JOIN sessions s ON s.id = u.session_id
WHERE s.started_at >= ? AND s.started_at < ?
"""


def query_window(conn, start, end):
    cur = conn.execute(SQL, (start, end))
    row = cur.fetchone()
    inp = int(row["input_tokens"] or 0)
    out = int(row["output_tokens"] or 0)
    cr = int(row["cache_read_tokens"] or 0)
    cw = int(row["cache_write_tokens"] or 0)
    rs = int(row["reasoning_tokens"] or 0)
    calls = int(row["api_calls"] or 0)
    usd = float(row["estimated_usd"] or 0.0)
    total = inp + out + cr + cw + rs
    cache_per_call = (float(cr) / calls) if calls else 0.0
    reasoning_pct_out = (100.0 * rs / out) if out else 0.0
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "cache_read_tokens": cr,
        "cache_write_tokens": cw,
        "reasoning_tokens": rs,
        "total_tokens": total,
        "api_calls": calls,
        "cache_read_per_call": cache_per_call,
        "reasoning_pct_of_output": reasoning_pct_out,
        "estimated_usd": usd,
    }


def emit(name, start, end, now, tz, stats):
    incomplete = now < end
    print("window=%s" % name)
    print("start=%s" % iso(start, tz))
    print("end=%s" % iso(end, tz))
    print("incomplete=%s" % ("true" if incomplete else "false"))
    print("total_tokens=%d" % stats["total_tokens"])
    print("input_tokens=%d" % stats["input_tokens"])
    print("output_tokens=%d" % stats["output_tokens"])
    print("cache_read_tokens=%d" % stats["cache_read_tokens"])
    print("cache_write_tokens=%d" % stats["cache_write_tokens"])
    print("reasoning_tokens=%d" % stats["reasoning_tokens"])
    print("api_calls=%d" % stats["api_calls"])
    print("cache_read_per_call=%.1f" % stats["cache_read_per_call"])
    print("reasoning_pct_of_output=%.2f" % stats["reasoning_pct_of_output"])
    print("estimated_usd=%.4f" % stats["estimated_usd"])


def main():
    cutoff_raw = os.environ.get("TOKEN_DIET_CUTOFF", CUTOFF_DEFAULT)
    y, m, d = parse_cutoff(cutoff_raw)
    days = int(os.environ.get("TOKEN_DIET_WINDOW_DAYS", str(WINDOW_DAYS)))
    tz = tzinfo()
    cutoff = epoch(y, m, d, tz)
    before_start = cutoff - days * 86400
    after_end = cutoff + days * 86400
    now = datetime.now(tz=timezone.utc).timestamp()
    path = db_path()

    print("mode=read-only")
    print("cutoff=%s" % cutoff_raw)
    print("window_days=%d" % days)
    print("tz=%s" % TZ_NAME)
    print("db=%s" % path)

    conn = connect_ro(path)
    try:
        before = query_window(conn, before_start, cutoff)
        after = query_window(conn, cutoff, after_end)
    finally:
        conn.close()

    emit("before", before_start, cutoff, now, tz, before)
    emit("after", cutoff, after_end, now, tz, after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
PY
