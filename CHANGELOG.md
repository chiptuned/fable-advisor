# Changelog — chiptuned/fable-advisor

## 4.2.0 — 2026-08-07 · DeepSeek becomes the default; grok/kimi retired

Fleet reshaped after the operator cancelled the Grok and Kimi subscriptions and
downgraded the Claude plan. Measured 2026-08-07: codex **97% consumed (critical)** —
still functional, verified passing an end-to-end test at 3% remaining — Claude window
24% consumed (~3.1%/h), gemini 0%, grok 4% (cancelled, lapsing).

- **DeepSeek V4 Flash is the default implementer.** The reason is structural, not
  price: every other lane is subscription-metered and has a wall; DeepSeek is
  pay-per-token and only has a bill. Metered lanes are now the reserve, not the default.
- **New `codex-advisor` lane** (read-only, GPT-5.6 Sol high, `--sandbox read-only`):
  design/plan/diff review that would otherwise bill the Claude window. Doctrine prefers
  it over the Claude advisor **whenever codex has quota** — and at 3% remaining it still
  answers, so spend that remainder on advisory rather than implementation.
- **`fable-advisor` (Opus 5) stays the final judgment lane** at commitment boundaries.
- **Grok and Kimi retired as model lanes.** `agents/grok-implementer.md` is kept only
  while the cancelled subscription still answers; delete it once it stops. The `kimi`
  CLI survives purely as the *host* for the DeepSeek lane — no Moonshot model or quota.
- **Gemini 3.6 Pro watch**: Google is expected to announce it imminently. When it
  lands, check `agy models` for the slug and re-measure before promoting — a newer slug
  is a hypothesis, not an upgrade.
- **New `tools/lane_dashboard.py`**: a local (127.0.0.1-only, stdlib-only) web
  dashboard with one button per lane that runs a real end-to-end test — seeded bug,
  negative control checked first, independent re-verification — and distinguishes
  "broken" from "not configured / out of quota". Built because reading a report is not
  the same as watching it work. **Exercised for real before shipping**: gemini `pass`
  (23.7s), codex `pass` (19.8s, gpt-5.6-sol, no downgrade), deepseek correctly
  `unavailable` with the setup instruction — the "broken vs not configured" distinction
  verified end-to-end, not just smoke-tested.
- Obsolete grok-Heavy paragraphs (the `--best-of-n` quality evaluation, the ×9
  concurrency sizing) removed; parallelism guidance now keys off which lane can absorb
  a fan-out rather than a cancelled subscription's concurrency.

## 4.1.0 — 2026-08-01 · DeepSeek lane (OpenRouter) — elastic overflow

- **New `deepseek-implementer` lane**: DeepSeek V4 Flash
  (`deepseek/deepseek-v4-flash-0731`, 1M context, `tool_use`) via **OpenRouter**,
  hosted by the **`kimi` CLI as a generic agentic runner**. This is *not* the retired
  Moonshot/Kimi K3 model lane (retired 2026-07-18) — no Moonshot model or quota is
  involved; only the CLI is reused as a host.
- **Why codex could not host it**: codex 0.144.4 rejects `wire_api = "chat"`
  ("no longer supported", use `responses`), and OpenRouter exposes only
  `/api/v1/chat/completions` — no Responses API. Verified both ends before choosing a
  host, rather than assuming.
- **Role is elasticity, not savings.** $0.14 / 1M prompt and $0.28 / 1M completion,
  pay-per-token and **uncapped** — about 2.5× grok's per-token subscription rate. It is
  the only lane that keeps working when the owned subscriptions cap out. Route here on
  overflow-beyond-quota or for a fourth independent family; **no standing bulk role**
  while grok or codex have headroom.
- **Verified today**: the `kimi` host runs headless and *edits files* (`-p` mode,
  auto-approved tool calls, process-cwd discipline) — proven on a seeded bug with a
  failing negative control first. **Still unproven**: the OpenRouter pairing itself,
  which needs the operator's key; until the catalog import runs, the lane correctly
  reports `STATUS: unavailable` rather than guessing an alias.
- **Key handling**: the one-time import uses the `KIMI_REGISTRY_API_KEY` env fallback,
  never `--api-key` on the command line (argv is visible to `ps` and shell history).
  The lane never reads, echoes or logs the key.

## 4.0.0 — 2026-07-26 · Opus 5 is the architect and the advisor

Operator decision from published benchmarks: Opus 5 leads on the axes this pattern
actually uses — agentic terminal coding (43.3% vs 33.7%), knowledge work (GDPval-AA
1861 vs 1747), novel problem-solving (ARC-AGI-3 30.2% vs n/a), computer use (70.6% vs
66.1%), business workflows (26.0% vs 17.4%), agentic search (90.8% vs 87.4%). The
remaining counter-examples are within noise (HLE no-tools 56.5 vs 56.3, FrontierCode
53.5 vs 53.4); two apparent wins in that column are Mythos 5 rows, not Fable.

- **Advisor pinned to Opus 5**: `model: inherit` → **`model: opus`**, so a consult is
  worth the same from any session, including a cheap one (advisor-only mode).
- **Architect is Opus 5** throughout the doctrine, README, and manifests. The
  dual-Claude-window logic is gone: **everything Claude-side now shares one weekly
  all-models window** — architect turns, advisor consults, and every Claude subagent
  (Explore included). Switching Claude models buys no headroom; only pushing work to
  the external CLI lanes does. That asymmetry is stated as the core reason the pattern
  exists.
- `status: critical` on the Claude window now means: say so to the operator and spend
  the remainder on judgment only — consults and verification, never typing.
- Prior model is no longer referenced as an option anywhere in the live docs. Entries
  below are historical record and are left intact.

