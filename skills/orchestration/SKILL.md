---
name: orchestration
description: Routing doctrine for the architect-as-orchestrator pattern — how a session running the smartest model delegates implementation to cheaper cross-vendor lanes to minimize cost. USE WHEN delegating implementation work, choosing between deepseek-implementer/gemini-implementer/codex-implementer/codex-advisor lanes, writing a spec for a subagent, deciding whether to consult fable-advisor, managing session cost or token spend, or running any multi-task build where the session is the architect.
---

# Orchestration — the architect's routing doctrine

The session is the architect: it owns requirements, architecture, decomposition, specs, routing, and verification. It should almost never type implementation code. Every implementation task gets routed to the cheapest lane that is adequate for it — escalation is deliberate, per task, never a fixed binding.

## Cost and throughput — the prime directives

The session model is the most expensive lane in the system, on both input and output tokens — and it is also the bottleneck: nothing moves while it types. **The architect runs on Opus 5**, the strongest model measured on agentic terminal coding, knowledge work, novel problem-solving, computer use, and business workflows — which is exactly the architect's job. It is also the scarcest resource in the fleet: **every Claude-side call shares one weekly all-models window** — the architect's own turns, the advisor, and every Claude subagent (Explore included) draw on the same pool, while the external CLI lanes draw on separate vendor quotas and never touch it. That asymmetry is the core reason this pattern exists. Spend the architect on judgment, spend the lanes on volume, and never let the architect be the only thing running. Four rules follow.

**Emit judgment, not volume.** The architect's output is decomposition, specs, routing decisions, verdicts on diffs, and short reports. It does not type implementation code, test bodies, boilerplate, or config files. A code block longer than an interface signature or a few illustrative lines is a spec that hasn't been delegated yet — stop and delegate it. Fixing a lane's bug by hand is the same failure in disguise: send a corrected spec back to the cheap lane instead. This is not just a cost failure — inline architect implementation spends the one quota the fleet cannot buy more of, so it is a quota failure too.

**Keep the context lean.** Everything in the architect's context is re-read at architect prices on every turn. Delegate broad exploration, codebase searches, and log-grepping to a cheap read-only agent and keep only the conclusions; read files yourself only when the decision genuinely depends on the exact code. Don't paste long files, full diffs, or verbose command output into the conversation when a path reference or an excerpt will do.

**Reason once, then hand off.** Do the hard thinking — the architecture, the interface design, the debugging hypothesis — in one pass, capture it in the spec, and let the cheap lane carry it from there. Re-deriving decisions across turns burns the premium twice.

**Dispatch early, never idle.** Wall-clock speed comes from lanes running while the architect works, not from the architect typing faster. The moment a spec is finished, fire its lane and move to the next decision — don't hold the next dispatch hostage to the previous task's verification. Independent specs launch together in one message. An architect working alone while zero lanes run is the slow configuration, whatever it saves in coordination.

What stays with the architect regardless of cost: decomposition, interface design, hypothesis selection when debugging, spec writing, lane routing, and judging verification evidence. Those tokens are what the premium is for — everything else is a candidate for delegation.

## The lanes

| Lane | Producer | Invoke | Route here when |
|---|---|---|---|
| **Default implementer** | DeepSeek V4 Flash (OpenRouter) | `deepseek-implementer` agent | **Almost everything.** The spec determines the outcome: boilerplate, wiring, CRUD, mechanical edits, straightforward features, bulk fan-out. Pay-per-token and uncapped — the only lane that cannot run out. Requires the `kimi` CLI as host plus a configured OpenRouter provider. |
| Second family | Gemini 3.1 Pro (high) | `gemini-implementer` agent | A second independent implementation, a race partner, or the fallback when the DeepSeek path is down. Subscription-metered; check live quota. Requires the `agy` CLI. |
| Advisory (non-Claude) | GPT-5.6 Sol (high reasoning) | `codex-advisor` agent | Design review, plan critique, diff review — **preferred over the Claude advisor whenever it has quota**, precisely to spare the Claude window. Read-only, never edits. Requires the codex CLI. |
| Implementation (non-Claude) | GPT-5.6 Sol (high reasoning) | `codex-implementer` agent | Correctness-critical work worth a second implementation, when codex has quota to spare. |
| Judgment (final) | Opus 5 | `fable-advisor` agent | Not an implementation lane. The decision-maker of last resort at commitment boundaries — see below. |

Lane capacity — measured 2026-08-01. Re-measure before treating as constants; the live collector below always wins over this table.

