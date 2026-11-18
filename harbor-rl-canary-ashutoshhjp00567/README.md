# Harbor RL Submission — Ashutosh Kumar Jaiswal (@ashutoshhjp00567)

## 1. Loom Walkthrough Video
- **Video URL:** [Watch 5-Minute Walkthrough](https://www.loom.com/share/YOUR_VIDEO_ID)  
  *(Link sharing set to "Anyone with the link can view". See `VIDEO_WALKTHROUGH_SCRIPT.md` for the exact minute-by-minute transcript and script).*

---

## 2. Task & Calibration Summary
- **Bug 1 (Easy — Surface Bug):** A broken CLI argument index (`csv_path = sys.argv[2]` instead of `sys.argv[1]`) that immediately raises `IndexError: list index out of range` upon standard execution.
- **Bug 2 (Medium — Logic Bug):** Faulty transaction status filtering that counts unconfirmed `PENDING` rows as valid (`if status in ("SUCCESS", "PENDING"):`) and truncates floats to single-decimal precision (`round(total, 1)`).
- **Bug 3 (Hard — Edge Case):** Subtle deduplication defect where repeat `tx_id` records are compared lexicographically as raw ISO strings (`timestamp > records[tx_id]["timestamp"]`) instead of normalized chronological UTC datetime objects, failing across mixed timezone offsets (e.g., `+08:00` vs `Z`).
- **Calibration Scores:**  
  `nop` = **`0.000`** | `oracle` (`solve.sh`) = **`1.000`** | Partial `oracle` (Bug 1+2 fixed, Bug 3 broken) = **`0.500`** | `hack.sh` = **`0.000`**

---

## 3. Ablation & RL Advantage Table (`terminus-2`, `k=3` Trials)

| Run | Change Tested | Trial 1 (Binary / Dense) | Trial 2 (Binary / Dense) | Trial 3 (Binary / Dense) | Mean Binary | Mean Dense ($\bar{R}$) | Binary Advantage ($R_1-\bar{R}, R_2-\bar{R}, R_3-\bar{R}$) | Dense Advantage ($R_1-\bar{R}, R_2-\bar{R}, R_3-\bar{R}$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Run 1: Baseline** | Original 3-bug task (no sample file, agent creates ad-hoc test) | `0.0 / 0.50` | `0.0 / 0.20` | `0.0 / 0.00` | `0.00` | `0.233` | `[0.00, 0.00, 0.00]` | `[+0.267, -0.033, -0.233]` |
| **Run 2: Ablation** | Added `/app/sample_transactions.csv` with multi-timezone duplicate records | `1.0 / 1.00` | `1.0 / 1.00` | `0.0 / 0.50` | `0.667` | `0.833` | `[+0.333, +0.333, -0.667]` | `[+0.167, +0.167, -0.333]` |

---

## 4. Trajectory Forensics (`trajectory.json`)
- **Where the Agent Failed in Run 1:**  
  In Baseline Trial 1 (`jobs_summary/run1_baseline/reconcile-bug__trial-1/agent/trajectory.json`, Step 7), the agent executed `echo 'tx_id,timestamp,amount,status\nT1,2026-01-01T10:00:00Z,10.0,SUCCESS' > /tmp/test.csv && python /app/reconcile.py /tmp/test.csv`. Because the synthetic test CSV contained only a single UTC row without duplicate `tx_id`s or varying timezone offsets (`+08:00`), the agent verified that Bug 1 and Bug 2 passed, concluded its job was complete, and terminated without testing Bug 3.
- **Ablation Hypothesis & Result:**  
  We hypothesized that providing an in-container fixture (`/app/sample_transactions.csv`) containing non-trivial duplicate records across distinct timezone offsets (`2026-03-01T16:00:00+08:00` vs `2026-03-01T11:00:00Z`) would induce the agent to test edge cases before stopping. In Ablation Trial 1 (Step 5), running `python /app/reconcile.py /app/sample_transactions.csv` immediately exposed to the agent that the `FAILED` transaction was erroneously selected over the later `SUCCESS` transaction due to string comparison. The agent promptly implemented `datetime.fromisoformat(...).astimezone(timezone.utc)`, achieving a `1.000` score.

---

## 5. Dense Reward & Anti-Cheat Design
- **My Dense Reward Weights (`tests/test.sh`):**  
  Points are structured hierarchically:
  - **Bug 1 (Surface CLI & JSON contract):** `0.20` — verifies script execution without crash, argument parsing, and standard JSON schema.
  - **Bug 2 (Logic & Status Aggregation):** `0.30` — verifies accurate exclusion of `PENDING` records, aggregation of `SUCCESS` and `FAILED` rows, and 2-decimal rounding.
  - **Bug 3 (Edge Case Deduplication):** `0.50` — verifies multi-timezone UTC-normalized deduplication.
  This awards incremental credit for partial progress (`0.20`, `0.50`, `1.00`) while ensuring unhandled crashes remain `0.00`.
- **How `solution/hack.sh` Cheated & How I Blocked It:**  
  `solution/hack.sh` bypassed reconciliation by replacing `/app/reconcile.py` with a dummy script returning a static canned JSON payload (`{"total_valid_amount": 150.00, "valid_count": 3, "failed_count": 1}`). The hardened verifier blocks this by dynamically generating non-deterministic test batches at evaluation time (using random UUID transaction IDs, random float amounts, and varying status mixtures) across multiple seeds. It compares target execution output against dynamically computed expectations. Any script outputting static values fails invariant checks and is awarded `0.000`.
- **Remaining Reward-Hacking Risk:**  
  A sophisticated agent could inspect the `/tests` folder if permissions permit or monkey-patch the Python runtime / inspection hooks to snoop on the caller's arguments. To completely eliminate this in production, Harbor runs verifiers in isolated read-protected steps, or mounts `/tests` in a separate container context.

---

## 6. AI Tool Workflow
- **AI Tool & Model Used:** Antigravity / Gemini CLI with `Gemini 3.8 Flash (High)`.
- **How I Avoided Prompt Leakage:**  
  `instruction.md` was drafted strictly as a black-box product requirements document detailing input CSV columns, business requirements, and output schema. It deliberately omitted any mention of function names, line numbers, or specific buggy implementations (e.g. no mentions of `sys.argv[2]`, `PENDING` inclusion, or string comparison). This forced the agent to independently inspect `/app/reconcile.py`, diagnose failures, and synthesize fixes.

---

## 7. Deep-Dive RL Defense Questions (Oral Presentation Answers)

### Question 1: Mathematical Advantage Walkthrough
*Walkthrough of Run 1, Trial 1 ($R_1 = 0.50$):*
- **Binary Reward vs. Binary Advantage:**
  $$R_1^{\text{bin}} = 0.0, \quad R_2^{\text{bin}} = 0.0, \quad R_3^{\text{bin}} = 0.0 \implies \bar{R}^{\text{bin}} = 0.0$$
  $$\text{Advantage}_1^{\text{bin}} = 0.0 - 0.0 = \mathbf{0.00}$$
  Under binary grading, Trial 1 receives zero advantage, falling into the **Zero-Signal Trap** where useful code edits receive zero reinforcement.
- **Dense Reward vs. Dense Advantage:**
  $$R_1^{\text{dense}} = 0.50, \quad R_2^{\text{dense}} = 0.20, \quad R_3^{\text{dense}} = 0.00 \implies \bar{R}^{\text{dense}} = \frac{0.50 + 0.20 + 0.00}{3} \approx 0.233$$
  $$\text{Advantage}_1^{\text{dense}} = 0.50 - 0.233 = \mathbf{+0.267}$$
  $$\text{Advantage}_2^{\text{dense}} = 0.20 - 0.233 = \mathbf{-0.033}$$
  $$\text{Advantage}_3^{\text{dense}} = 0.00 - 0.233 = \mathbf{-0.233}$$
- **Reinforced vs. Penalized Actions:**
  In Trial 1, the bash edits `sed -i 's/sys.argv\[2\]/sys.argv\[1\]/'` (fixing Bug 1) and status condition normalization `status == "SUCCESS"` (fixing Bug 2) receive a **positive learning signal (+0.267)**, encouraging policy gradient updates (e.g., GRPO/PPO) to favor these patterns. Meanwhile, Trial 3's destructive argparse rewrite receives a **negative signal (-0.233)**.

### Question 2: Local Optima & Reward Weight Calibration
If an agent is trained for 1,000 steps with weights $(0.20, 0.30, 0.50)$, it could potentially converge to a **local optimum** where it comfortably collects $0.50$ by fixing Bug 1 and Bug 2, but refuses to tackle Bug 3 because risky modifications might crash the script and drop the reward from $0.50$ down to $0.00$.
- **Remediation Strategy:**
  1. **Non-destructive baseline reward / Step-level credit**: Ensure that if Bug 1 & 2 pass, the agent retains its baseline $0.50$ even if Bug 3 logic contains minor errors.
  2. **Non-linear reward shaping**: Adjust the weight distribution to heavily backload the reward for complete end-to-end correctness (e.g. $(0.10, 0.20, 0.70)$ or introducing an exponential bonus for passing all edge-case suites), ensuring the expected value of solving Bug 3 significantly exceeds the safety of stopping early.
  3. **Curriculum learning / Staged prompts**: Gradually introduce complex multi-timezone test suites as training progresses.

### Question 3: Adversarial Gaming in Hardened Verifiers
Even with dynamically generated inputs, an agent could attempt **verifier introspection / process-level hijacking**:
- The agent could inspect `/proc` or `/tmp` to locate the verifier process, read the generated CSV file path directly from the process command-line arguments, read the ground truth or call `datetime.fromisoformat` inside a subshell to compute and mirror the verifier's exact calculations without fixing `/app/reconcile.py`.
- Alternatively, the agent could modify `sys.modules` or monkeypatch Python standard libraries in `/usr/local/lib/python3.12` to intercept verifier execution.
- **Countermeasure**: Verifier execution must occur in a separate, unprivileged, isolated container environment where the agent has no write access to system libraries or inter-process visibility.
