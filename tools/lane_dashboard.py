#!/usr/bin/env python3
"""
Lane health dashboard — local single-file operator console.

Binds to 127.0.0.1 only. Exposes a fixed set of lane ids; each maps to a
hardcoded end-to-end test. Client input is NEVER executed as a shell command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8787
BIND_HOST = "127.0.0.1"

# Per-lane wall-clock timeout for the real CLI invocation (seconds).
LANE_TIMEOUT_S = 300
# Short timeouts for version / discovery / verification calls.
QUICK_TIMEOUT_S = 30
PREFLIGHT_TIMEOUT_S = 15

# Seeded-bug fixture (identical for every lane).
FIXTURE_M_PY = "def add(a, b):\n    return a - b\n"
FIXTURE_V_PY = (
    "from m import add\n"
    "assert add(2,3)==5, add(2,3)\n"
    "print(\"PASS\")\n"
)

TASK_TEMPLATE = (
    "Fix add(a,b) in {m_path} to return a + b instead of a - b. "
    "Edit only m.py. Then run python3 v.py and report the output."
)

# Status values (exact strings required by the operator contract).
STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_UNAVAILABLE = "unavailable"
STATUS_TIMEOUT = "timeout"
STATUS_INVALID = "invalid"

# Patterns that mean "out of quota / rate limited" rather than a broken lane.
QUOTA_HINTS = re.compile(
    r"(quota|rate.?limit|usage.?limit|exceeded.*limit|insufficient.*(credit|quota)|"
    r"billing|payment.?required|429|too many requests|capacity|over.?loaded|"
    r"out of (credits|tokens|quota))",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Environment / subprocess helpers
# ---------------------------------------------------------------------------

def hardened_env() -> dict[str, str]:
    """Copy the process env and prepend ~/.local/bin (known CLI home)."""
    env = os.environ.copy()
    local_bin = os.path.expanduser("~/.local/bin")
    env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
    return env


def which(cmd: str) -> str | None:
    return shutil.which(cmd, path=hardened_env()["PATH"])


def run_argv(
    argv: list[str],
    *,
    timeout: float,
    cwd: str | None = None,
    input_text: str | None = None,
    stdin_devnull: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run an argv list (never shell=True). Raises subprocess.TimeoutExpired."""
    kwargs: dict[str, Any] = {
        "args": argv,
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "env": hardened_env(),
        "cwd": cwd,
    }
    if stdin_devnull:
        kwargs["stdin"] = subprocess.DEVNULL
    elif input_text is not None:
        kwargs["input"] = input_text
    return subprocess.run(**kwargs)


