---
name: orchestration
description: Routing doctrine for the architect-as-orchestrator pattern — how a session running the smartest model delegates implementation to cheaper cross-vendor lanes to minimize cost. USE WHEN delegating implementation work, choosing between grok-implementer/codex-implementer/gemini-implementer lanes, writing a spec for a subagent, deciding whether to consult fable-advisor, managing session cost or token spend, or running any multi-task build where the session is the architect.
---

# Orchestration — the architect's routing doctrine

The session is the architect: it owns requirements, architecture, decomposition, specs, routing, and verification. It should almost never type implementation code. Every implementation task gets routed to the cheapest lane that is adequate for it — escalation is deliberate, per task, never a fixed binding.

## Cost and throughput — the prime directives

The session model is the most expensive lane in the system, on both input and output tokens — and it is also the bottleneck: nothing moves while it types. Since 2026-07-20 it is also the scarcest: Fable 5 runs at 50% of Max-plan limits, and the architect's measured weekly budget sits *below* its recent usage. Architect tokens are now the binding constraint of the whole fleet — the external CLI lanes draw on separate vendor quotas and don't touch it. Spend Fable on judgment, spend the lanes on volume, and never let the architect be the only thing running. Four rules follow.

**Emit judgment, not volume.** The architect's output is decomposition, specs, routing decisions, verdicts on diffs, and short reports. It does not type implementation code, test bodies, boilerplate, or config files. A code block longer than an interface signature or a few illustrative lines is a spec that hasn't been delegated yet — stop and delegate it. Fixing a lane's bug by hand is the same failure in disguise: send a corrected spec back to the cheap lane instead. Under the halved Fable cap this is no longer just a cost failure — inline architect implementation spends the one quota the fleet cannot buy more of, so it is a quota failure too.

**Keep the context lean.** Everything in the architect's context is re-read at architect prices on every turn. Delegate broad exploration, codebase searches, and log-grepping to a cheap read-only agent and keep only the conclusions; read files yourself only when the decision genuinely depends on the exact code. Don't paste long files, full diffs, or verbose command output into the conversation when a path reference or an excerpt will do.

**Reason once, then hand off.** Do the hard thinking — the architecture, the interface design, the debugging hypothesis — in one pass, capture it in the spec, and let the cheap lane carry it from there. Re-deriving decisions across turns burns the premium twice.

**Dispatch early, never idle.** Wall-clock speed comes from lanes running while the architect works, not from the architect typing faster. The moment a spec is finished, fire its lane and move to the next decision — don't hold the next dispatch hostage to the previous task's verification. Independent specs launch together in one message. An architect working alone while zero lanes run is the slow configuration, whatever it saves in coordination.

What stays with the architect regardless of cost: decomposition, interface design, hypothesis selection when debugging, spec writing, lane routing, and judging verification evidence. Those tokens are what the premium is for — everything else is a candidate for delegation.

## The lanes

