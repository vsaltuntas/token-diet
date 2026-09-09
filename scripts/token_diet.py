#!/usr/bin/env python3
"""token-diet: measure / apply / rollback frugal settings for coding agents.

Default is dry-run. Never writes unless --yes. Never touches MCP lists, model
ids, proxies, OAuth, or host-specific gateways.

Core: Claude Code, Codex CLI, Hermes Agent.
Native instruction snippets: Kimi, Gemini, Goose, Qwen, OpenCode, Cline, Droid.
"""
from __future__ import print_function

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
BACKUP_SUFFIX = ".bak-token-diet"
CREATED_MARK = "__TOKEN_DIET_CREATED__\n"
MARKERS = (
    "Token diet",
    "Token disiplini",
    "Delege-önce",
    "token-diet",
    "token diet",
)
WASTE_EFFORT = {"ultra", "xhigh", "x-high", "max"}
CLAUDE_ENV = {
    "CLAUDE_CODE_EFFORT_LEVEL": "medium",
    "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet",
    "MAX_MCP_OUTPUT_TOKENS": "20000",
}
HERMES_KEYS = (
    ("agent.reasoning_effort", "medium"),
    ("agent.service_tier", "normal"),
    ("auxiliary.background_review.enabled", "false"),
    ("tool_output.max_bytes", "20000"),
    ("tool_output.max_lines", "800"),
    ("compression.protect_last_n", "10"),
    ("compression.in_place", "true"),
    ("compression.proactive_prune_tokens", "48000"),
    ("prompt_caching.cache_ttl", "1h"),
    ("tools.tool_search.threshold_pct", "5"),
    ("display.personality", "concise"),
)
AGENTS = ("implementer", "researcher", "reviewer")
TARGETS = (
    "all",
    "claude",
    "codex",
    "hermes",
    "kimi",
    "gemini",
    "goose",
    "qwen",
    "opencode",
    "cline",
    "droid",
)
NATIVE_SNIPPET_CLIENTS = ("kimi", "gemini", "goose", "qwen", "opencode", "cline", "droid")


def home_dir():
    raw = os.environ.get("TOKEN_DIET_HOME")
    return Path(raw).expanduser() if raw else Path.home()


def claude_dir():
    if os.environ.get("TOKEN_DIET_HOME"):
        return home_dir() / ".claude"
    return Path(os.environ.get("CLAUDE_HOME", home_dir() / ".claude"))


def codex_dir():
    if os.environ.get("TOKEN_DIET_HOME"):
        return home_dir() / ".codex"
    return Path(os.environ.get("CODEX_HOME", home_dir() / ".codex"))


def hermes_dir():
    if os.environ.get("TOKEN_DIET_HOME"):
        return home_dir() / ".hermes"
    return Path(os.environ.get("HERMES_HOME", home_dir() / ".hermes"))


def config_home():
    if os.environ.get("TOKEN_DIET_HOME"):
        return home_dir() / ".config"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser()
    return home_dir() / ".config"


def kimi_dir():
    if os.environ.get("TOKEN_DIET_HOME"):
        h = home_dir()
        if (h / ".kimi").exists() and not (h / ".kimi-code").exists():
            return h / ".kimi"
        return h / ".kimi-code"
    env = os.environ.get("KIMI_CODE_HOME")
    if env:
        return Path(env).expanduser()
    h = home_dir()
    if (h / ".kimi-code").exists():
        return h / ".kimi-code"
    if (h / ".kimi").exists():
        return h / ".kimi"
    return h / ".kimi-code"


def gemini_dir():
    if os.environ.get("TOKEN_DIET_HOME"):
        return home_dir() / ".gemini"
    return Path(os.environ.get("GEMINI_HOME", home_dir() / ".gemini"))


def goose_dir():
    return config_home() / "goose"


def qwen_dir():
    if os.environ.get("TOKEN_DIET_HOME"):
        return home_dir() / ".qwen"
    return Path(os.environ.get("QWEN_HOME", home_dir() / ".qwen"))


def opencode_dir():
    env = os.environ.get("OPENCODE_CONFIG_DIR")
    if env and not os.environ.get("TOKEN_DIET_HOME"):
        return Path(env).expanduser()
    return config_home() / "opencode"