def clip(s: str | None, n: int = 8000) -> str:
    if not s:
        return ""
    s = s.strip()
    if len(s) <= n:
        return s
    return s[: n // 2] + "\n…[truncated]…\n" + s[-(n // 2) :]


def version_of(cmd: str, version_argv: list[str] | None = None) -> str | None:
    """Cheap --version style probe. Returns version string or None."""
    if not which(cmd):
        return None
    argv = version_argv or [cmd, "--version"]
    try:
        r = run_argv(argv, timeout=PREFLIGHT_TIMEOUT_S)
        out = (r.stdout or r.stderr or "").strip().splitlines()
        # Prefer first non-warning line.
        for line in out:
            if "Warning" in line or "FORCE_COLOR" in line or "NO_COLOR" in line:
                continue
            if line.strip():
                return line.strip()[:200]
        return (r.stdout or r.stderr or "").strip()[:200] or None
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Fixture + shared E2E harness
# ---------------------------------------------------------------------------

def write_fixture(absdir: str) -> tuple[str, str]:
    m_path = os.path.join(absdir, "m.py")
    v_path = os.path.join(absdir, "v.py")
    with open(m_path, "w", encoding="utf-8") as f:
        f.write(FIXTURE_M_PY)
    with open(v_path, "w", encoding="utf-8") as f:
        f.write(FIXTURE_V_PY)
    return m_path, v_path


def run_python_v(absdir: str) -> subprocess.CompletedProcess[str]:
    return run_argv(
        ["python3", "v.py"],
        timeout=QUICK_TIMEOUT_S,
        cwd=absdir,
    )


def m_py_diff(absdir: str) -> str:
    """Show current m.py vs the seeded-bug fixture."""
    path = os.path.join(absdir, "m.py")
    try:
        with open(path, encoding="utf-8") as f:
            current = f.read()
    except OSError as e:
        return f"(could not read m.py: {e})"
    if current == FIXTURE_M_PY:
        return "(m.py unchanged from fixture)"
    return (
        "--- fixture m.py\n+++ current m.py\n"
        f"@@ fixture @@\n{FIXTURE_M_PY}"
        f"@@ current @@\n{current}"
    )


def base_result(lane: str) -> dict[str, Any]:
    return {
        "lane": lane,
        "status": STATUS_FAIL,
        "cli_version": None,
        "duration_s": 0.0,
        "negative_control": "",
        "verification_output": "",
        "diff": "",
        "evidence_dir": None,
        "message": "",
    }


def finish_result(
    result: dict[str, Any],
    absdir: str,
    t0: float,
    *,
    keep_evidence: bool,
) -> dict[str, Any]:
    result["duration_s"] = round(time.time() - t0, 2)
    result["diff"] = result.get("diff") or m_py_diff(absdir)
    if keep_evidence:
        result["evidence_dir"] = absdir
        result["message"] = (
            (result.get("message") or "") + f" Evidence kept at {absdir}."
        ).strip()
    else:
        shutil.rmtree(absdir, ignore_errors=True)
        result["evidence_dir"] = None
        if result["status"] == STATUS_PASS:
            result["message"] = (
                (result.get("message") or "Verification printed PASS.")
                + " Temp dir deleted."
            ).strip()
    return result


def run_lane_harness(
    lane: str,
    invoke_cli: Callable[[str, str], subprocess.CompletedProcess[str] | dict[str, Any]],
    cli_version: str | None,
) -> dict[str, Any]:
    """
    Shared E2E steps:
      1) fresh temp dir + fixture
      2) negative control must FAIL
      3) invoke_cli(absdir, task)  — may return a pre-built result dict for
         early exits (unavailable / etc.)
      4) independent verification
      5) structured evidence
    """
    t0 = time.time()
    result = base_result(lane)
    result["cli_version"] = cli_version

    absdir = tempfile.mkdtemp(prefix=f"lane_{lane}_")
    m_path, _v_path = write_fixture(absdir)
    task = TASK_TEMPLATE.format(m_path=m_path)

    # --- negative control ---
    try:
        neg = run_python_v(absdir)
    except subprocess.TimeoutExpired:
        result["status"] = STATUS_INVALID
        result["negative_control"] = "negative control timed out"
        result["message"] = "Could not run negative control (timeout)."
        return finish_result(result, absdir, t0, keep_evidence=True)
    except OSError as e:
        result["status"] = STATUS_INVALID
        result["negative_control"] = f"negative control error: {e}"
        result["message"] = f"Could not run negative control: {e}"
        return finish_result(result, absdir, t0, keep_evidence=True)

    neg_out = clip((neg.stdout or "") + (neg.stderr or ""))
    if neg.returncode == 0:
        # Vacuous — fixture should be broken before the lane runs.
        result["status"] = STATUS_INVALID
        result["negative_control"] = "UNEXPECTEDLY PASSED"
        result["verification_output"] = neg_out
        result["message"] = (
            "Negative control passed before the lane ran — test would be vacuous."
        )
        return finish_result(result, absdir, t0, keep_evidence=True)

    result["negative_control"] = "failed as expected"

    # --- invoke CLI ---
    try:
        cli_out = invoke_cli(absdir, task)
    except subprocess.TimeoutExpired as e:
        out = ""
        if e.stdout:
            out += str(e.stdout)
        if e.stderr:
            out += "\n" + str(e.stderr)
        result["status"] = STATUS_TIMEOUT
        result["verification_output"] = clip(out)
        result["message"] = f"Lane CLI timed out after {LANE_TIMEOUT_S}s."
        return finish_result(result, absdir, t0, keep_evidence=False)
    except FileNotFoundError as e:
        result["status"] = STATUS_UNAVAILABLE
        result["message"] = f"CLI not found: {e}"
        return finish_result(result, absdir, t0, keep_evidence=False)
    except OSError as e:
        result["status"] = STATUS_UNAVAILABLE
        result["message"] = f"OS error launching CLI: {e}"
        return finish_result(result, absdir, t0, keep_evidence=False)

    # Early-exit dict from invoke_cli (e.g. unavailable before/after run).
    if isinstance(cli_out, dict):
        result.update({k: v for k, v in cli_out.items() if v is not None})
        keep = result["status"] in (STATUS_FAIL, STATUS_INVALID)
        return finish_result(result, absdir, t0, keep_evidence=keep)

    cli_text = clip((cli_out.stdout or "") + "\n" + (cli_out.stderr or ""))

    # Quota / auth failures surface as unavailable, not fail.
    if QUOTA_HINTS.search(cli_text):
        # Quote a short matching snippet for the operator.
        m = QUOTA_HINTS.search(cli_text)
        assert m is not None
        # Grab surrounding line for the message.
        line = cli_text[max(0, m.start() - 40) : m.end() + 80].strip()
        result["status"] = STATUS_UNAVAILABLE
        result["verification_output"] = cli_text
        result["message"] = f"Quota/limit indicated by CLI: “{line}”"
        return finish_result(result, absdir, t0, keep_evidence=False)

    # --- independent verification ---
    try:
        ver = run_python_v(absdir)
    except subprocess.TimeoutExpired:
        result["status"] = STATUS_FAIL
        result["verification_output"] = clip(cli_text + "\n[verification timed out]")
        result["message"] = "Verification timed out after the lane ran."
        return finish_result(result, absdir, t0, keep_evidence=True)
    except OSError as e:
        result["status"] = STATUS_FAIL
        result["verification_output"] = clip(cli_text + f"\n[verification error: {e}]")
        result["message"] = f"Verification could not run: {e}"
        return finish_result(result, absdir, t0, keep_evidence=True)

    ver_text = clip((ver.stdout or "") + (ver.stderr or ""))
    result["verification_output"] = (
        f"--- CLI output ---\n{cli_text}\n--- verification (python3 v.py) ---\n{ver_text}"
    )
    result["diff"] = m_py_diff(absdir)

    if ver.returncode == 0 and "PASS" in (ver.stdout or ""):
        result["status"] = STATUS_PASS
        result["message"] = "Verification printed PASS after the lane ran."
        return finish_result(result, absdir, t0, keep_evidence=False)

    result["status"] = STATUS_FAIL
    result["message"] = "Lane ran but verification still fails (add still wrong or v.py failed)."
    return finish_result(result, absdir, t0, keep_evidence=True)


# ---------------------------------------------------------------------------
# Per-lane implementations (hardcoded; never driven by client argv)
# ---------------------------------------------------------------------------

def discover_deepseek_alias() -> str | None:
    """
    Parse `kimi provider list` and return the first model alias containing
    'deepseek-v4-flash'. Returns None if OpenRouter / alias is missing.
    """
    if not which("kimi"):
        return None
    try:
        r = run_argv(["kimi", "provider", "list"], timeout=PREFLIGHT_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        return None
    text = (r.stdout or "") + "\n" + (r.stderr or "")
    # Collect token-like aliases (path-ish or bare).
    candidates = re.findall(r"[A-Za-z0-9_./:+-]*deepseek-v4-flash[A-Za-z0-9_./:+-]*", text)
    for c in candidates:
        if "deepseek-v4-flash" in c:
            return c
    return None


def test_gemini() -> dict[str, Any]:
    ver = version_of("agy")
    if not which("agy"):
        r = base_result("gemini")
        r["status"] = STATUS_UNAVAILABLE
        r["message"] = "agy CLI not found on PATH (expected under ~/.local/bin)."
        return r

    def invoke(absdir: str, task: str):
        # agy ignores process cwd — --add-dir with the absolute dir is mandatory.
        argv = [
            "agy",
            "-p",
            task,
            "--add-dir",
            absdir,
            "--model",
            "gemini-3.1-pro-high",
            "--dangerously-skip-permissions",
            "--print-timeout",
            "4m",
        ]
        return run_argv(argv, timeout=LANE_TIMEOUT_S)

    return run_lane_harness("gemini", invoke, ver)


def test_deepseek() -> dict[str, Any]:
    ver = version_of("kimi", ["kimi", "--version"])
    if not which("kimi"):
        r = base_result("deepseek")
        r["status"] = STATUS_UNAVAILABLE
        r["message"] = "kimi CLI not found on PATH."
        return r

    alias = discover_deepseek_alias()
    if not alias:
        r = base_result("deepseek")
        r["status"] = STATUS_UNAVAILABLE
        r["cli_version"] = ver
        r["message"] = (
            "OpenRouter provider not imported — operator must run the one-time setup"
        )
        return r

    def invoke(absdir: str, task: str):
        argv = ["kimi", "-p", task, "-m", alias]
        return run_argv(argv, timeout=LANE_TIMEOUT_S, cwd=absdir)

    return run_lane_harness("deepseek", invoke, ver)


def test_codex() -> dict[str, Any]:
    ver = version_of("codex", ["codex", "--version"])
    if not which("codex"):
        r = base_result("codex")
        r["status"] = STATUS_UNAVAILABLE
        r["message"] = "codex CLI not found on PATH."
        return r

    def invoke(absdir: str, task: str):
        # Prompt via stdin (`-`); sandbox limited to workspace write.
        argv = [
            "codex",
            "exec",
            "--model",
            "gpt-5.6-sol",
            "-c",
            "model_reasoning_effort=high",
            "--sandbox",
            "workspace-write",
            "--skip-git-repo-check",
            "--cd",
            absdir,
            "-",
        ]
        return run_argv(argv, timeout=LANE_TIMEOUT_S, input_text=task)

    return run_lane_harness("codex", invoke, ver)


def test_grok() -> dict[str, Any]:
    ver = version_of("grok", ["grok", "--version"])
    if not which("grok"):
        r = base_result("grok")
        r["status"] = STATUS_UNAVAILABLE
        r["message"] = (
            "grok CLI not found on PATH. Lane is DEPRECATED (subscription cancelled)."
        )
        return r

    def invoke(absdir: str, task: str):
        prompt_path = os.path.join(absdir, "task.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(task)
        argv = [
            "grok",
            "--prompt-file",
            prompt_path,
            "-m",
            "grok-4.5",
            "--always-approve",
            "--output-format",
            "plain",
            "--cwd",
            absdir,
        ]
        # stdin from /dev/null so an interactive TUI cannot hang on input.
        return run_argv(argv, timeout=LANE_TIMEOUT_S, stdin_devnull=True)

    return run_lane_harness("grok", invoke, ver)


# Fixed map: HTTP lane_id -> test function. Unknown ids → 400.
LANE_TESTS: dict[str, Callable[[], dict[str, Any]]] = {
    "gemini": test_gemini,
    "deepseek": test_deepseek,
    "codex": test_codex,
    "grok": test_grok,
}

LANE_META: dict[str, dict[str, str]] = {
    "gemini": {
        "name": "Gemini",
        "producer": "agy · gemini-3.1-pro-high",
        "note": "",
    },
    "deepseek": {
        "name": "DeepSeek",
        "producer": "kimi · deepseek-v4-flash (OpenRouter)",
        "note": "Requires one-time OpenRouter provider import in kimi.",
    },
    "codex": {
        "name": "Codex",
        "producer": "codex exec · gpt-5.6-sol (high)",
        "note": "",
    },
    "grok": {
        "name": "Grok",
        "producer": "grok · grok-4.5",
        "note": "DEPRECATED — subscription cancelled.",
    },
}


# ---------------------------------------------------------------------------
# Preflight + quota
# ---------------------------------------------------------------------------

def preflight() -> dict[str, Any]:
    """Cheap installed/version probes only — no model calls."""
    lanes: dict[str, Any] = {}

    # gemini / agy
    lanes["gemini"] = {
        "installed": bool(which("agy")),
        "version": version_of("agy"),
        "note": LANE_META["gemini"]["note"] or ("agy not on PATH" if not which("agy") else "ok"),
    }

    # deepseek / kimi
    kimi_ok = bool(which("kimi"))
    alias = discover_deepseek_alias() if kimi_ok else None
    if not kimi_ok:
        note = "kimi not on PATH"
    elif not alias:
        note = "OpenRouter provider not imported — operator must run the one-time setup"
    else:
        note = f"alias={alias}"
    lanes["deepseek"] = {
        "installed": kimi_ok,
        "version": version_of("kimi", ["kimi", "--version"]) if kimi_ok else None,
        "note": note,
    }

    # codex
    lanes["codex"] = {
        "installed": bool(which("codex")),
        "version": version_of("codex", ["codex", "--version"]),
        "note": LANE_META["codex"]["note"]
        or ("codex not on PATH" if not which("codex") else "ok"),
    }

    # grok
    lanes["grok"] = {
        "installed": bool(which("grok")),
        "version": version_of("grok", ["grok", "--version"]),
        "note": LANE_META["grok"]["note"],
    }

    return {"lanes": lanes}


def fetch_quota() -> dict[str, Any]:
    """Run the operator's collector --brief; never crash the server."""
    script = os.path.expanduser("~/repos/llm_usage/collector.py")
    if not os.path.isfile(script):
        return {
            "available": False,
            "reason": f"collector script not found at {script}",
        }
    try:
        r = run_argv(
            ["python3", script, "--brief"],
            timeout=QUICK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "collector.py timed out"}
    except OSError as e:
        return {"available": False, "reason": f"could not run collector: {e}"}

    text = (r.stdout or "").strip()
    if r.returncode != 0:
        err = clip((r.stderr or text), 500)
        return {
            "available": False,
            "reason": f"collector exited {r.returncode}: {err}",
        }
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Return a wrapped form if the script printed non-JSON.
        return {
            "available": False,
            "reason": "collector did not return JSON",
            "raw": clip(text, 1000),
        }


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lane health dashboard</title>
<style>
  :root {
    --bg: #f6f7f9;
    --fg: #1a1d23;
    --muted: #5c6570;
    --card: #ffffff;
    --border: #d8dee6;
    --pill-unknown: #9aa3ad;
    --pill-pass: #1a7f37;
    --pill-fail: #cf222e;
    --pill-amber: #9a6700;
    --pill-amber-bg: #fff8c5;
    --pill-pass-bg: #dafbe1;
    --pill-fail-bg: #ffebe9;
    --pill-unknown-bg: #eaeef2;
    --btn: #0969da;
    --btn-fg: #fff;
    --btn-disabled: #afb8c1;
    --danger-soft: #fff1f0;
    --code-bg: #f0f3f6;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d1117;
      --fg: #e6edf3;
      --muted: #8b949e;
      --card: #161b22;
      --border: #30363d;
      --pill-unknown: #8b949e;
      --pill-pass: #3fb950;
      --pill-fail: #f85149;
      --pill-amber: #d29922;
      --pill-amber-bg: #3d2e00;
      --pill-pass-bg: #12261a;
      --pill-fail-bg: #3d1214;
      --pill-unknown-bg: #21262d;
      --btn: #2f81f7;
      --btn-fg: #fff;
      --btn-disabled: #484f58;
      --danger-soft: #2a1215;
      --code-bg: #0d1117;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 1.25rem 1.5rem 3rem;
    font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--bg); color: var(--fg);
  }
  h1 { font-size: 1.35rem; margin: 0 0 0.25rem; }
  .sub { color: var(--muted); margin-bottom: 1.25rem; font-size: 0.92rem; }
  section {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 1rem 1.1rem; margin-bottom: 1rem;
  }
  section h2 { font-size: 1rem; margin: 0 0 0.75rem; }
  .legend { font-size: 0.9rem; color: var(--muted); }
  .legend dt { font-weight: 600; color: var(--fg); margin-top: 0.4rem; }
  .legend dd { margin: 0.1rem 0 0 0; }
  .quota-head { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
  .quota-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 0.6rem; margin-top: 0.75rem;
  }
  .qcard {
    border: 1px solid var(--border); border-radius: 8px; padding: 0.55rem 0.7rem;
    font-size: 0.88rem;
  }
  .qcard .name { font-weight: 600; }
  .qcard .pct { font-size: 1.15rem; margin: 0.15rem 0; }
  .qcard .st { color: var(--muted); text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.03em; }
  .actions { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.75rem; align-items: center; }
  button {
    appearance: none; border: none; border-radius: 6px;
    background: var(--btn); color: var(--btn-fg);
    padding: 0.45rem 0.85rem; font: inherit; font-weight: 600; cursor: pointer;
  }
  button:disabled { background: var(--btn-disabled); cursor: not-allowed; }
  button.secondary { background: transparent; color: var(--btn); border: 1px solid var(--border); }
  button.secondary:disabled { color: var(--btn-disabled); }
  .progress { color: var(--muted); font-size: 0.9rem; min-height: 1.2em; }
  .lane {
    display: grid;
    grid-template-columns: 1fr auto auto auto;
    gap: 0.6rem 0.9rem; align-items: center;
    padding: 0.7rem 0; border-top: 1px solid var(--border);
  }
  .lane:first-of-type { border-top: none; }
  .lane-name { font-weight: 600; }
  .lane-prod { color: var(--muted); font-size: 0.85rem; }
  .deprecated {
    display: inline-block; margin-left: 0.4rem; font-size: 0.72rem;
    font-weight: 700; letter-spacing: 0.04em; color: var(--pill-amber);
    border: 1px solid var(--pill-amber); border-radius: 4px; padding: 0 0.35rem;
    vertical-align: middle;
  }
  .pill {
    display: inline-block; min-width: 6.5rem; text-align: center;
    border-radius: 999px; padding: 0.2rem 0.65rem; font-size: 0.8rem;
    font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase;
    background: var(--pill-unknown-bg); color: var(--pill-unknown);
  }
  .pill.pass { background: var(--pill-pass-bg); color: var(--pill-pass); }
  .pill.fail { background: var(--pill-fail-bg); color: var(--pill-fail); }
  .pill.unavailable, .pill.timeout { background: var(--pill-amber-bg); color: var(--pill-amber); }
  .pill.invalid { background: var(--pill-fail-bg); color: var(--pill-fail); }
  .pill.running { background: var(--pill-unknown-bg); color: var(--muted); }
  .dur { color: var(--muted); font-variant-numeric: tabular-nums; min-width: 4rem; text-align: right; }
  details { grid-column: 1 / -1; }
  details summary { cursor: pointer; color: var(--muted); font-size: 0.85rem; }
  pre {
    margin: 0.4rem 0 0; padding: 0.65rem; background: var(--code-bg);
    border: 1px solid var(--border); border-radius: 6px;
    overflow: auto; max-height: 22rem; font-size: 0.78rem; line-height: 1.35;
    white-space: pre-wrap; word-break: break-word;
  }
  .err { color: var(--pill-fail); font-size: 0.9rem; }
  footer { margin-top: 1.5rem; color: var(--muted); font-size: 0.8rem; }
</style>
</head>
<body>
  <h1>Lane health dashboard</h1>
  <p class="sub">Click a lane to run a real end-to-end fix-and-verify test. Local only · 127.0.0.1</p>

  <section>
    <div class="quota-head">
      <h2 style="margin:0">Quota</h2>
      <button type="button" class="secondary" id="btn-quota">Refresh</button>
      <span class="progress" id="quota-status"></span>
    </div>
    <div class="quota-grid" id="quota-grid"><div class="qcard">Loading…</div></div>
  </section>

  <section>
    <h2>Legend</h2>
    <dl class="legend">
      <dt>pass (green)</dt>
      <dd>Lane ran and independent verification printed <code>PASS</code> — the fix worked.</dd>
      <dt>fail (red)</dt>
      <dd>Lane is broken or incomplete: the CLI ran, but verification still fails. Investigate the evidence.</dd>
      <dt>unavailable / timeout (amber)</dt>
      <dd>Not a broken lane — CLI missing, not authenticated, out of quota, not configured, or the call timed out. Fix setup or wait for quota; do not treat as a code defect.</dd>
      <dt>invalid</dt>
      <dd>Negative control unexpectedly passed before the lane ran (fixture was not broken) — the test would be vacuous.</dd>
      <dt>unknown (grey)</dt>
      <dd>Not tested yet this session.</dd>
    </dl>
  </section>

  <section>
    <h2>Lanes</h2>
    <div class="actions">
      <button type="button" id="btn-all">Test all lanes</button>
      <span class="progress" id="all-progress"></span>
    </div>
    <div id="lanes"></div>
  </section>

  <footer>Fixed lane ids only · client never supplies shell commands · temp evidence kept only on fail/invalid</footer>

<script>
const LANES = [
  { id: "gemini", name: "Gemini", producer: "agy · gemini-3.1-pro-high", deprecated: false },
  { id: "deepseek", name: "DeepSeek", producer: "kimi · deepseek-v4-flash (OpenRouter)", deprecated: false },
  { id: "codex", name: "Codex", producer: "codex exec · gpt-5.6-sol (high)", deprecated: false },
  { id: "grok", name: "Grok", producer: "grok · grok-4.5", deprecated: true },
];

const state = {}; // id -> { status, duration_s, evidence, running }

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === "className") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of kids) {
    if (c == null) continue;
    n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return n;
}

