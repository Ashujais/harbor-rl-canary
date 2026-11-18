#!/usr/bin/env python3
"""
Hardened Dense-Reward Verifier for Payment Reconciliation Task
Grades submissions independently across Bug 1, Bug 2, and Bug 3:
- Bug 1 (CLI execution & JSON schema contract): 0.20
- Bug 2 (Status filtering & calculation precision): 0.30
- Bug 3 (Timezone-aware deduplication edge cases): 0.50
Total: 1.00

Anti-Cheat Hardening:
Generates dynamic, non-deterministic transaction batches at evaluation time.
Detects static/canned outputs (like hack.sh) and clamps reward to 0.00.
"""

import csv
from datetime import datetime, timedelta, timezone
import json
import os
import random
import subprocess
import sys
import tempfile
import uuid


def run_target(script_path, csv_path, timeout=10):
    """Executes target reconcile script and returns (success, json_data, error_msg)"""
    try:
        proc = subprocess.run(
            [sys.executable, script_path, csv_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return False, None, f"Exit code {proc.returncode}: {proc.stderr.strip()}"
        
        try:
            data = json.loads(proc.stdout)
            return True, data, ""
        except json.JSONDecodeError as e:
            return False, None, f"Invalid JSON output: {e}\nStdout: {proc.stdout[:200]}"
    except Exception as e:
        return False, None, str(e)


def check_bug1_surface(script_path):
    """
    Check 1: Bug 1 - Surface Bug (Weight: 0.20)
    Tests whether the script accepts sys.argv[1] without crashing or raising IndexError,
    and returns valid JSON containing all expected schema keys.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("tx_id,timestamp,amount,status\n")
        f.write("TX_INIT,2026-01-01T10:00:00Z,50.00,SUCCESS\n")
        temp_csv = f.name

    try:
        ok, data, err = run_target(script_path, temp_csv)
        if not ok or data is None:
            return False, f"Bug 1 Check Failed: {err}"
        
        # Verify schema
        required_keys = {"total_valid_amount", "valid_count", "failed_count"}
        if not required_keys.issubset(data.keys()):
            return False, f"Bug 1 Check Failed: Missing schema keys {required_keys - set(data.keys())}"
        
        return True, "Bug 1 Passed: CLI argument parsing and JSON output schema verified."
    finally:
        if os.path.exists(temp_csv):
            os.remove(temp_csv)


def check_bug2_logic(script_path):
    """
    Check 2: Bug 2 - Logic Bug (Weight: 0.30)
    Tests status filtering and rounding:
    - Only SUCCESS contributes to valid_count and total_valid_amount
    - FAILED contributes to failed_count
    - PENDING must be disregarded (neither valid nor failed)
    - total_valid_amount rounded to 2 decimal places
    """
    # Generate randomized dataset
    rng = random.Random(42)
    rows = []
    expected_valid_count = 0
    expected_failed_count = 0
    expected_total_valid_amount = 0.0

    num_records = rng.randint(12, 20)
    for i in range(num_records):
        tx_id = f"TX_LOGIC_{uuid.uuid4().hex[:8]}"
        status = rng.choice(["SUCCESS", "FAILED", "PENDING"])
        amount = round(rng.uniform(10.05, 99.95), 2)
        ts = f"2026-02-{rng.randint(10, 20):02d}T{rng.randint(10, 22):02d}:00:00Z"
        rows.append((tx_id, ts, amount, status))

        if status == "SUCCESS":
            expected_valid_count += 1
            expected_total_valid_amount += amount
        elif status == "FAILED":
            expected_failed_count += 1

    expected_total_valid_amount = round(expected_total_valid_amount, 2)

    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("tx_id,timestamp,amount,status\n")
        for r in rows:
            f.write(f"{r[0]},{r[1]},{r[2]},{r[3]}\n")
        temp_csv = f.name

    try:
        ok, data, err = run_target(script_path, temp_csv)
        if not ok:
            return False, f"Bug 2 Check Failed: {err}"

        val_cnt = data.get("valid_count")
        fail_cnt = data.get("failed_count")
        tot_amt = data.get("total_valid_amount")

        if val_cnt != expected_valid_count:
            return False, f"Bug 2 Failed: valid_count expected {expected_valid_count}, got {val_cnt} (likely included PENDING)"
        if fail_cnt != expected_failed_count:
            return False, f"Bug 2 Failed: failed_count expected {expected_failed_count}, got {fail_cnt}"
        if abs(tot_amt - expected_total_valid_amount) > 0.01:
            return False, f"Bug 2 Failed: total_valid_amount expected {expected_total_valid_amount}, got {tot_amt}"

        return True, "Bug 2 Passed: Status filtering (SUCCESS/FAILED/PENDING) and monetary aggregation verified."
    finally:
        if os.path.exists(temp_csv):
            os.remove(temp_csv)


def check_bug3_timezone_dedup(script_path):
    """
    Check 3: Bug 3 - Hard Edge Case (Weight: 0.50)
    Tests deduplication where duplicate tx_ids appear with different timezone offsets.
    Crucial test case:
      Record A has a local time with large positive offset:
        '2026-03-01T16:00:00+08:00' -> 08:00:00 UTC (FAILED, amount 10.00)
      Record B has a UTC time:
        '2026-03-01T11:00:00Z'     -> 11:00:00 UTC (SUCCESS, amount 100.00)
    In naive string comparison:
      '2026-03-01T16:00:00+08:00' > '2026-03-01T11:00:00Z' is True!
      Naive code erroneously keeps Record A (FAILED, total_valid_amount = 0.0).
    In true chronological (UTC) order:
      Record B (11:00 UTC) is 3 hours LATER than Record A (08:00 UTC).
      Correct code keeps Record B (SUCCESS, total_valid_amount = 100.0).
    """
    # Construct distinct test cases specifically targeting lexicographical vs UTC order
    cases = [
        # Pair 1: +08:00 vs Z (String says +08:00 is greater, but Z is 3 hours later)
        {
            "tx_id": "TX_TZ_101",
            "earlier_row": ("TX_TZ_101", "2026-03-01T16:00:00+08:00", 25.00, "FAILED"), # UTC: 08:00:00
            "later_row": ("TX_TZ_101", "2026-03-01T11:00:00Z", 120.50, "SUCCESS"),      # UTC: 11:00:00 (Winner)
            "expected_status": "SUCCESS",
            "expected_amount": 120.50
        },
        # Pair 2: Z vs -05:00 (String says Z is greater, but -05:00 is 2 hours later)
        {
            "tx_id": "TX_TZ_102",
            "earlier_row": ("TX_TZ_102", "2026-03-01T18:00:00Z", 50.00, "SUCCESS"),      # UTC: 18:00:00
            "later_row": ("TX_TZ_102", "2026-03-01T15:00:00-05:00", 75.25, "FAILED"),    # UTC: 20:00:00 (Winner)
            "expected_status": "FAILED",
            "expected_amount": 0.0
        },
        # Pair 3: +05:30 vs +01:00 (String says +05:30 is greater, but +01:00 is 1.5 hours later)
        {
            "tx_id": "TX_TZ_103",
            "earlier_row": ("TX_TZ_103", "2026-03-02T14:00:00+05:30", 60.00, "PENDING"), # UTC: 08:30:00
            "later_row": ("TX_TZ_103", "2026-03-02T11:00:00+01:00", 200.00, "SUCCESS"),  # UTC: 10:00:00 (Winner)
            "expected_status": "SUCCESS",
            "expected_amount": 200.00
        }
    ]

    expected_valid_count = 2   # TX_TZ_101 (SUCCESS) and TX_TZ_103 (SUCCESS)
    expected_failed_count = 1  # TX_TZ_102 (FAILED)
    expected_total_valid_amount = 120.50 + 200.00 # 320.50

    # Write cases into CSV with rows mixed
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("tx_id,timestamp,amount,status\n")
        for c in cases:
            # Write both earlier and later in varying order
            f.write(f"{c['earlier_row'][0]},{c['earlier_row'][1]},{c['earlier_row'][2]},{c['earlier_row'][3]}\n")
            f.write(f"{c['later_row'][0]},{c['later_row'][1]},{c['later_row'][2]},{c['later_row'][3]}\n")
        temp_csv = f.name

    try:
        ok, data, err = run_target(script_path, temp_csv)
        if not ok:
            return False, f"Bug 3 Check Failed: {err}"

        val_cnt = data.get("valid_count")
        fail_cnt = data.get("failed_count")
        tot_amt = data.get("total_valid_amount")

        if val_cnt != expected_valid_count or fail_cnt != expected_failed_count or abs(tot_amt - expected_total_valid_amount) > 0.01:
            return False, (
                f"Bug 3 Failed (Timezone deduplication error):\n"
                f"Expected: valid_count={expected_valid_count}, failed_count={expected_failed_count}, total_valid_amount={expected_total_valid_amount}\n"
                f"Got: valid_count={val_cnt}, failed_count={fail_cnt}, total_valid_amount={tot_amt}\n"
                f"(Indicates timestamps were compared lexicographically as strings instead of chronological UTC datetimes)."
            )

        return True, "Bug 3 Passed: Multi-timezone deduplication correctly evaluated chronological order."
    finally:
        if os.path.exists(temp_csv):
            os.remove(temp_csv)


def check_anti_cheat(script_path):
    """
    Anti-Cheat Validation:
    Runs the script on two dynamic, completely random datasets with unpredictable values.
    Verifies that the script computes output dynamically from input and does not return
    static canned outputs (like hack.sh).
    """
    for seed in [1337, 9999]:
        rng = random.Random(seed)
        n = rng.randint(5, 10)
        expected_valid = 0
        expected_amt = 0.0
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write("tx_id,timestamp,amount,status\n")
            for i in range(n):
                tx = f"TX_AC_{seed}_{i}"
                amt = round(rng.uniform(10.0, 50.0), 2)
                f.write(f"{tx},2026-04-01T12:00:00Z,{amt},SUCCESS\n")
                expected_valid += 1
                expected_amt += amt
            temp_csv = f.name

        try:
            ok, data, err = run_target(script_path, temp_csv)
            if not ok or not data:
                return False, f"Anti-Cheat Check Failed to execute on random control data: {err}"
            
            # If the output doesn't match this random control dataset, it's a hardcoded cheat
            if data.get("valid_count") != expected_valid or abs(data.get("total_valid_amount", 0.0) - expected_amt) > 0.01:
                return False, f"Anti-Cheat Check Triggered: Output does not match dynamically generated test input (canned/hardcoded response detected)."
        finally:
            if os.path.exists(temp_csv):
                os.remove(temp_csv)
                
    return True, "Anti-Cheat Passed: Genuine data processing verified across randomized inputs."


def main():
    script_path = sys.argv[1] if len(sys.argv) > 1 else "/app/reconcile.py"
    logs_dir = sys.argv[2] if len(sys.argv) > 2 else "/logs/verifier"
    
    os.makedirs(logs_dir, exist_ok=True)
    reward_file = os.path.join(logs_dir, "reward.txt")

    print(f"=== Starting Verifier Evaluation for {script_path} ===")
    
    # Run Anti-Cheat check first
    ac_passed, ac_msg = check_anti_cheat(script_path)
    if not ac_passed:
        print(f"[REWARD HACK DETECTED] {ac_msg}")
        with open(reward_file, "w") as f:
            f.write("0.000\n")
        print("Final Reward: 0.000")
        return

    # Check 1: Bug 1 (Weight: 0.20)
    b1_passed, b1_msg = check_bug1_surface(script_path)
    print(f"[{'PASS' if b1_passed else 'FAIL'}] Bug 1: {b1_msg}")
    
    reward = 0.00
    if b1_passed:
        reward += 0.20
        
        # Check 2: Bug 2 (Weight: 0.30)
        b2_passed, b2_msg = check_bug2_logic(script_path)
        print(f"[{'PASS' if b2_passed else 'FAIL'}] Bug 2: {b2_msg}")
        if b2_passed:
            reward += 0.30
            
            # Check 3: Bug 3 (Weight: 0.50)
            b3_passed, b3_msg = check_bug3_timezone_dedup(script_path)
            print(f"[{'PASS' if b3_passed else 'FAIL'}] Bug 3: {b3_msg}")
            if b3_passed:
                reward += 0.50
        else:
            print("[SKIP] Bug 3 skipped due to Bug 2 failure.")
    else:
        print("[SKIP] Bug 2 & Bug 3 skipped due to Bug 1 failure.")

    final_reward = round(reward, 3)
    with open(reward_file, "w") as f:
        f.write(f"{final_reward:.3f}\n")

    print(f"=== Verification Complete. Final Reward: {final_reward:.3f} ===")


if __name__ == "__main__":
    main()
