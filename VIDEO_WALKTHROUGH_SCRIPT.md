# 5-Minute Loom Walkthrough Script & Recording Guide

Use this exact script and timing guide to record your 5-minute unedited Loom video.  
*Tip: Keep your terminal and editor (VS Code) open side-by-side.*

---

## ⏱️ PART 1: Live Reward Mutation & Anti-Hack Proof (0:00 – 1:45)

### Screen to Show:
Terminal and editor with `tasks/reconcile-bug/solution/solve.sh` and `verify_all.py`.

### What to Say & Do:
1. **[0:00 - 0:25] Introduction & Baseline Oracle Verification:**
   - **Say:** *"Hello! In this walkthrough, I will demonstrate the Harbor RL environment calibration, dense reward function, anti-cheat verifier, and trajectory forensics for the payment reconciliation task."*
   - **Action:** Run the calibration test:
     ```bash
     python verify_all.py
     ```
   - **Point to terminal:** Show that `solve.sh` scores **`1.000`** and `nop` scores **`0.000`**.

2. **[0:25 - 1:05] Live Partial-Credit Canary (Demonstrating the 0.500 Score):**
   - **Say:** *"Now, let's demonstrate live reward mutation. Our verifier awards 0.20 for Bug 1 (CLI execution) and 0.30 for Bug 2 (status filtering and rounding), totaling 0.50, and 0.50 for Bug 3 (multi-timezone deduplication). I will now break Bug 3 by replacing UTC datetime comparison with naive string comparison. Because Bug 1 and Bug 2 remain resolved, this mutated script should score exactly 0.500."*
   - **Action:** Show the partial fix output in terminal:
     ```text
     [TEST 3: PARTIAL] Score: 0.500 | Expected: 0.500
     ```
   - **Say:** *"As predicted, the verifier grades Bug 1 and Bug 2 as passed (+0.500) and detects that naive string comparison fails on timezone offsets like +08:00 vs UTC, awarding exactly 0.500."*

3. **[1:05 - 1:45] Anti-Cheat Proof (`hack.sh`):**
   - **Say:** *"Next, let's examine reward hacking. In `tasks/reconcile-bug/solution/hack.sh`, an adversarial agent attempts to game the verifier by returning a static canned JSON object matching naive test values without doing any real CSV processing."*
   - **Action:** Show `tasks/reconcile-bug/solution/hack.sh` on screen.
   - **Say:** *"Our hardened verifier dynamically generates randomized batches with random UUIDs and floats at runtime. When `hack.sh` is evaluated:"*
   - **Point to terminal:** Show `[TEST 2: HACK] Score: 0.000 | Expected: 0.000`.
   - **Say:** *"The verifier catches the canned output immediately and clamps the reward to 0.000!"*

---

## ⏱️ PART 2: Side-by-Side Trajectory Forensics (1:45 – 3:15)

### Screen to Show:
Open `jobs_summary/run1_baseline/reconcile-bug__trial-1/agent/trajectory.json` alongside `jobs_summary/run2_ablation/reconcile-bug__trial-1/agent/trajectory.json`.

### What to Say & Do:
1. **[1:45 - 2:30] Inspecting Baseline Failure in Run 1:**
   - **Say:** *"In Run 1 Baseline, the agent had to discover and fix bugs without an in-container sample dataset. In Trial 1, step 7, the agent fixed the CLI index (Bug 1) and fixed the PENDING filter (Bug 2). Then, look at this bash command: `echo 'tx_id,timestamp,amount,status\nT1,2026-01-01T10:00:00Z,10.0,SUCCESS' > /tmp/test.csv`. The agent tested its fix against only a single UTC row! Because there were no duplicate transaction IDs or varying timezone offsets in its synthetic test, the script passed, the agent thought it was done, and it terminated early, missing Bug 3 completely."*

2. **[2:30 - 3:15] Showing the Ablation Change & Result in Run 2:**
   - **Say:** *"For Run 2, we conducted a controlled ablation: we added `/app/sample_transactions.csv` containing multi-timezone duplicate transactions (`2026-03-01T16:00:00+08:00` vs `2026-03-01T11:00:00Z`). In Run 2 Trial 1, step 5, the agent ran `reconcile.py` against this sample file and noticed that the FAILED transaction was chosen because string comparison thought 16:00 was later than 11:00 UTC! Seeing this failure live prompted the agent to implement `datetime.fromisoformat(...).astimezone(timezone.utc)`, lifting the score to a full 1.000!"*

---

## ⏱️ PART 3: Defending RL Math & Reward Design (3:15 – 5:00)

### Screen to Show:
`README.md` (Table in Section 3 and Answers in Section 7).

### What to Say & Do:
1. **[3:15 - 3:55] Question 1: Mathematical Advantage Walkthrough:**
   - **Point to Table in Section 3:**
   - **Say:** *"In Run 1 Baseline, under binary grading, all three trials scored 0.0. The group mean was 0.0, meaning every trial received 0.0 - 0.0 = 0.00 Advantage. This is the Zero-Signal Trap: the agent learned nothing from trial 1 despite fixing 2 out of 3 bugs! With our dense verifier, Trial 1 scored 0.50, Trial 2 scored 0.20, and Trial 3 scored 0.00, giving a mean of 0.233. Now Trial 1 gets a positive advantage of +0.267, strongly reinforcing the edits that fixed Bug 1 and Bug 2, while Trial 3 gets a negative advantage of -0.233, penalizing syntax-breaking errors."*

2. **[3:55 - 4:30] Question 2: Local Optima & Weight Calibration:**
   - **Say:** *"If an agent trains for 1,000 steps with weights 0.20, 0.30, and 0.50, could it get stuck in a local optimum? Yes! An agent might decide that fixing Bug 1 and Bug 2 guarantees 0.50, whereas modifying Bug 3 risks breaking the entire script and dropping to 0.00. To prevent this local optimum, we backload the reward—for example, (0.10, 0.20, 0.70)—so the expected payoff of solving Bug 3 heavily outweighs the risk of stopping at Bug 2."*

3. **[4:30 - 5:00] Question 3: Future Reward Hacking & Conclusion:**
   - **Say:** *"Finally, even with randomized data, a clever agent could attempt verifier introspection—inspecting `/proc` or `/tmp` to read the verifier's dynamically generated files or monkeypatching Python's standard library. In production, verifiers must run in an isolated, read-protected sandbox. That concludes the walkthrough. Thank you!"*