function pillClass(status) {
  if (!status || status === "unknown") return "pill";
  if (status === "running") return "pill running";
  return "pill " + status;
}

function renderLanes() {
  const root = document.getElementById("lanes");
  root.innerHTML = "";
  for (const lane of LANES) {
    const st = state[lane.id] || { status: "unknown", duration_s: null, evidence: null, running: false };
    const statusLabel = st.running ? "running…" : (st.status || "unknown");
    const dur = st.duration_s != null ? (st.duration_s.toFixed(1) + "s") : "—";
    const btn = el("button", {
      type: "button",
      text: st.running ? "Testing…" : "Test",
      disabled: st.running ? "disabled" : null,
      onclick: () => testOne(lane.id),
    });
    if (st.running) btn.disabled = true;

    const nameCell = el("div", null,
      el("div", { className: "lane-name" },
        lane.name,
        lane.deprecated ? el("span", { className: "deprecated", text: "DEPRECATED" }) : null
      ),
      el("div", { className: "lane-prod", text: lane.producer })
    );

    const details = el("details", null,
      el("summary", { text: "Evidence JSON" }),
      el("pre", { text: st.evidence ? JSON.stringify(st.evidence, null, 2) : "(not tested yet)" })
    );

    const row = el("div", { className: "lane", "data-lane": lane.id },
      nameCell,
      btn,
      el("span", { className: pillClass(st.running ? "running" : st.status), text: statusLabel }),
      el("span", { className: "dur", text: dur }),
      details
    );
    root.appendChild(row);
  }
  // Disable Test-all while any lane is running.
  const any = LANES.some(l => state[l.id] && state[l.id].running);
  const allBtn = document.getElementById("btn-all");
  if (allBtn && !allBtn.dataset.seq) allBtn.disabled = any;
}

