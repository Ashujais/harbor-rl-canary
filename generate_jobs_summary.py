import json
import os
import uuid
from datetime import datetime, timezone, timedelta

def create_job_artifacts(output_root):
    runs = {
        "run1_baseline": [
            {
                "trial_id": "trial-1",
                "binary_score": 0.0,
                "dense_score": 0.50,
                "summary": "Agent fixed Bug 1 (sys.argv index) and Bug 2 (status filtering), but missed Bug 3 (timezone deduplication).",
                "steps": [
                    {
                        "command": "cat /app/reconcile.py",
                        "output": "... (reads reconcile.py code, spots IndexError on sys.argv[2] and PENDING check) ..."
                    },
                    {
                        "command": "python /app/reconcile.py",
                        "output": "Usage: python reconcile.py <csv_file>"
                    },
                    {
                        "command": "sed -i 's/sys.argv\\[2\\]/sys.argv\\[1\\]/g' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "python -c \"import sys; print('Testing Bug 2 fix')\"",
                        "output": "Testing Bug 2 fix"
                    },
                    {
                        "command": "sed -i 's/status in (\"SUCCESS\", \"PENDING\")/status == \"SUCCESS\"/g' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "sed -i 's/round(total_valid_amount, 1)/round(total_valid_amount, 2)/g' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "echo 'tx_id,timestamp,amount,status\\nT1,2026-01-01T10:00:00Z,10.0,SUCCESS' > /tmp/test.csv && python /app/reconcile.py /tmp/test.csv",
                        "output": "{\\n  \"total_valid_amount\": 10.0,\\n  \"valid_count\": 1,\\n  \"failed_count\": 0\\n}"
                    }
                ]
            },
            {
                "trial_id": "trial-2",
                "binary_score": 0.0,
                "dense_score": 0.20,
                "summary": "Agent fixed Bug 1 (CLI index), but botched Bug 2 status filtering (counted PENDING) and missed Bug 3.",
                "steps": [
                    {
                        "command": "python /app/reconcile.py test.csv",
                        "output": "Traceback (most recent call last):\\n  File \"/app/reconcile.py\", line 56, in main\\n    csv_path = sys.argv[2]\\nIndexError: list index out of range"
                    },
                    {
                        "command": "sed -i 's/csv_path = sys.argv\\[2\\]/csv_path = sys.argv\\[1\\]/' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "grep -n 'status' /app/reconcile.py",
                        "output": "18:            status = row[\"status\"].strip().upper()\n35:    for tx in records.values():\n36:        status = tx[\"status\"]\n39:        if status in (\"SUCCESS\", \"PENDING\"):"
                    },
                    {
                        "command": "sed -i 's/\"PENDING\"/\"PROCESSING\"/' /app/reconcile.py",
                        "output": ""
                    }
                ]
            },
            {
                "trial_id": "trial-3",
                "binary_score": 0.0,
                "dense_score": 0.00,
                "summary": "Agent attempted to rewrite reconcile.py with argparse, introduced syntax error, failed Bug 1.",
                "steps": [
                    {
                        "command": "cat /app/reconcile.py",
                        "output": "... (prints buggy script) ..."
                    },
                    {
                        "command": "python -m py_compile /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "cat << 'EOF' > /app/reconcile.py\nimport argparse, csv, json\n# Broken argparse snippet with unclosed parenthesis\nparser = argparse.ArgumentParser(\nEOF",
                        "output": ""
                    },
                    {
                        "command": "python /app/reconcile.py input.csv",
                        "output": "  File \"/app/reconcile.py\", line 4\n    parser = argparse.ArgumentParser(\n                                     ^\nSyntaxError: unexpected EOF while parsing"
                    }
                ]
            }
        ],
        "run2_ablation": [
            {
                "trial_id": "trial-1",
                "binary_score": 1.0,
                "dense_score": 1.00,
                "summary": "Ablation run: Agent leveraged /app/sample_transactions.csv, detected timezone comparison flaw, and fixed all 3 bugs.",
                "steps": [
                    {
                        "command": "ls -l /app",
                        "output": "-rw-r--r-- 1 root root 1940 Nov 15 16:45 reconcile.py\n-rw-r--r-- 1 root root  420 Nov 15 16:45 sample_transactions.csv"
                    },
                    {
                        "command": "cat /app/sample_transactions.csv",
                        "output": "tx_id,timestamp,amount,status\nTX101,2026-03-01T16:00:00+08:00,10.00,FAILED\nTX101,2026-03-01T11:00:00Z,100.00,SUCCESS"
                    },
                    {
                        "command": "python /app/reconcile.py /app/sample_transactions.csv",
                        "output": "Traceback (most recent call last):\n  File \"/app/reconcile.py\", line 56, in main\n    csv_path = sys.argv[2]\nIndexError: list index out of range"
                    },
                    {
                        "command": "sed -i 's/sys.argv\\[2\\]/sys.argv\\[1\\]/' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "python /app/reconcile.py /app/sample_transactions.csv",
                        "output": "{\n  \"total_valid_amount\": 0.0,\n  \"valid_count\": 0,\n  \"failed_count\": 1\n}\n# Note: Agent observes FAILED was selected because '16:00:00+08:00' > '11:00:00Z' stringwise, but 11:00 UTC is later!"
                    },
                    {
                        "command": "python -c \"from datetime import datetime, timezone; print(datetime.fromisoformat('2026-03-01T16:00:00+08:00').astimezone(timezone.utc))\"",
                        "output": "2026-03-01 08:00:00+00:00"
                    },
                    {
                        "command": "cat << 'EOF' > /app/reconcile.py\nimport csv\nfrom datetime import datetime, timezone\nimport json, sys\n\ndef parse_iso_timestamp(ts):\n    dt = datetime.fromisoformat(ts)\n    if dt.tzinfo is None:\n        dt = dt.replace(tzinfo=timezone.utc)\n    return dt.astimezone(timezone.utc)\n\ndef parse_transactions(csv_file):\n    records = {}\n    with open(csv_file, mode='r', encoding='utf-8') as f:\n        for row in csv.DictReader(f):\n            tx_id = row['tx_id'].strip()\n            dt = parse_iso_timestamp(row['timestamp'].strip())\n            amt = float(row['amount'].strip())\n            st = row['status'].strip().upper()\n            if tx_id not in records or dt > records[tx_id]['dt']:\n                records[tx_id] = {'dt': dt, 'amount': amt, 'status': st}\n    v_cnt = sum(1 for r in records.values() if r['status'] == 'SUCCESS')\n    f_cnt = sum(1 for r in records.values() if r['status'] == 'FAILED')\n    tot = sum(r['amount'] for r in records.values() if r['status'] == 'SUCCESS')\n    return {'total_valid_amount': round(tot, 2), 'valid_count': v_cnt, 'failed_count': f_cnt}\n\nif __name__ == '__main__':\n    if len(sys.argv) < 2: sys.exit(1)\n    print(json.dumps(parse_transactions(sys.argv[1]), indent=2))\nEOF",
                        "output": ""
                    },
                    {
                        "command": "python /app/reconcile.py /app/sample_transactions.csv",
                        "output": "{\n  \"total_valid_amount\": 100.0,\n  \"valid_count\": 1,\n  \"failed_count\": 0\n}"
                    }
                ]
            },
            {
                "trial_id": "trial-2",
                "binary_score": 1.0,
                "dense_score": 1.00,
                "summary": "Ablation run: Agent utilized sample input, fixed CLI index, excluded PENDING, implemented timezone UTC normalization.",
                "steps": [
                    {
                        "command": "cat /app/sample_transactions.csv",
                        "output": "tx_id,timestamp,amount,status\n..."
                    },
                    {
                        "command": "python /app/reconcile.py /app/sample_transactions.csv",
                        "output": "IndexError: list index out of range"
                    },
                    {
                        "command": "sed -i 's/sys.argv\\[2\\]/sys.argv\\[1\\]/g' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "python -c \"import datetime; print('datetime available')\"",
                        "output": "datetime available"
                    },
                    {
                        "command": "python /app/reconcile.py /app/sample_transactions.csv",
                        "output": "{\n  \"total_valid_amount\": 100.0,\n  \"valid_count\": 1,\n  \"failed_count\": 0\n}"
                    }
                ]
            },
            {
                "trial_id": "trial-3",
                "binary_score": 0.0,
                "dense_score": 0.50,
                "summary": "Ablation run: Agent fixed Bug 1 and Bug 2, attempted custom regex parser for timezones but failed negative timezone offsets.",
                "steps": [
                    {
                        "command": "sed -i 's/sys.argv\\[2\\]/sys.argv\\[1\\]/' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "sed -i 's/status in (\"SUCCESS\", \"PENDING\")/status == \"SUCCESS\"/' /app/reconcile.py",
                        "output": ""
                    },
                    {
                        "command": "python /app/reconcile.py /app/sample_transactions.csv",
                        "output": "Partial match"
                    }
                ]
            }
        ]
    }

    base_time = datetime(2026, 11, 15, 14, 0, 0, tzinfo=timezone.utc)

    for run_key, trials in runs.items():
        for t in trials:
            trial_dir = os.path.join(output_root, run_key, f"reconcile-bug__{t['trial_id']}")
            agent_dir = os.path.join(trial_dir, "agent")
            verifier_dir = os.path.join(trial_dir, "verifier")
            os.makedirs(agent_dir, exist_ok=True)
            os.makedirs(verifier_dir, exist_ok=True)

            # 1. Write reward.txt
            with open(os.path.join(verifier_dir, "reward.txt"), "w") as f:
                f.write(f"{t['dense_score']:.3f}\n")

            # 2. Write verifier.log
            with open(os.path.join(verifier_dir, "verifier.log"), "w") as f:
                f.write(f"=== Verifier Log for {run_key}/{t['trial_id']} ===\n")
                f.write(f"Anti-Cheat Check: PASSED\n")
                f.write(f"Bug 1 (Surface): {'PASSED (+0.20)' if t['dense_score'] >= 0.20 else 'FAILED (+0.00)'}\n")
                f.write(f"Bug 2 (Logic): {'PASSED (+0.30)' if t['dense_score'] >= 0.50 else 'FAILED (+0.00)'}\n")
                f.write(f"Bug 3 (Timezone Edge Case): {'PASSED (+0.50)' if t['dense_score'] >= 1.00 else 'FAILED (+0.00)'}\n")
                f.write(f"Binary Score: {t['binary_score']:.1f}\n")
                f.write(f"Dense Reward: {t['dense_score']:.3f}\n")

            # 3. Write result.json
            result_data = {
                "schema_version": 1,
                "id": str(uuid.uuid4()),
                "task_name": "reconcile-bug",
                "trial_name": f"reconcile-bug__{t['trial_id']}",
                "trial_uri": f"file:///{trial_dir.replace('\\', '/')}",
                "task_id": "local://tasks/reconcile-bug",
                "task_checksum": "a8f3b49c2d1e05f6",
                "config": {
                    "agent": "terminus-2",
                    "model": "gemini/gemini-2.5-flash",
                    "ablation": run_key == "run2_ablation"
                },
                "agent_info": {
                    "name": "terminus-2",
                    "model": "gemini/gemini-2.5-flash",
                    "version": "0.26.0"
                },
                "verifier_result": {
                    "rewards": {
                        "reward": t["dense_score"],
                        "binary_reward": t["binary_score"]
                    },
                    "summary": t["summary"]
                },
                "started_at": base_time.isoformat(),
                "finished_at": (base_time + timedelta(seconds=145)).isoformat()
            }
            with open(os.path.join(trial_dir, "result.json"), "w") as f:
                json.dump(result_data, f, indent=2)

            # 4. Write trajectory.json (ATIF-v1.7 format)
            traj_steps = [
                {
                    "step_id": 1,
                    "timestamp": base_time.isoformat(),
                    "source": "user",
                    "message": "Fix the broken payment reconciliation CLI at /app/reconcile.py. Refer to instruction.md for rules.",
                    "extra": {"is_sidechain": False}
                }
            ]

            step_idx = 2
            for s in t["steps"]:
                traj_steps.append({
                    "step_id": step_idx,
                    "timestamp": (base_time + timedelta(seconds=step_idx * 15)).isoformat(),
                    "source": "agent",
                    "model_name": "gemini-2.5-flash",
                    "message": f"Executing: {s['command']}",
                    "tool_calls": [
                        {
                            "tool_call_id": f"call_{uuid.uuid4().hex[:12]}",
                            "function_name": "bash",
                            "arguments": {"command": s["command"]}
                        }
                    ],
                    "observation": {
                        "results": [
                            {
                                "content": s["output"]
                            }
                        ]
                    },
                    "metrics": {
                        "prompt_tokens": 1240 + step_idx * 120,
                        "completion_tokens": 85 + step_idx * 15
                    }
                })
                step_idx += 1

            trajectory_data = {
                "schema_version": "ATIF-v1.7",
                "session_id": str(uuid.uuid4()),
                "agent": {
                    "name": "terminus-2",
                    "version": "0.26.0",
                    "model_name": "gemini/gemini-2.5-flash"
                },
                "steps": traj_steps
            }
            with open(os.path.join(agent_dir, "trajectory.json"), "w") as f:
                json.dump(trajectory_data, f, indent=2)

            base_time += timedelta(minutes=15)

    print("All jobs_summary artifacts created successfully.")

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "jobs_summary"
    create_job_artifacts(out)
