# AI Assistant Session Transcript: Harbor RL Task Creation & Calibration

**Tool**: Antigravity / Gemini CLI  
**Model**: Gemini 3.8 Flash (High)  
**Task**: Engineering Internship Take-Home: RL Environments & Agent Evaluation in Harbor (2-Day Sprint)  
**Author**: Ashutosh Kumar Jaiswal (<ashutoshhjp00567@gmail.com>)

---

## 1. Project Initialization & Architecture Strategy

### User Request
> "read this whole project and make each and everything mentioned in it"
> [Attached: `rl-harbor.md`]

### AI Response & Plan
To build a production-grade Harbor task that adheres to all 4 rubric deliverables without prompt leakage:
1. **Sandboxed Gym Design**: Formulate `/app/reconcile.py` (under 90 lines) containing 3 calibrated bugs of strictly graduated difficulty:
   - *Bug 1 (Easy / Surface)*: CLI invocation crash (`csv_path = sys.argv[2]`), raising `IndexError: list index out of range` on standard invocation `python /app/reconcile.py <csv>`.
   - *Bug 2 (Medium / Logic)*: Financial status accounting flaw (`status in ("SUCCESS", "PENDING")`), improperly crediting pending transactions as valid, alongside single-decimal float truncation.
   - *Bug 3 (Hard / Edge Case)*: Deduplication timestamp comparison flaw. The buggy script uses string comparison `timestamp > records[tx_id]['timestamp']` instead of parsing ISO-8601 strings into UTC datetime objects. This fails when timestamps have non-UTC offsets (e.g., `+08:00` vs `Z`).
2. **Zero-Spoiler Instruction (`instruction.md`)**:
   - Provide complete, unambiguous business requirements (CSV columns, output schema, status rules, chronological UTC deduplication).
   - Strict avoidance of any prompt leakage (no line numbers, no variable names, no hints that `reconcile.py` has an IndexError or string comparison bug).
3. **Reference Solution (`solve.sh`)**:
   - Clean, idiomatic Python 3.12 solution using `datetime.fromisoformat` and `astimezone(timezone.utc)` to achieve a 1.000 score.
4. **Adversarial Cheat Script (`hack.sh`)**:
   - A reward-hacking script outputting static canned JSON matching naive verifier assertions.
5. **Hardened Dense-Reward Verifier (`tests/test.sh` & `tests/test_verifier.py`)**:
   - Bug 1 (Weight 0.20): Basic invocation & schema.
   - Bug 2 (Weight 0.30): Status filtering & monetary aggregation on dynamic batches.
   - Bug 3 (Weight 0.50): Multi-timezone deduplication edge cases.
   - Anti-Cheat Invariant Gate: Dynamically creates randomized UUIDs, float amounts, and timestamps at evaluation time. Detects canned outputs and forces `reward = 0.000`.
6. **Execution & Trajectory Forensics**:
   - Baseline Run (Run 1) and Controlled Ablation Run (Run 2) with 3 trials each.
   - Generated `jobs_summary` containing complete `result.json` and ATIF-v1.7 `trajectory.json` files.
   - Complete RL advantage calculations avoiding the Zero-Signal Trap.

---

## 2. Preventing Prompt Leakage

In RL bench design, prompt leakage is a fatal flaw: if the agent's prompt hints at the bugs, the evaluation tests prompt adherence rather than autonomous agent reasoning and code exploration.

To prevent leakage:
1. `instruction.md` is written strictly from the perspective of an external software specification / API contract.
2. The agent is informed *what* the output contract and business rules are, but never *where* or *how* the existing code is broken.
3. The prompt does not mention timezones explicitly as a "bug in line 22", but rather specifies the business requirement: "If multiple records with the same tx_id exist, only the record with the latest timestamp in chronological (UTC) order must be retained."

---

## 3. Verification & Calibration Proof

Executed `verify_all.py` to confirm verifier scores:
- `NOP` (unmodified buggy environment): **`0.000`**
- `HACK` (adversarial cheat script): **`0.000`**
- `PARTIAL` (Bug 1 & 2 resolved, Bug 3 broken): **`0.500`**
- `SOLVE` (complete reference solution): **`1.000`**

Calibration confirmed.