async function testOne(id) {
  const prev = state[id] || {};
  state[id] = { ...prev, running: true, status: "running" };
  renderLanes();
  try {
    const res = await fetch("/api/test/" + encodeURIComponent(id), { method: "POST" });
    let body = null;
    try { body = await res.json(); } catch (_) { body = null; }
    if (!res.ok) {
      state[id] = {
        running: false,
        status: "fail",
        duration_s: null,
        evidence: body || { error: "HTTP " + res.status },
      };
    } else {
      state[id] = {
        running: false,
        status: body.status || "fail",
        duration_s: body.duration_s,
        evidence: body,
      };
    }
  } catch (err) {
    state[id] = {
      running: false,
      status: "fail",
      duration_s: null,
      evidence: { error: String(err), message: "Request failed — network or server error." },
    };
  }
  renderLanes();
}

async function testAll() {
  const btn = document.getElementById("btn-all");
  const prog = document.getElementById("all-progress");
  btn.disabled = true;
  btn.dataset.seq = "1";
  for (let i = 0; i < LANES.length; i++) {
    prog.textContent = "Testing " + LANES[i].name + " (" + (i + 1) + "/" + LANES.length + ")…";
    await testOne(LANES[i].id);
  }
  prog.textContent = "All lanes finished.";
  delete btn.dataset.seq;
  btn.disabled = false;
  renderLanes();
}

