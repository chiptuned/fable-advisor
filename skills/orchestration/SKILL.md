---
name: orchestration
description: Routing doctrine for the architect-as-orchestrator pattern — how a session running the smartest model delegates implementation to cheaper cross-vendor lanes to minimize cost. USE WHEN delegating implementation work, choosing between grok-implementer/kimi-implementer/codex-implementer lanes, writing a spec for a subagent, deciding whether to consult fable-advisor, managing session cost or token spend, or running any multi-task build where the session is the architect.
---

# Orchestration — the architect's routing doctrine

The session is the architect: it owns requirements, architecture, decomposition, specs, routing, and verification. It should almost never type implementation code. Every implementation task gets routed to the cheapest lane that is adequate for it — escalation is deliberate, per task, never a fixed binding.

## Cost and throughput — the prime directives

The session model is the most expensive lane in the system, on both input and output tokens — and it is also the bottleneck: nothing moves while it types. The economic case for this pattern is keeping its token volume low; the speed case is keeping cheap lanes running while it thinks. Spend Fable on judgment, spend the lanes on volume, and never let the architect be the only thing running. Four rules follow.

**Emit judgment, not volume.** The architect's output is decomposition, specs, routing decisions, verdicts on diffs, and short reports. It does not type implementation code, test bodies, boilerplate, or config files. A code block longer than an interface signature or a few illustrative lines is a spec that hasn't been delegated yet — stop and delegate it. Fixing a lane's bug by hand is the same failure in disguise: send a corrected spec back to the cheap lane instead.

**Keep the context lean.** Everything in the architect's context is re-read at architect prices on every turn. Delegate broad exploration, codebase searches, and log-grepping to a cheap read-only agent and keep only the conclusions; read files yourself only when the decision genuinely depends on the exact code. Don't paste long files, full diffs, or verbose command output into the conversation when a path reference or an excerpt will do.

**Reason once, then hand off.** Do the hard thinking — the architecture, the interface design, the debugging hypothesis — in one pass, capture it in the spec, and let the cheap lane carry it from there. Re-deriving decisions across turns burns the premium twice.

**Dispatch early, never idle.** Wall-clock speed comes from lanes running while the architect works, not from the architect typing faster. The moment a spec is finished, fire its lane and move to the next decision — don't hold the next dispatch hostage to the previous task's verification. Independent specs launch together in one message. An architect working alone while zero lanes run is the slow configuration, whatever it saves in coordination.

What stays with the architect regardless of cost: decomposition, interface design, hypothesis selection when debugging, spec writing, lane routing, and judging verification evidence. Those tokens are what the premium is for — everything else is a candidate for delegation.

## The lanes

| Lane | Producer | Invoke | Route here when |
|---|---|---|---|
| Routine | Grok 4.5 | `grok-implementer` agent | The spec fully determines the outcome: boilerplate, wiring, CRUD, mechanical edits, straightforward features. **Default lane.** Requires the [Grok CLI](https://x.ai/cli). |
| Trial | Kimi K3 | `kimi-implementer` agent | **Evaluation window — see below.** Reasoning between Grok 4.5 and GPT-5.6 Sol; throughput slightly behind Grok 4.5. Requires the [Kimi Code CLI](https://moonshotai.github.io/kimi-cli/) (`kimi`). |
| Cross-vendor | GPT-5.6 Sol (high reasoning) | `codex-implementer` agent | Correctness/completeness is critical enough to want a second implementation, or as the alternative family when the grok lane is unavailable. Requires the codex CLI. |
| Judgment | Fable 5 | `fable-advisor` agent | Not an implementation lane. See "Commitment boundaries" below. |

**Kimi evaluation window — through 2026-07-24.** Kimi K3 is under active evaluation: until the window closes, when the deciding rule below points at grok or codex, route to `kimi-implementer` instead unless the task is throughput-critical bulk (many mechanical files where grok's speed edge dominates) or correctness-critical enough to still warrant a codex race — in which case race kimi *against* that lane rather than skipping it. The point is to accumulate real evidence on kimi across the routine and reasoning bands, so a kimi lane left idle during the window is a routing failure. Note kimi's positioning honestly in reports: reasoning between Grok 4.5 and GPT-5.6 Sol, throughput slightly behind Grok 4.5. If kimi returns `unavailable`, fall back to the lane the deciding rule originally picked and say so. After 2026-07-24, this paragraph expires: revert to the deciding rule with grok as default, and keep kimi only where the trial's evidence earned it a place.

Deciding rule: how much does the outcome depend on judgment the spec can't capture? Little → the default grok lane; you will verify anyway. A lot, and mistakes are costly → race both lanes on the same spec and pick the stronger diff, or keep that piece with the architect.

Don't let task size argue for inline edits. A single small edit is faster by hand, but sessions are made of many — the honest comparison is a batch of inline edits done serially at the bottleneck versus one grok spec running while the architect thinks about the next thing. Batch related small edits into one delegated task; the architect types only when an edit is truly blocking and shorter than its own spec. If the grok lane sits unused for a whole session, that's a routing failure to explain, not a neutral outcome.

Grok vs codex is not a capability ranking — it's a failure-distribution question. Both are non-Anthropic families, so either lane's output gets genuine cross-vendor review from the Claude architect; racing them buys a *third* independent perspective for one extra lane's cost.

If a lane returns `unavailable` or `timeout`, re-route the same spec to the other lane and say so explicitly in your report — never quietly absorb the substitution. If both CLI lanes are unavailable, implement with a Claude subagent and state the downgrade plainly.

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

## Commitment boundaries

Consult `fable-advisor` (read-only, verdict in under 300 words) at the moments that decide whether the next hour is wasted:

- Before committing to an architecture, data migration, API shape, or refactor strategy
- Whenever the same problem has resisted two distinct attempts
- Once before declaring a multi-step deliverable done

Pass it the decision, the constraints, and the options considered. Act on the verdict or surface the disagreement — never silently ignore it. (If the session itself already runs on Fable, the advisor still earns its keep as a context-clean skeptic reading the actual code.)

## Verification

Reports are claims, not evidence. Before accepting any lane's work: read the diff, and re-run the verification command (or spot-check its quoted output against the working tree). "Should work", "tests should pass", or a report with no command output means the task is not done. A lane that reports a spec gap gets a corrected spec, not a "use your judgment".