- **deepseek** (`kimi` CLI hosting OpenRouter, `deepseek/deepseek-v4-flash-0731`): **$0.14 / 1M prompt, $0.28 / 1M completion, pay-per-token and UNCAPPED.** 1M context, `tool_use` supported. It is now the **default implementer** for a structural reason, not a price one: every other lane in this fleet is subscription-metered and therefore has a wall, while this one only has a bill. Prefer it for the bulk of implementation so the metered lanes stay in reserve for what only they can do. Cost control is the architect's job — batch related edits into one spec rather than paying per round-trip.
- **gemini** (`agy` CLI, Gemini 3.1 Pro high): subscription-metered, measured 0% consumed on 2026-08-01 — currently the healthiest metered lane. Verified working end-to-end. **`--add-dir <absolute root>` is mandatory** (the CLI is sandboxed and ignores process cwd; without it, it edits a private scratch copy and reports success — an empty `git diff` is the tell). Google is expected to announce **Gemini 3.6 Pro** imminently: when it lands, check `agy models` for the new slug, treat it as a candidate default for this lane, and re-measure before promoting it — a newer slug is a hypothesis, not an upgrade.
- **codex** (ChatGPT Plus, GPT-5.6 Sol high): measured **97% consumed, `critical`** on 2026-08-01. Hosts two lanes — `codex-advisor` (read-only review, the preferred advisory path when it has quota) and `codex-implementer`. Both are effectively unavailable until the window resets; expect `STATUS: unavailable` and fall back rather than retrying. When it does have room, spend it on **advisory** first: that is the work that otherwise bills the Claude window.
- **Claude window** (Opus 5): measured 24% consumed, burn ~3.1%/h on 2026-08-01. Everything Claude-side shares it — architect turns, `fable-advisor` consults, and every Claude subagent including Explore. The external CLI lanes never touch it. This asymmetry is the whole point of the pattern.
- **Retired / lapsing:** the Grok lane (SuperGrok Heavy) and the Kimi K3 model lane were both **cancelled by the operator** (2026-08-01 and 2026-07-18). Neither has a standing role. `agents/grok-implementer.md` is kept only while the cancelled subscription still answers — do not route to it by default, and delete it once it stops. The `kimi` CLI survives purely as the *host* for the DeepSeek lane; no Moonshot model or quota is involved.

### Dynamic routing from measured usage

The static numbers above age. When the operator provides a usage collector, prefer *live* quota over the table. Run it at session start, **before *and after* any large fan-out** (a wide dispatch burns enough to invalidate the snapshot it was routed on — routing the next fan-out on pre-burn data is how you overshoot a cap), and whenever a lane misbehaves. It is one cheap shell call, not a per-task ritual:

```bash
python3 ~/repos/llm_usage/collector.py --brief   # operator's path; JSON on stdout
```

It emits, per lane: `pct_used` / `pct_left`, `window`, `resets_in_h`, `caps_in_h`, `caps_before_reset`, `burn_pct_per_h`, `status` (`ok` | `warn` | `critical` — and treat any unrecognised value as at least as severe as `warn`, never as `ok`), and `recommend` (bool) — plus a top-level `best_lane` and a `note` that the data is advisory.

How to act on it:

- **`recommend: false` or `status: warn`** → stop sending that lane new bulk work; finish what's in flight and shift the queue elsewhere. **`status: critical`** → stop *starting* anything there, including small work; on a Claude window it means the session itself is close to the wall — say so plainly to the operator rather than quietly burning the remainder.
- **`caps_before_reset: true`** → that lane runs out *before* its window resets; combined with `caps_in_h` and `burn_pct_per_h` it tells you how long you can keep spending. Treat it as the strongest shed-load signal in the payload.
- **Pick the bulk sink by *time*, not percentage.** Among lanes that are both *active* and hold a *standing volume role* (today: grok and codex — a lane with unmeasured economics like gemini does **not** win bulk work by having an untouched quota), rank by **`caps_in_h` against `resets_in_h`**: time-to-cap at current burn versus time-to-refill. Hours are comparable across providers; percentages are not, because each lane's 100% is a different absolute size (grok ~990M/week vs codex ~157M/week — grok at 40% left still holds ~4× codex's 70%). Use `pct_left` only as a tiebreak, and break remaining ties toward the larger measured absolute quota. Cross-check the concurrency notes above: capacity and parallelism are different constraints.
- **Architect side:** there is one Claude window and everything Claude-side shares it. When it goes `warn`, push harder outward — bigger batches per lane spec, shorter architect output, fewer Claude subagents (Explore included). When it goes `critical`, say so to the operator and spend what remains on judgment only: consults and verification, never typing. Reaching for a different Claude model does not buy headroom — it is the same pool.

Traps — the payload is advisory, not an oracle:

- **Never route on `best_lane` alone.** It ranks by free capacity, so a *cancelled or retired* subscription scores perfect (0% used, 100% left) and wins. Observed 2026-07-26: `best_lane: "kimi"` — a lane retired on 2026-07-18. Always intersect the collector's lanes with the fleet's actually-active lanes (grok, codex, gemini + the Claude windows); ignore rows for lanes this doctrine no longer runs.
- **"Unused" is not "best" — the same trap has two faces.** A retired lane and a *brand-new, unmeasured* lane both show ~100% left. Verified 2026-07-26: ranking active lanes purely by `pct_left` promoted gemini (100% left, economics unmeasured) over grok Heavy for bulk. Free quota is a permission to spend, never on its own a reason to.
- **Negative `resets_in_h` means stale data** (window already elapsed, nothing refreshed it) — treat that row as unknown, not as free capacity.
- **`pct_left` is not throughput.** A lane with quota but poor concurrency won't clear a fan-out faster than a busier high-concurrency lane; apply the sizing rule from "Parallelism".
- The collector's own `note` says provider-reported *or estimated*. Never let it override a hard failure signal from a lane's own report (`unavailable`, `timeout`, auth error) — live evidence beats projected quota.