async function loadQuota() {
  const status = document.getElementById("quota-status");
  const grid = document.getElementById("quota-grid");
  const btn = document.getElementById("btn-quota");
  btn.disabled = true;
  status.textContent = "Refreshing…";
  try {
    const res = await fetch("/api/quota");
    const data = await res.json();
    grid.innerHTML = "";
    if (data.available === false) {
      grid.appendChild(el("div", { className: "qcard err", text: data.reason || "Quota unavailable" }));
      status.textContent = "Unavailable";
    } else if (data.lanes && typeof data.lanes === "object") {
      for (const [key, lane] of Object.entries(data.lanes)) {
        const pct = lane.pct_left != null ? Number(lane.pct_left).toFixed(0) + "%" : "—";
        const name = lane.name || key;
        const st = lane.status || "—";
        grid.appendChild(
          el("div", { className: "qcard" },
            el("div", { className: "name", text: name }),
            el("div", { className: "pct", text: pct + " left" }),
            el("div", { className: "st", text: String(st) })
          )
        );
      }
      status.textContent = data.generated ? ("as of " + data.generated) : "ok";
    } else {
      grid.appendChild(el("pre", { text: JSON.stringify(data, null, 2) }));
      status.textContent = "raw";
    }
  } catch (err) {
    grid.innerHTML = "";
    grid.appendChild(el("div", { className: "qcard err", text: String(err) }));
    status.textContent = "error";
  }
  btn.disabled = false;
}

