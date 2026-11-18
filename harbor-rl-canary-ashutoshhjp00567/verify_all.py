#!/usr/bin/env python3
"""
Test Harness for Reconcile Task Calibration & Verification
Executes local validation of:
1. 'nop' (original environment/reconcile.py) -> MUST score 0.000
2. 'hack.sh' (adversarial canned response) -> MUST score 0.000
3. 'partial' (fixes Bug 1 & Bug 2, leaves Bug 3 broken) -> MUST score 0.500
4. 'solve.sh' (full reference solution) -> MUST score 1.000
"""

import os
import shutil
import subprocess
import sys
import tempfile


def run_verifier_on_script(candidate_script):
    with tempfile.TemporaryDirectory() as tmp_logs:
        verifier_script = os.path.join(
            os.path.dirname(__file__), "tasks", "reconcile-bug", "tests", "test_verifier.py"
        )
        proc = subprocess.run(
            [sys.executable, verifier_script, candidate_script, tmp_logs],
            capture_output=True,
            text=True,
        )
        reward_file = os.path.join(tmp_logs, "reward.txt")
        if os.path.exists(reward_file):
            with open(reward_file, "r") as f:
                reward = float(f.read().strip())
        else:
            reward = 0.0
        return reward, proc.stdout, proc.stderr


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    reconcile_bug_dir = os.path.join(base_dir, "tasks", "reconcile-bug")

    # 1. Test NOP (Original Buggy Environment)
    nop_script = os.path.join(reconcile_bug_dir, "environment", "reconcile.py")
    nop_reward, nop_out, _ = run_verifier_on_script(nop_script)
    print(f"[TEST 1: NOP] Score: {nop_reward:.3f} | Expected: 0.000")
    assert nop_reward == 0.0, f"NOP failed, got {nop_reward}"

    # 2. Test HACK (Reward Hacking Stub)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write('''#!/usr/bin/env python3
import json
import sys
# Hardcoded response attempting to fool static checks
print(json.dumps({"total_valid_amount": 150.00, "valid_count": 3, "failed_count": 1}, indent=2))
''')
        hack_script = f.name

    try:
        hack_reward, hack_out, _ = run_verifier_on_script(hack_script)
        print(f"[TEST 2: HACK] Score: {hack_reward:.3f} | Expected: 0.000")
        assert hack_reward == 0.0, f"HACK failed, got {hack_reward}"
    finally:
        if os.path.exists(hack_script):
            os.remove(hack_script)

    # 3. Test PARTIAL FIX (Bug 1 & Bug 2 fixed, Bug 3 broken)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write('''#!/usr/bin/env python3
import csv
import json
import sys

def parse_transactions(csv_file):
    records = {}
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"].strip()
            timestamp = row["timestamp"].strip()
            amount = float(row["amount"].strip())
            status = row["status"].strip().upper()

            # Bug 3 is left broken (naive string comparison)
            if tx_id in records:
                if timestamp > records[tx_id]["timestamp"]:
                    records[tx_id] = {"timestamp": timestamp, "amount": amount, "status": status}
            else:
                records[tx_id] = {"timestamp": timestamp, "amount": amount, "status": status}

    valid_count = 0
    failed_count = 0
    total_valid_amount = 0.0

    for tx in records.values():
        status = tx["status"]
        amount = tx["amount"]

        # Bug 2 is FIXED: only SUCCESS is valid, FAILED is counted, PENDING is ignored
        if status == "SUCCESS":
            valid_count += 1
            total_valid_amount += amount
        elif status == "FAILED":
            failed_count += 1

    return {
        "total_valid_amount": round(total_valid_amount, 2),
        "valid_count": valid_count,
        "failed_count": failed_count,
    }

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    # Bug 1 is FIXED: reading sys.argv[1]
    csv_path = sys.argv[1]
    summary = parse_transactions(csv_path)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
''')
        partial_script = f.name

    try:
        partial_reward, partial_out, _ = run_verifier_on_script(partial_script)
        print(f"[TEST 3: PARTIAL] Score: {partial_reward:.3f} | Expected: 0.500")
        assert partial_reward == 0.5, f"PARTIAL failed, got {partial_reward}"
    finally:
        if os.path.exists(partial_script):
            os.remove(partial_script)

    # 4. Test SOLVE (Reference Solution)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write('''#!/usr/bin/env python3
import csv
from datetime import datetime, timezone
import json
import sys

def parse_iso_timestamp(ts_str):
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def parse_transactions(csv_file):
    records = {}
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = row["tx_id"].strip()
            ts_str = row["timestamp"].strip()
            amount = float(row["amount"].strip())
            status = row["status"].strip().upper()

            dt_utc = parse_iso_timestamp(ts_str)

            if tx_id in records:
                if dt_utc > records[tx_id]["dt_utc"]:
                    records[tx_id] = {"dt_utc": dt_utc, "amount": amount, "status": status}
            else:
                records[tx_id] = {"dt_utc": dt_utc, "amount": amount, "status": status}

    valid_count = 0
    failed_count = 0
    total_valid_amount = 0.0

    for tx in records.values():
        status = tx["status"]
        amount = tx["amount"]

        if status == "SUCCESS":
            valid_count += 1
            total_valid_amount += amount
        elif status == "FAILED":
            failed_count += 1

    return {
        "total_valid_amount": round(total_valid_amount, 2),
        "valid_count": valid_count,
        "failed_count": failed_count,
    }

def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    csv_path = sys.argv[1]
    summary = parse_transactions(csv_path)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
''')
        solve_script = f.name

    try:
        solve_reward, solve_out, _ = run_verifier_on_script(solve_script)
        print(f"[TEST 4: SOLVE] Score: {solve_reward:.3f} | Expected: 1.000")
        assert solve_reward == 1.0, f"SOLVE failed, got {solve_reward}"
    finally:
        if os.path.exists(solve_script):
            os.remove(solve_script)

    print("\nALL 4 CALIBRATION TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    main()
