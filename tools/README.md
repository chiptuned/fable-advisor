# Lane health dashboard

Local, single-file operator console that runs a **real end-to-end test** of each
implementation lane (gemini/agy, deepseek/kimi, codex, grok) and shows
pass/fail with evidence. Opens in a browser; no install beyond Python 3.

## Run

```bash
python3 tools/lane_dashboard.py          # http://127.0.0.1:8787/
python3 tools/lane_dashboard.py --port 8791
```

stdlib only (`http.server`, `subprocess`, …). No pip packages, no CDNs.

## Safety

- Binds **127.0.0.1 only** (never `0.0.0.0`).
- HTTP never executes client-supplied commands: lane ids map to **hardcoded**
  test functions; unknown ids return 400. Subprocess calls use argv lists
  (`shell=False`).
- Each CLI call has an explicit timeout. Temp dirs are kept only on
  fail/invalid so you can inspect evidence.
- Does not read or log API keys. Real lane tests call paid APIs — use
  deliberately; the UI runs them **sequentially** when testing all lanes.