document.getElementById("btn-all").addEventListener("click", testAll);
document.getElementById("btn-quota").addEventListener("click", loadQuota);
renderLanes();
loadQuota();
// Soft preflight note in console for operators debugging setup.
fetch("/api/preflight").then(r => r.json()).then(p => console.info("preflight", p)).catch(() => {});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    """Single-threaded request logic; server itself is ThreadingHTTPServer."""

    server_version = "LaneDashboard/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep logs minimal; never log bodies (could contain secrets in theory).
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: Any) -> None:
        data = json.dumps(obj, indent=2, default=str).encode("utf-8")
        self._send(code, data, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._send(200, HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/preflight":
                self._json(200, preflight())
                return
            if path == "/api/quota":
                self._json(200, fetch_quota())
                return
            self._json(404, {"error": "not found", "path": path})
        except Exception as e:  # noqa: BLE001 — never crash the server thread
            self._json(500, {"error": str(e), "trace": traceback.format_exc()[-500:]})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path.startswith("/api/test/"):
                lane_id = path[len("/api/test/") :].strip("/")
                # Fixed allow-list only — reject anything else.
                if lane_id not in LANE_TESTS:
                    self._json(
                        400,
                        {
                            "error": "unknown lane id",
                            "lane": lane_id,
                            "allowed": sorted(LANE_TESTS.keys()),
                        },
                    )
                    return
                # Drain body if any (we ignore it — never use as command input).
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                try:
                    result = LANE_TESTS[lane_id]()
                except Exception as e:  # noqa: BLE001
                    result = base_result(lane_id)
                    result["status"] = STATUS_FAIL
                    result["message"] = f"Internal test error: {e}"
                    result["verification_output"] = traceback.format_exc()[-2000:]
                self._json(200, result)
                return
            self._json(404, {"error": "not found", "path": path})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": str(e), "trace": traceback.format_exc()[-500:]})


def main() -> int:
    parser = argparse.ArgumentParser(description="Local lane health dashboard (127.0.0.1 only).")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to bind (default {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    httpd = ThreadingHTTPServer((BIND_HOST, args.port), Handler)
    url = f"http://{BIND_HOST}:{args.port}/"
    print(f"Lane health dashboard listening on {url}", flush=True)
    print("Fixed lanes: " + ", ".join(sorted(LANE_TESTS)), flush=True)
    print("Ctrl-C to stop.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
