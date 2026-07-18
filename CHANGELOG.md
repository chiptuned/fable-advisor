# Changelog — chiptuned/fable-advisor

## 3.7.0 — 2026-07-18 · SuperGrok Heavy

Operator moved base SuperGrok → SuperGrok Heavy.

- **Capacity (confirmed):** grok weekly ceiling ~99M → **~990M tok/week** (10×
  quota for 10× price, ~1 token/dollar, so per-token value unchanged at ~€0.07/Mtok
  — the ceiling moved, not the price). Grok Heavy is now the **least-constrained
  lane** and the primary sink for bulk/routine volume shifted off the halved
  (2026-07-20) Fable budget. Codex's standing role narrows to cross-vendor
  correctness + alternative-family fallback; it remains cheapest per-token but is
  no longer the capacity sink. Re-measure grok's concurrent-session ceiling on
  Heavy (was ×9 on base; Heavy differentiator is ~10× concurrency/compute).
- **Per-task quality (open evaluation, NOT a re-ranking):** Heavy advertises
  "16 agents collaborating"; whether that reaches the headless CLI is unverified.
  `--best-of-n` (headless-only) and `--agents` are exposed. Doctrine now says: race
  `grok-implementer --best-of-n` against codex on the next few hard/correctness-
  critical specs and move grok's band up **only if its diffs consistently win** —
  same discipline as the (closed) kimi trial. No routing change on marketing alone.
  grok-implementer agent gains an opt-in `--best-of-n` path for the eval.

## 3.6.0 — 2026-07-18 · Fleet rebalance (measured usage data)

Decisions made from measured per-lane quota, €/Mtok capacity price, throughput and
TTFT p50/p95 (operator's LLM-usage widget).

- **Kimi K3 trial lane RETIRED** (ran 3.4.0 → 3.5.2, 2026-07-16→18). Verdict on
  **capacity economics, not quality**: Allegretto (€39/mo) yields ~9M tok/week (5h
  window exhausts in hours); ~€1.00/Mtok at full capacity = 14× worse than grok,
  33× worse than codex; its reasoning band (between Grok 4.5 and GPT-5.6 Sol) is
  fully covered by the two kept lanes. Subscription cancelled; agent definition
  deleted. Do not re-add without materially changed pricing.
- **Doctrine rebalanced for the 2026-07-20 Anthropic change**: Fable 5 drops to 50%
  of Max-plan limits (measured weekly cap ~200M → ~100M against ~176M/week recent
  usage). Architect tokens are now the fleet's scarcest resource: inline architect
  implementation is a quota failure, codex explicitly absorbs bulk overflow
  (~157M tok/week at ~€0.03/Mtok, ~35% spare), grok stays default for routine
  (~99M tok/week, ~€0.07/Mtok, fastest TTFT). fable-advisor consults are exempt
  from rationing — they are cheap relative to architect typing.
- **Lane concurrency encoded** (measured/observed): grok ×9 concurrent without
  throttling (plus `--best-of-n` internal parallelism; ~8,300 req/window);
  codex ×2 observed, treat as moderate until measured higher. Sizing rule added:
  effective throughput = tok/s × safe concurrent instances. SuperGrok Heavy noted
  as a 10×-quota-for-10×-price headroom purchase only; ChatGPT Pro noted as the
  escape valve (its differentiator: Codex agent concurrency + ~3.2B tok/week).

## 3.5.x — 2026-07-17 · Grok lane repair

- Root-caused and fixed headless grok: `--always-approve` (not `--permission-mode
  auto`/`acceptEdits`, which don't land writes) and `--prompt-file`/`-p` (never a
  positional prompt — that's the interactive TUI). E2E-verified through the agent
  lane incl. a forced internal-subagent-spawn test. Doctrine notes the
  local-agent-mode subagent-spawn deadlock workaround and the stale-session trap.

## 3.4.x — 2026-07-16 · Kimi trial lane added (since retired, see 3.6.0)

## 3.3.x — 2026-07-16 · Throughput-first retune

- Fork of DannyMac180/fable-advisor with upstream PRs #2 #4 #5 merged; cursor lane
  (PR #7) and Smithers workflow (PR #6) dropped as unused. Throughput promoted to
  co-prime directive; parallel dispatch and anti-inline-edit batching added.