## 3.9.2 — 2026-07-26 · False-outage fix (PATH) + `critical` status

- **Root-caused a reported "gemini lane unavailable" that was not gemini.** `agy` and
  `grok` both install to `~/.local/bin`, which is exported only from the user's shell
  profile; a subagent shell that doesn't source it fails `command -v` and the lane
  correctly-but-wrongly reports `STATUS: unavailable` while the CLI works fine.
  Confirmed live: a gemini subagent reported `command -v agy` failing until it
  exported `PATH="$HOME/.local/bin:$PATH"`. Both preflights now harden the PATH first
  and are forbidden from declaring `unavailable` on a bare `command -v` miss.
- **Fleet health check, all three lanes green** (each verified independently by the
  architect, negative control failing first): grok **0.2.111**, codex **0.144.4** on
  gpt-5.6-sol (no downgrade, sandbox workspace-write), agy **1.1.7** via `--add-dir`.
  Diffs correctly scoped, verification files untouched in all three.
- **Doctrine: `status: critical` added** — the collector emits it (observed: Opus 5 at
  85% used, cap in 4.8h) but the section only described `ok|warn`. `critical` now means
  stop *starting* work there, and on a Claude window, tell the operator plainly rather
  than silently burning the remainder. Unrecognised statuses are treated as ≥ `warn`.
- Note: grok drifted 0.2.106 → 0.2.111 and agy 1.1.5 → 1.1.7 within days — the
  record-the-CLI-version rule keeps earning its place.

## 3.9.0 — 2026-07-26 · Opus 5 architects + usage-driven routing

- **Architect can be Fable 5 *or* Opus 5.** `fable-advisor` frontmatter changed
  `model: fable` → **`model: inherit`**, so the advisor follows whichever top model
  the session runs (documented value; invalid/unavailable pins silently fall back to
  the inherited model anyway). Doctrine, README, and lane table generalized from
  "Fable" to "the architect model", keeping the measured Fable-specific facts intact.
  Removed the stale README instruction to hand-edit `model: fable` → `model: opus`.
- **New doctrine section: "Dynamic routing from measured usage."** When the operator
  ships a usage collector (`python3 ~/repos/llm_usage/collector.py --brief`, JSON),
  the orchestrator prefers live quota over the static table: shed load on
  `recommend: false` / `status: warn`, treat `caps_before_reset: true` as the
  strongest shed signal, sink bulk into the highest `pct_left` **active** lane.
- **Fable and Opus are separate windows** (measured 2026-07-26: Fable 59% used /
  recommend, Opus 5 79% / warn / caps in 6.6h). When the session's own window is
  tight and the other has headroom, route `fable-advisor` consults to the model with
  room via a per-invocation model override (it beats `inherit`); if both are tight,
  push volume outward — Claude-side subagents (Explore included) bill the Claude
  window, CLI lanes never do.
- **Bulk sink is ranked by time-to-cap, not `pct_left`** (advisor consult caught this
  before it shipped): percentages have incomparable bases — grok's ~990M/week at 40%
  left still beats codex's ~157M/week at 70%, so percentage-ranking would flip bulk
  onto the smaller lane, cap it, and oscillate. Rank on `caps_in_h` vs `resets_in_h`
  (hours are comparable); `pct_left` is a tiebreak only. Also: re-run the collector
  *after* wide fan-outs, not only before — a big dispatch invalidates its own snapshot.
- **Documented the `best_lane` trap:** the collector ranks by free capacity, so a
  *cancelled* subscription scores perfect. Observed live: `best_lane: "kimi"` — a
  lane retired 2026-07-18. Never route on `best_lane` alone; intersect with the
  fleet's active lanes. Negative `resets_in_h` = stale row, not free capacity.
- **gemini-implementer verified as a spawned subagent** (not just direct CLI): fixed
  edge-case logic (malformed-input `None` handling + clamp) on agy **1.1.7**, diff
  scoped to the target file, assertions untouched. Note agy self-updated 1.1.5 →
  1.1.7 within days — the lane's "record the CLI version" rule is load-bearing.
- README install block corrected to `chiptuned/fable-advisor` (was pointing at
  upstream, which would install a different plugin).

## 3.8.0 — 2026-07-21 · Gemini lane (agy / Gemini 3.1 Pro)

- **New `gemini-implementer` lane**: drives the `agy` CLI (Google Antigravity CLI,
  v1.1.5) on **Gemini 3.1 Pro high** (`--model gemini-3.1-pro-high`) in headless
  print mode (`-p`). A third model family (Google) for cross-vendor diversity and
  three-way races. Authored via the grok lane; corrected and verified by the
  architect.
- **Verified end-to-end (2026-07-21)**: headless print + auth, and the file-write
  path — agy fixed a seeded single-file bug, the check passed, `git diff` scoped to
  the target only.
- **Two hard findings baked into the doc**: (1) `--mode accept-edits` is
  insufficient headless (auto-denies `read_file` → zero output); only
  `--dangerously-skip-permissions` works — parallels grok's `--always-approve`
  finding. (2) agy is **sandboxed to `~/.gemini/antigravity-cli/scratch` and ignores
  process cwd** — `--add-dir <absolute root>` is **mandatory** and the spec must use
  absolute paths; without it agy edits a private scratch copy and falsely reports
  success (empty `git diff` is the tell).
- **Economics unmeasured**: no per-token cost / weekly quota / concurrency numbers
  yet, so gemini gets **no standing bulk role** — cross-vendor/race use only until
  measured. Natural third contender for the open grok-Heavy quality evaluation.
- Requires `Bash(agy:*)` in the permission allowlist (added to user settings).

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