def cline_rules_dir():
    docs = home_dir() / "Documents" / "Cline" / "Rules"
    alt = home_dir() / "Cline" / "Rules"
    if docs.exists():
        return docs
    if alt.exists():
        return alt
    return docs


def factory_dir():
    if os.environ.get("TOKEN_DIET_HOME"):
        return home_dir() / ".factory"
    return Path(os.environ.get("FACTORY_HOME", home_dir() / ".factory"))


def native_client_specs():
    return (
        {
            "name": "kimi",
            "bins": ("kimi", "kimi-code"),
            "dir": kimi_dir,
            "file": "AGENTS.md",
            "snippet": "kimi-AGENTS.md.snippet",
        },
        {
            "name": "gemini",
            "bins": ("gemini",),
            "dir": gemini_dir,
            "file": "GEMINI.md",
            "snippet": "GEMINI.md.snippet",
        },
        {
            "name": "goose",
            "bins": ("goose",),
            "dir": goose_dir,
            "file": ".goosehints",
            "snippet": "goosehints.snippet",
        },
        {
            "name": "qwen",
            "bins": ("qwen",),
            "dir": qwen_dir,
            "file": "QWEN.md",
            "snippet": "QWEN.md.snippet",
        },
        {
            "name": "opencode",
            "bins": ("opencode",),
            "dir": opencode_dir,
            "file": "AGENTS.md",
            "snippet": "OPENCODE.md.snippet",
        },
        {
            "name": "cline",
            "bins": ("cline",),
            "dir": cline_rules_dir,
            "file": "token-diet.md",
            "snippet": "cline-token-diet.md.snippet",
        },
        {
            "name": "droid",
            "bins": ("droid",),
            "dir": factory_dir,
            "file": "AGENTS.md",
            "snippet": "FACTORY.md.snippet",
        },
    )


def which(name):
    return shutil.which(name)