| Lane | Producer | Invoke | Route here when |
|---|---|---|---|
| Routine + bulk | Grok 4.5 | `grok-implementer` agent | The spec fully determines the outcome: boilerplate, wiring, CRUD, mechanical edits, straightforward features. **Default lane**, the parallelism workhorse, and — on SuperGrok Heavy — the high-capacity sink for bulk volume shifted off the halved Fable budget. Requires the [Grok CLI](https://x.ai/cli). |
| Cross-vendor | GPT-5.6 Sol (high reasoning) | `codex-implementer` agent | Correctness/completeness is critical enough to want a second implementation, and the alternative family when grok is unavailable. Cheapest per-token owned capacity. Requires the codex CLI. |
| Third family (Google) | Gemini 3.1 Pro (high) | `gemini-implementer` agent | A Google-family independent implementation, or a third diff in a race, when cross-vendor diversity is worth the extra lane. **Economics unmeasured — no standing volume role yet** (see capacity note). Requires the `agy` CLI (Google Antigravity CLI). |
| Judgment | Fable 5 | `fable-advisor` agent | Not an implementation lane. See "Commitment boundaries" below. |

Lane capacity and concurrency — measured/observed 2026-07, marked as such; re-measure before treating as constants:

- **grok** (SuperGrok **Heavy**, active since 2026-07-18): ~990M tok/week at ~€0.07/Mtok (Heavy is 10× base quota for 10× price — ~1 token per dollar, so per-token value is unchanged; the ceiling, not the price, is what moved). Fastest lane measured (TTFT p50 6.2s, highest tok/s). **Observed ×9 concurrent sessions without throttling on base; Heavy's real differentiator is ~10× concurrency/compute** — re-measure the concurrent-session ceiling on Heavy, don't assume it's still 9. Internal parallelism (`--best-of-n <N>`, headless-only; inline `--agents`) multiplies further. **This is now the least-constrained lane in the fleet and the primary sink for bulk/routine volume** — with Fable halved on 2026-07-20, grok Heavy absorbs essentially all volume shifted off the architect's budget.
- **codex** (ChatGPT Plus): ~157M tok/week at ~€0.03/Mtok — cheapest *per-token* owned capacity, ~35% spare. Concurrency cap undocumented; **observed ×2 fine — treat as moderate until measured higher**. Its standing role is now cross-vendor correctness and the alternative family when grok is unavailable, rather than the capacity sink (grok Heavy took that). ChatGPT Pro's differentiator is agent concurrency ("maximum access to Codex agent") plus ~20× volume (~3.2B tok/week, ~€0.013/Mtok): the escape valve if parallel codex demand or raw volume ever outgrows current caps; don't upgrade preemptively.
- **gemini** (`agy` CLI, Gemini 3.1 Pro high): added 2026-07-21. Per-token cost, weekly quota, and concurrency are **UNMEASURED** — do not give it a standing bulk/overflow role until they are. Verified working: headless single-file writes via `--add-dir <root>` + `--dangerously-skip-permissions` (the CLI is sandboxed and ignores cwd — `--add-dir` is mandatory; see the agent doc). Use it now for cross-vendor diversity (a Google third family in races), and measure it on a few real tasks — including the open grok-Heavy quality question, gemini is a natural third contender — before ranking it.
- **fable-advisor consults**: cheap and parallel-safe — but every Claude-side subagent draws on the post-2026-07-20 halved Fable quota, and the external CLI lanes don't. That asymmetry is now a core reason this pattern exists: state it, and push volume outward.

Lane history, so decisions aren't relitigated: a **Kimi K3 trial lane** ran 2026-07-16→18 and was **retired early on capacity economics, not quality** — ~€1.00/Mtok at full plan capacity (14× grok, 33× codex), ~9M tok/week on the viable plan tier, and a reasoning band already covered by the two kept lanes. Subscription cancelled; full rationale in CHANGELOG.md. Don't propose re-adding it without materially changed pricing.

Deciding rule: how much does the outcome depend on judgment the spec can't capture? Little → the default grok lane; you will verify anyway. A lot, and mistakes are costly → race both lanes on the same spec and pick the stronger diff, or keep that piece with the architect.

**Open evaluation — grok Heavy on hard specs (do not pre-judge).** SuperGrok Heavy advertises "16 AI agents collaborating" for higher-quality answers, and the CLI exposes `--best-of-n` (headless) and `--agents`. Whether that collaboration reaches the headless lane and *measurably* lifts `grok-implementer` on correctness-sensitive work is **unverified** — treat it as a hypothesis, not a re-ranking, exactly as the kimi trial was treated. Discipline: on the next few hard / correctness-critical tasks, race `grok-implementer` **with `--best-of-n` enabled** against `codex-implementer` on the same spec and record which diff wins. Only if grok's diffs consistently win does its band move up to take correctness work currently raced to codex. Until that evidence exists, grok stays the routine-and-bulk lane and codex keeps the correctness band. Do not adjust routing on the strength of the marketing.

Don't let task size argue for inline edits. A single small edit is faster by hand, but sessions are made of many — the honest comparison is a batch of inline edits done serially at the bottleneck versus one grok spec running while the architect thinks about the next thing. Batch related small edits into one delegated task; the architect types only when an edit is truly blocking and shorter than its own spec. If the grok lane sits unused for a whole session, that's a routing failure to explain, not a neutral outcome.

Grok vs codex is not a capability ranking — it's a failure-distribution question. Both are non-Anthropic families, so either lane's output gets genuine cross-vendor review from the Claude architect; racing them buys a *third* independent perspective for one extra lane's cost.

If a lane returns `unavailable` or `timeout`, re-route the same spec to the other lane and say so explicitly in your report — never quietly absorb the substitution. If both CLI lanes are unavailable, implement with a Claude subagent and state the downgrade plainly.

Known environment bug (observed 2026-07-17, Claude desktop local-agent-mode): spawning the `grok-implementer` subagent can deadlock on subagent-spawn permissions. That is a harness bug, not evidence about grok — when it bites, the architect runs the lane's sanctioned headless invocation directly in its own Bash (see the agent doc; one task per call, same spec contract and verification rules) and states the substitution in its report.

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

Sizing rule: **effective lane throughput = per-request tok/s × safe concurrent instances.** A slower lane with high parallelism beats a faster serial one for fan-out work — so racing and wide fan-outs default to the high-concurrency lane (grok, ×9 observed) and use codex at its moderate observed concurrency (×2) rather than assuming more. When a task decomposes into many independent specs, that decomposition is itself the argument for routing them to grok in parallel rather than queueing them anywhere serially.

## Commitment boundaries

Consult `fable-advisor` (read-only, verdict in under 300 words) at the moments that decide whether the next hour is wasted:

- Before committing to an architecture, data migration, API shape, or refactor strategy
- Whenever the same problem has resisted two distinct attempts
- Once before declaring a multi-step deliverable done

Pass it the decision, the constraints, and the options considered. Act on the verdict or surface the disagreement — never silently ignore it. (If the session itself already runs on Fable, the advisor still earns its keep as a context-clean skeptic reading the actual code.) A consult is a few hundred tokens of verdict against hours of misdirected lane work — cheap relative to architect typing even under the halved Fable cap. Do not ration consults to save quota; ration inline implementation instead.

## Verification

Reports are claims, not evidence. Before accepting any lane's work: read the diff, and re-run the verification command (or spot-check its quoted output against the working tree). "Should work", "tests should pass", or a report with no command output means the task is not done. A lane that reports a spec gap gets a corrected spec, not a "use your judgment".
