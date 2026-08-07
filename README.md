# Fable Advisor — chiptuned fork

> **This is [chiptuned](https://github.com/chiptuned)'s throughput-first fork of [DannyMac180/fable-advisor](https://github.com/DannyMac180/fable-advisor).** Differences from upstream: all open upstream PRs merged (#2 #4 #5), routing doctrine retuned to prioritize wall-clock throughput and the architect's quota (parallel dispatch, early hand-off, anti-inline-edit batching, measured lane concurrency), and no cursor/Smithers lanes. Grok and Kimi lanes were retired when those subscriptions were cancelled (see CHANGELOG.md); DeepSeek via OpenRouter is now the default implementer. Install: `claude plugin marketplace add chiptuned/fable-advisor`.

**The smartest model runs the show. Cheaper models do the typing.**

Claude Code lets every subagent run on a different model — and lets the session itself run on a different model than its subagents. This plugin exploits that with the **architect pattern**: your session runs on **Opus 5**, Anthropic's most capable model, acting as a full-time architect. It owns requirements, decomposition, specs, and verification — and routes every implementation task to the cheapest adequate lane:

| Lane | Producer | Invocation | Route here when |
|---|---|---|---|
| **Default implementer** | **DeepSeek V4 Flash** (OpenRouter) | `deepseek-implementer` agent | Almost everything — pay-per-token and uncapped, hosted by the `kimi` CLI. The only lane without a wall |
| Second family | Gemini 3.1 Pro (high) | `gemini-implementer` agent | Independent second diff, race partner, or fallback — via the `agy` CLI |
| Advisory (non-Claude) | GPT-5.6 Sol (high reasoning) | `codex-advisor` agent | Design/plan/diff review, read-only — preferred over the Claude advisor whenever codex has quota |
| Implementation (non-Claude) | GPT-5.6 Sol (high reasoning) | `codex-implementer` agent | Correctness-critical second implementation, quota permitting |
| Judgment (final) | **Opus 5** | `fable-advisor` agent | Commitment boundaries — the decision-maker of last resort |

Tokens route by volume: the expensive model emits the fewest tokens (judgment and specs), cheap lanes emit the most (code). Implementation mechanics are ~90% of a session's tokens and the external lanes handle them at near-parity — so this runs far cheaper than Opus-for-everything, and every implementation comes from a *different model family* than the architect that reviews it: cross-vendor review is built into the routing, not bolted on. For high-stakes work, race `deepseek-implementer` and `gemini-implementer` on the same spec and let the architect pick the stronger diff.

The plugin ships the **orchestration skill** — the routing doctrine that teaches the session when to use each lane, the cost discipline that keeps the expensive model's own token volume minimal (emit judgment not volume, keep context lean, reason once then hand off), the five-part spec contract that makes context-free delegation safe, and the verification rules that keep cheap lanes honest.

## Install

```
claude plugin marketplace add chiptuned/fable-advisor
claude plugin install fable-advisor@fable-advisor
```

Updating an existing installation to the latest release:

```
claude plugin marketplace update fable-advisor
claude plugin update fable-advisor@fable-advisor
```

Then start your session as the architect:

```
/model opus
```

**Lite mode — one file, 30 seconds.** Don't want the full pattern? Copy [`agents/fable-advisor.md`](agents/fable-advisor.md) into `~/.claude/agents/` and keep your session on Sonnet. You get advisor consults at commitment boundaries without the orchestration layer (see "Advisor-only mode" below).

## Requirements

- **Claude Code ≥ 2.1.170** with a subscription that includes Opus 5 (Pro, Max, Team, or Enterprise — all current consumer plans qualify).
- The advisor is pinned to `model: opus`, so it stays Opus 5 even when consulted from a cheaper session. The caller can override the model per consult (see "Dynamic routing from measured usage" in the orchestration skill).
- **DeepSeek lane (the default implementer):** needs the `kimi` CLI as host plus an OpenRouter provider. One-time setup — put your OpenRouter key in a dotenv or export it, then import the provider (the env fallback keeps the key out of `argv`, where `ps` and shell history would see it):

  ```
  export KIMI_REGISTRY_API_KEY='<your OpenRouter key>'
  kimi provider catalog add openrouter --default-model deepseek/deepseek-v4-flash-0731
  ```

  Until that import runs, the lane reports `STATUS: unavailable` rather than guessing.
- **Gemini lane:** needs the `agy` CLI (Google Antigravity) authenticated. `--add-dir <absolute root>` is mandatory — the CLI is sandboxed and ignores the process cwd.
- **Codex lane (optional):** the `codex-implementer` agent needs the [OpenAI Codex CLI](https://github.com/openai/codex) installed and authenticated (`npm i -g @openai/codex`, then `codex login`). It invokes **GPT-5.6 Sol** as `gpt-5.6-sol` with `model_reasoning_effort=high`. GPT-5.6 access may be limited during preview; without model access, an installed/authenticated CLI, or successful authentication, the agent reports `STATUS: unavailable` and the other lanes remain unaffected.
- Heads-up: if a pinned Claude model isn't available on your account, Claude Code silently falls back to your session model — the pattern degrades quietly rather than erroring. If results feel unremarkable, check your plan. (This quiet fallback applies only to Claude model pins — the external CLI lanes always fail loudly with a structured error.)
- **`~/.local/bin` on PATH:** `agy`, `kimi` and `grok` install there, and a shell that doesn't source your profile won't find them — the classic false outage. Every lane preflight hardens the PATH before concluding a CLI is missing.
- **Check the lanes yourself:** `python3 tools/lane_dashboard.py` serves a local dashboard (127.0.0.1 only) with one button per lane that runs a real seeded-bug test and shows the evidence.

Model resolution order in Claude Code: `CLAUDE_CODE_SUBAGENT_MODEL` env var → per-invocation `model` parameter → agent frontmatter → session model.

## Use it

With the session on Opus 5, just ask for work — the orchestration skill routes it:

```
Add rate limiting to our public API. Design it, delegate the
implementation, and verify the evidence before you call it done.
```

The architect writes the spec, picks the lane (rate limiting touches concurrency — a good case for racing `deepseek-implementer` against `gemini-implementer` and picking the stronger diff), reads the diff and verification evidence when the report comes back, and only then reports done.

To make the doctrine always-on, add one line to your project's `CLAUDE.md`:

```
You are the architect running the most expensive model — minimize your
own token volume. Delegate all implementation through the orchestration
skill's routing table (never type code yourself), delegate broad codebase
exploration to cheap read-only agents, and verify evidence before
accepting any lane's report.
```

## Commitment boundaries

Even the architect gets a second opinion. The `fable-advisor` agent is a read-only skeptic — consulted before architecture decisions, migrations, API designs, and whenever a problem has resisted two attempts. It reads your actual code and returns a verdict in under 300 words. It never implements. Running it from an Opus 5 session still pays: it sees the code fresh, without your conversation's accumulated assumptions.

## Advisor-only mode (the original pattern)

The inverse arrangement, for when you'd rather keep the session cheap: run the session on Sonnet and consult `fable-advisor` only at commitment boundaries.

```
Migrate our checkout sessions from Postgres to Redis — plan it,
consult your advisor before committing, then implement.
```

A typical consult costs cents. To make it automatic, add to your project's `CLAUDE.md`:

```
Before committing to any architecture decision, migration, or refactor
touching 3+ files, consult the fable-advisor agent and act on its verdict.
```

## FAQ

**Is this Anthropic's "advisor tool"?** No — that's a server-side API feature. These are plain Claude Code subagents plus a skill: readable, editable, no beta flags.

**Does this work on claude.ai?** No — subagent model routing is Claude Code only (CLI, desktop, VS Code, web).

**Why not just run everything on Opus 5?** You can. It's excellent. It's also the most expensive lane per token, and most of a session's tokens are implementation mechanics that the cheap lanes handle at near-parity. Spend the premium where judgment lives.

**Upgrading from v2?** v3 replaced the Sonnet/Opus `implementer` agent with `grok-implementer` — Grok 4.5 via the [Grok CLI](https://x.ai/cli) is now the default typing lane. v3.1 upgrades the optional `codex-implementer` lane from GPT-5.5 to GPT-5.6 Sol at high reasoning. The `fable-advisor` agent and advisor-only mode work exactly as before. If you preferred the Claude implementer, grab [`implementer.md` from the v2.1.0 tag](https://github.com/DannyMac180/fable-advisor/blob/3c1846c/agents/implementer.md).

**Why Grok and GPT-5.6 Sol lanes in a Claude plugin?** Vendor diversity. Models from one family share blind spots; an independent implementation from a different lineage catches what same-family review misses — and with Claude as the architect, *every* diff now gets cross-vendor review for free. The architect stays Claude — the lanes are producers, not judges.

## Go deeper

I write [**Attention Heads**](https://attentionheads.substack.com/?utm_source=github&utm_medium=readme&utm_campaign=fable-advisor) — deep, evidence-backed writing on AI, cognition, and agentic engineering. The **Agentic Engineering Field Notes** series is where I publish practical advice on the craft of using AI. [Subscribe](https://attentionheads.substack.com/subscribe?utm_source=github&utm_medium=readme&utm_campaign=fable-advisor) to get new posts to your inbox.

## License

MIT