def rtk_init_cmd():
    """Non-interactive `rtk init` for the installed binary.

    `--auto-patch` is not universal. Probe `rtk init --help` and only pass
    flags that exist. Prefer `--auto-patch` (no prompt); else `--no-patch`.
    """
    cmd = ["rtk", "init", "-g"]
    help_txt = ""
    try:
        help_txt = subprocess.check_output(
            ["rtk", "init", "--help"],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    except (OSError, subprocess.CalledProcessError):
        help_txt = ""
    if "--auto-patch" in help_txt:
        cmd.append("--auto-patch")
    elif "--no-patch" in help_txt:
        cmd.append("--no-patch")
    return cmd


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None


def has_marker(text):
    if not text:
        return False
    lower = text.lower()
    for m in MARKERS:
        if m.lower() in lower:
            return True
    return False


def backup_path(path):
    return Path(str(path) + BACKUP_SUFFIX)


def ensure_backup(path, dry):
    if not path.exists():
        return "none"
    bak = backup_path(path)
    if bak.exists():
        return "kept"
    if dry:
        return "would-backup"
    shutil.copy2(path, bak)
    return "backed"


def write_file(path, content, dry):
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def mark_created(path, dry):
    bak = backup_path(path)
    if bak.exists() or dry:
        return
    bak.parent.mkdir(parents=True, exist_ok=True)
    bak.write_text(CREATED_MARK, encoding="utf-8")


def append_snippet(path, snippet, dry):
    existed = path.exists()
    existing = read_text(path) or ""
    if has_marker(existing):
        return "ok", "present"
    block = snippet if snippet.endswith("\n") else snippet + "\n"
    if existing and not existing.endswith("\n"):
        existing += "\n"
    new = existing + ("\n" if existing else "") + block
    if existing == new:
        return "ok", "present"
    if existed:
        ensure_backup(path, dry)
    else:
        mark_created(path, dry)
    write_file(path, new, dry)
    return ("would-change" if dry else "applied"), "append"


def copy_if_missing(src, dest, dry):
    if dest.exists():
        return "ok", "exists"
    if dry:
        return "would-change", "create"
    dest.parent.mkdir(parents=True, exist_ok=True)
    mark_created(dest, dry)
    shutil.copy2(src, dest)
    return "applied", "create"


def load_json(path):
    raw = read_text(path)
    if raw is None:
        return None, "missing"
    try:
        return json.loads(raw), "ok"
    except ValueError as exc:
        return None, "invalid-json:%s" % exc


def dump_json(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def toml_effort(text):
    if not text:
        return None
    m = re.search(r'(?m)^model_reasoning_effort\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def set_toml_effort(text, value):
    text = text or ""
    if re.search(r'(?m)^model_reasoning_effort\s*=', text):
        return re.sub(
            r'(?m)^model_reasoning_effort\s*=\s*"[^"]+"',
            'model_reasoning_effort = "%s"' % value,
            text,
            count=1,
        )
    if text and not text.endswith("\n"):
        text += "\n"
    return text + 'model_reasoning_effort = "%s"\n' % value


def present_cli(binary, directory):
    return bool(which(binary) or directory.exists())


def present_any(binaries, directory):
    for b in binaries:
        if which(b):
            return True
    return directory.exists()


class Report(object):
    def __init__(self, mode):
        self.mode = mode
        self.rows = []

    def add(self, key, status, detail=""):
        self.rows.append((key, status, detail))
        line = "%-48s %-14s %s" % (key, status, detail)
        print(line.rstrip())

    def counts(self):
        n = {}
        for _, s, _ in self.rows:
            n[s] = n.get(s, 0) + 1
        return n

    def would(self):
        return sum(1 for _, s, _ in self.rows if s == "would-change")

    def failed(self):
        return sum(1 for _, s, _ in self.rows if s in ("error", "invalid"))


def target_enabled(args, name):
    return args.target in ("all", name)


def apply_claude(args, rep):
    cdir = claude_dir()
    if not present_cli("claude", cdir) and not args.force:
        rep.add("claude", "skip", "cli/dir not found")
        return
    settings_path = cdir / "settings.json"
    data, st = load_json(settings_path)
    if st.startswith("invalid"):
        rep.add("claude.settings", "error", st)
        return
    if data is None:
        data = {}
    env = dict(data.get("env") or {})
    env_changed = False
    for k, v in CLAUDE_ENV.items():
        cur = env.get(k)
        if str(cur) == v:
            rep.add("claude.env.%s" % k, "ok", v)
        else:
            env[k] = v
            env_changed = True
            rep.add(
                "claude.env.%s" % k,
                "would-change" if args.dry_run else "applied",
                "%s -> %s" % (cur, v),
            )
    if env_changed:
        ensure_backup(settings_path, args.dry_run)
        data["env"] = env
        write_file(settings_path, dump_json(data), args.dry_run)

    for name in AGENTS:
        src = TEMPLATES / "claude-agents" / ("%s.md" % name)
        dest = cdir / "agents" / ("%s.md" % name)
        status, detail = copy_if_missing(src, dest, args.dry_run)
        rep.add("claude.agent.%s" % name, status, detail)

    snippet = read_text(TEMPLATES / "CLAUDE.md.snippet") or ""
    status, detail = append_snippet(cdir / "CLAUDE.md", snippet, args.dry_run)
    rep.add("claude.snippet", status, detail)

    rtk_hook = False
    hooks = (data.get("hooks") or {}) if isinstance(data, dict) else {}
    blob = json.dumps(hooks)
    if "rtk" in blob.lower():
        rtk_hook = True
    if rtk_hook:
        rep.add("claude.rtk_hook", "ok", "present")
    elif which("rtk"):
        argv = rtk_init_cmd()
        cmd = " ".join(argv)
        if getattr(args, "rtk", False):
            if args.dry_run:
                rep.add("claude.rtk_hook", "would-change", cmd)
            else:
                try:
                    subprocess.check_call(argv)
                    rep.add("claude.rtk_hook", "applied", cmd)
                except (OSError, subprocess.CalledProcessError) as exc:
                    rep.add("claude.rtk_hook", "error", str(exc))
        else:
            rep.add("claude.rtk_hook", "skip", "optional; pass --rtk to run: %s" % cmd)
    else:
        rep.add("claude.rtk_hook", "skip", "rtk not installed (optional)")


def apply_codex(args, rep):
    cdir = codex_dir()
    if not present_cli("codex", cdir) and not args.force:
        rep.add("codex", "skip", "cli/dir not found")
        return
    cfg = cdir / "config.toml"
    text = read_text(cfg)
    effort = toml_effort(text)
    if effort is None and text is None:
        # no config yet — do not invent a full config.toml
        rep.add("codex.effort", "skip", "no config.toml (will not create one)")
    elif effort is None:
        new = set_toml_effort(text, "high")
        ensure_backup(cfg, args.dry_run)
        write_file(cfg, new, args.dry_run)
        rep.add("codex.effort", "would-change" if args.dry_run else "applied", "set high")
    elif effort.lower() in WASTE_EFFORT:
        new = set_toml_effort(text, "high")
        ensure_backup(cfg, args.dry_run)
        write_file(cfg, new, args.dry_run)
        rep.add(
            "codex.effort",
            "would-change" if args.dry_run else "applied",
            "%s -> high" % effort,
        )
    else:
        rep.add("codex.effort", "ok", effort)

    for name in ("worker", "reviewer"):
        src = TEMPLATES / "codex-profiles" / ("%s.config.toml" % name)
        dest = cdir / ("%s.config.toml" % name)
        status, detail = copy_if_missing(src, dest, args.dry_run)
        rep.add("codex.profile.%s" % name, status, detail)

    snippet = read_text(TEMPLATES / "AGENTS.md.snippet") or ""
    status, detail = append_snippet(cdir / "AGENTS.md", snippet, args.dry_run)
    rep.add("codex.snippet", status, detail)


def hermes_get(key):
    hermes = os.environ.get("HERMES_BIN") or which("hermes")
    if not hermes:
        return None, "no-hermes"
    try:
        out = subprocess.check_output(
            [hermes, "config", "get", key],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ).strip()
        return out, "ok"
    except subprocess.CalledProcessError as exc:
        err = (exc.output or "").strip()
        return None, "unsupported" if err else "error"
    except OSError:
        return None, "no-hermes"


def hermes_set(key, value, dry):
    if dry:
        return "would-change"
    hermes = os.environ.get("HERMES_BIN") or which("hermes")
    subprocess.check_call([hermes, "config", "set", key, value])
    return "applied"


def apply_hermes(args, rep):
    hdir = hermes_dir()
    if not present_cli("hermes", hdir) and not args.force:
        rep.add("hermes", "skip", "cli/dir not found")
        return
    live = not args.skip_hermes_cli and bool(os.environ.get("HERMES_BIN") or which("hermes"))
    if live:
        yaml_path = hdir / "config.yaml"
        backed = False
        for key, want in HERMES_KEYS:
            cur, st = hermes_get(key)
            if st in ("unsupported", "error"):
                rep.add("hermes.%s" % key, "skip", st)
                continue
            if st == "no-hermes":
                rep.add("hermes.config", "skip", "hermes binary missing")
                live = False
                break
            norm = (cur or "").strip().lower()
            want_n = want.lower()
            if norm == want_n or (want_n in ("true", "false") and norm == want_n):
                rep.add("hermes.%s" % key, "ok", cur)
            else:
                if not backed:
                    ensure_backup(yaml_path, args.dry_run)
                    backed = True
                try:
                    status = hermes_set(key, want, args.dry_run)
                    rep.add("hermes.%s" % key, status, "%s -> %s" % (cur, want))
                except (OSError, subprocess.CalledProcessError) as exc:
                    rep.add("hermes.%s" % key, "error", str(exc))
    else:
        rep.add("hermes.config", "skip", "cli disabled or missing")

    snippet = read_text(TEMPLATES / "SOUL.md.snippet") or ""
    status, detail = append_snippet(hdir / "SOUL.md", snippet, args.dry_run)
    rep.add("hermes.soul", status, detail)


def spec_paths(spec):
    d = spec["dir"]()
    return d, d / spec["file"]


def apply_native(args, rep, spec):
    d, dest = spec_paths(spec)
    if not present_any(spec["bins"], d) and not args.force:
        rep.add(spec["name"], "skip", "cli/dir not found")
        return
    snippet = read_text(TEMPLATES / spec["snippet"]) or ""
    status, detail = append_snippet(dest, snippet, args.dry_run)
    rep.add("%s.snippet" % spec["name"], status, detail)


def cmd_apply(args):
    if getattr(args, "explicit_dry_run", False):
        args.yes = False
    args.dry_run = not args.yes
    mode = "dry-run" if args.dry_run else "apply"
    print("%s token-diet  home=%s  target=%s" % (mode, home_dir(), args.target))
    rep = Report(mode)
    if target_enabled(args, "claude"):
        apply_claude(args, rep)
    if target_enabled(args, "codex"):
        apply_codex(args, rep)
    if target_enabled(args, "hermes"):
        apply_hermes(args, rep)
    for spec in native_client_specs():
        if target_enabled(args, spec["name"]):
            apply_native(args, rep, spec)
    n = rep.counts()
    print(
        "summary: would-change=%d applied=%d ok=%d skip=%d error=%d"
        % (
            n.get("would-change", 0),
            n.get("applied", 0),
            n.get("ok", 0),
            n.get("skip", 0),
            n.get("error", 0),
        )
    )
    if rep.failed():
        return 1
    if args.dry_run and rep.would():
        return 3
    return 0


def measure_claude(rep):
    cdir = claude_dir()
    if not present_cli("claude", cdir):
        rep.add("claude", "missing", "")
        return
    data, st = load_json(cdir / "settings.json")
    env = (data or {}).get("env") or {} if st == "ok" else {}
    for k, v in CLAUDE_ENV.items():
        cur = str(env.get(k, ""))
        rep.add("claude.env.%s" % k, "ok" if cur == v else "drift", cur or "-")
    for name in AGENTS:
        p = cdir / "agents" / ("%s.md" % name)
        rep.add("claude.agent.%s" % name, "ok" if p.exists() else "missing", str(p))
    text = read_text(cdir / "CLAUDE.md")
    rep.add("claude.snippet", "ok" if has_marker(text) else "missing", "")
    blob = json.dumps((data or {}).get("hooks") or {})
    rtk = "rtk" in blob.lower()
    # RTK is optional. Presence is ok; absence is skip, not a diet failure.
    rep.add("claude.rtk_hook", "ok" if rtk else "skip", "rtk_bin=%s hook=%s" % (bool(which("rtk")), rtk))


def measure_codex(rep):
    cdir = codex_dir()
    if not present_cli("codex", cdir):
        rep.add("codex", "missing", "")
        return
    effort = toml_effort(read_text(cdir / "config.toml"))
    if effort is None:
        rep.add("codex.effort", "missing", "-")
    elif effort.lower() in WASTE_EFFORT:
        rep.add("codex.effort", "drift", effort)
    else:
        rep.add("codex.effort", "ok", effort)
    for name in ("worker", "reviewer"):
        p = cdir / ("%s.config.toml" % name)
        rep.add("codex.profile.%s" % name, "ok" if p.exists() else "missing", "")
    text = read_text(cdir / "AGENTS.md")
    rep.add("codex.snippet", "ok" if has_marker(text) else "missing", "")


def measure_hermes(rep):
    hdir = hermes_dir()
    if not present_cli("hermes", hdir):
        rep.add("hermes", "missing", "")
        return
    live = bool(os.environ.get("HERMES_BIN") or which("hermes"))
    skip_cli = os.environ.get("TOKEN_DIET_SKIP_HERMES_CLI") == "1"
    if live and not skip_cli:
        for key, want in HERMES_KEYS:
            cur, st = hermes_get(key)
            if st != "ok":
                rep.add("hermes.%s" % key, "skip", st)
                continue
            ok = (cur or "").strip().lower() == want.lower()
            rep.add("hermes.%s" % key, "ok" if ok else "drift", cur or "-")
    else:
        rep.add("hermes.config", "skip", "cli disabled")
    text = read_text(hdir / "SOUL.md")
    rep.add("hermes.soul", "ok" if has_marker(text) else "missing", "")


def measure_native(rep, spec):
    d, dest = spec_paths(spec)
    if not present_any(spec["bins"], d):
        rep.add(spec["name"], "skip", "cli/dir not found")
        return
    text = read_text(dest)
    rep.add("%s.snippet" % spec["name"], "ok" if has_marker(text) else "missing", str(dest))


def cmd_measure(args):
    print("measure token-diet  home=%s" % home_dir())
    rtk = which("rtk")
    print("rtk: %s" % (rtk or "not installed"))
    rep = Report("measure")
    if target_enabled(args, "claude"):
        measure_claude(rep)
    if target_enabled(args, "codex"):
        measure_codex(rep)
    if target_enabled(args, "hermes"):
        measure_hermes(rep)
    for spec in native_client_specs():
        if target_enabled(args, spec["name"]):
            measure_native(rep, spec)
    n = rep.counts()
    drift = n.get("drift", 0) + n.get("missing", 0)
    verdict = "already-dieted" if drift == 0 and n.get("error", 0) == 0 else "needs-apply"
    print(
        "summary: ok=%d drift=%d missing=%d skip=%d verdict=%s"
        % (n.get("ok", 0), n.get("drift", 0), n.get("missing", 0), n.get("skip", 0), verdict)
    )
    return 0


def restore_backup(path, dry, rep, key):
    bak = backup_path(path)
    if not bak.exists():
        rep.add(key, "skip", "no backup")
        return
    raw = read_text(bak) or ""
    created = raw == CREATED_MARK
    if dry:
        rep.add(key, "would-change", "remove created" if created else "restore %s" % bak.name)
        return
    if created:
        if path.exists():
            path.unlink()
        bak.unlink()
        rep.add(key, "applied", "removed created file")
        return
    shutil.copy2(bak, path)
    rep.add(key, "applied", "restored")


def cmd_rollback(args):
    if getattr(args, "explicit_dry_run", False):
        args.yes = False
    args.dry_run = not args.yes
    mode = "dry-run" if args.dry_run else "rollback"
    print("%s token-diet rollback  home=%s" % (mode, home_dir()))
    rep = Report(mode)
    if target_enabled(args, "claude"):
        cdir = claude_dir()
        restore_backup(cdir / "settings.json", args.dry_run, rep, "claude.settings")
        restore_backup(cdir / "CLAUDE.md", args.dry_run, rep, "claude.snippet")
        for name in AGENTS:
            restore_backup(cdir / "agents" / ("%s.md" % name), args.dry_run, rep, "claude.agent.%s" % name)
    if target_enabled(args, "codex"):
        cdir = codex_dir()
        restore_backup(cdir / "config.toml", args.dry_run, rep, "codex.config")
        restore_backup(cdir / "AGENTS.md", args.dry_run, rep, "codex.snippet")
        for name in ("worker", "reviewer"):
            restore_backup(cdir / ("%s.config.toml" % name), args.dry_run, rep, "codex.profile.%s" % name)
    if target_enabled(args, "hermes"):
        hdir = hermes_dir()
        restore_backup(hdir / "config.yaml", args.dry_run, rep, "hermes.config")
        restore_backup(hdir / "SOUL.md", args.dry_run, rep, "hermes.soul")
    for spec in native_client_specs():
        if target_enabled(args, spec["name"]):
            _d, dest = spec_paths(spec)
            restore_backup(dest, args.dry_run, rep, "%s.snippet" % spec["name"])
    n = rep.counts()
    print(
        "summary: would-change=%d applied=%d skip=%d error=%d"
        % (n.get("would-change", 0), n.get("applied", 0), n.get("skip", 0), n.get("error", 0))
    )
    if rep.failed():
        return 1
    if args.dry_run and rep.would():
        return 3
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="token-diet",
        description="Frugal token settings for Claude / Codex / Hermes plus native rules for Kimi, Gemini, Goose, Qwen, OpenCode, Cline, Droid",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("measure", "apply", "rollback"):
        s = sub.add_parser(name)
        s.add_argument("--target", choices=TARGETS, default="all")
        s.add_argument("--force", action="store_true", help="write even if CLI/dir not detected")
        if name != "measure":
            s.add_argument("--yes", action="store_true", help="write files (default is dry-run)")
            s.add_argument(
                "--dry-run",
                dest="explicit_dry_run",
                action="store_true",
                help="explicit dry-run (default). Exit 3 if would-change>0",
            )
        if name == "apply":
            s.add_argument(
                "--rtk",
                action="store_true",
                help="run `rtk init -g` (plus --auto-patch if that rtk supports it) if hook missing",
            )
            s.add_argument("--skip-hermes-cli", action="store_true", help="do not call `hermes config`")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if getattr(args, "skip_hermes_cli", False) or os.environ.get("TOKEN_DIET_SKIP_HERMES_CLI"):
        args.skip_hermes_cli = True
    else:
        args.skip_hermes_cli = False
    if args.cmd == "measure":
        return cmd_measure(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "rollback":
        return cmd_rollback(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