Lane history, so decisions aren't relitigated: a **Kimi K3 trial lane** ran 2026-07-16→18 and was **retired early on capacity economics, not quality** — ~€1.00/Mtok at full plan capacity (14× grok, 33× codex), ~9M tok/week on the viable plan tier, and a reasoning band already covered by the two kept lanes. Subscription cancelled; full rationale in CHANGELOG.md. Don't propose re-adding it without materially changed pricing.

Deciding rule: how much does the outcome depend on judgment the spec can't capture? Little → the default deepseek lane; you will verify anyway. A lot, and mistakes are costly → race deepseek against gemini on the same spec and pick the stronger diff, or keep that piece with the architect. Escalate to codex only when its quota allows and the correctness stakes justify spending a metered lane.

Don't let task size argue for inline edits. A single small edit is faster by hand, but sessions are made of many — the honest comparison is a batch of inline edits done serially at the bottleneck versus one grok spec running while the architect thinks about the next thing. Batch related small edits into one delegated task; the architect types only when an edit is truly blocking and shorter than its own spec. If the default implementer lane sits unused for a whole session, that's a routing failure to explain, not a neutral outcome.

DeepSeek vs gemini vs codex is not a capability ranking — it's a failure-distribution question. All three are non-Anthropic families, so any lane's output gets genuine cross-vendor review from the Claude architect; racing two of them buys a third independent perspective for one extra lane's cost.

If a lane returns `unavailable` or `timeout`, re-route the same spec to the other lane and say so explicitly in your report — never quietly absorb the substitution. If both CLI lanes are unavailable, implement with a Claude subagent and state the downgrade plainly.

Known environment bug (observed 2026-07-17, Claude desktop local-agent-mode): spawning an implementer subagent can deadlock on subagent-spawn permissions. That is a harness bug, not evidence about grok — when it bites, the architect runs the lane's sanctioned headless invocation directly in its own Bash (see the agent doc; one task per call, same spec contract and verification rules) and states the substitution in its report.

One recoverable `unavailable` case: when codex reports `sandbox denied writes` (a host-side sandbox bug — the workspace-write ACE grant fails and the failure is cached; observed on Windows), you may resend the same spec with the line `sandbox-fallback: allowed` if the operator accepts codex running under their own configured sandbox mode; the lane then retries once without `--sandbox` and marks the report `SANDBOX: downgraded`.

## The spec contract

Implementers share none of your conversation context. Every delegation prompt carries all five parts:

1. **Objective** — what to build or change, one paragraph
2. **Files** — exact paths to create or modify
3. **Interfaces** — signatures, types, or API shapes the code must match
4. **Constraints** — project conventions, things not to touch
5. **Verification** — the command(s) that prove it works

A spec you can't finish writing is a signal the decision isn't made yet — that's architect work, not a reason to hand the ambiguity to a cheaper model.

## Parallelism

Independent specs (no shared files, no ordering dependency) launch as parallel agents in a single message — this is the main throughput lever. Dispatch each lane as soon as its spec is written; verify finished lanes while later ones are still running. Sequential chains and single-file surgery stay serial. For high-stakes work, a pick-the-stronger-diff race — `grok-implementer` and `codex-implementer` on the same spec, architect judges — buys three-vendor confidence for one extra lane's cost.

Sizing rule: **effective lane throughput = per-request tok/s × safe concurrent instances.** A slower lane with high parallelism beats a faster serial one for fan-out work — so racing and wide fan-outs default to the lane that can actually absorb them. DeepSeek has no quota wall, which makes it the natural fan-out target; gemini and codex are metered, so size their share against live quota. When a task decomposes into many independent specs, that decomposition is itself the argument for dispatching them in parallel rather than queueing them serially.

## Commitment boundaries

Consult `fable-advisor` (read-only, verdict in under 300 words) at the moments that decide whether the next hour is wasted:

- Before committing to an architecture, data migration, API shape, or refactor strategy
- Whenever the same problem has resisted two distinct attempts
- Once before declaring a multi-step deliverable done

Pass it the decision, the constraints, and the options considered. Act on the verdict or surface the disagreement — never silently ignore it. (Even when the session already runs Opus 5 itself, the advisor earns its keep as a context-clean skeptic reading the actual code, free of the conversation's accumulated assumptions.) A consult is a few hundred tokens of verdict against hours of misdirected lane work — cheap relative to architect typing. Do not ration consults to save quota; ration inline implementation instead.

## Verification

Reports are claims, not evidence. Before accepting any lane's work: read the diff, and re-run the verification command (or spot-check its quoted output against the working tree). "Should work", "tests should pass", or a report with no command output means the task is not done. A lane that reports a spec gap gets a corrected spec, not a "use your judgment".
