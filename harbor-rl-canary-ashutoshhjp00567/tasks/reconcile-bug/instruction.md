# Payment Reconciliation Task

You are tasked with fixing and verifying the payment reconciliation CLI tool located at `/app/reconcile.py`.

The script is responsible for processing a CSV file containing payment transactions and printing a JSON summary to stdout.

### CLI Usage
The script should be executable from the command line:
```bash
python /app/reconcile.py <path_to_csv>
```

### Input Format
The input is a standard CSV file with a header row followed by transaction records:
`tx_id,timestamp,amount,status`

- `tx_id` (string): Unique identifier for a transaction. Note: Multiple entries with the same `tx_id` may appear in the CSV (e.g. status updates or retries).
- `timestamp` (string): ISO-8601 formatted datetime string representing when the record occurred. Timestamps may include UTC indicators (`Z`) or explicit UTC offsets (e.g. `+05:30`, `-04:00`).
- `amount` (float): The transaction monetary value.
- `status` (string): Transaction status, which can be `SUCCESS`, `FAILED`, or `PENDING`.

### Business & Reconciliation Rules
1. **Deduplication**: If multiple records with the same `tx_id` exist, only the record with the latest timestamp in chronological (UTC) order must be retained. Older records for that `tx_id` must be disregarded.
2. **Status Accounting**:
   - Only records with status `SUCCESS` are counted as valid (`valid_count`).
   - Only records with status `FAILED` are counted as failed (`failed_count`).
   - Records with status `PENDING` (or unconfirmed statuses) are neither valid nor failed, and should not be counted in `valid_count` or `failed_count`.
3. **Monetary Sum**: `total_valid_amount` is the sum of amounts of all valid (`SUCCESS`) records, rounded to 2 decimal places.

### Output Format
The script must print a valid JSON object to standard output (`stdout`) matching the following schema:
```json
{
  "total_valid_amount": 1250.75,
  "valid_count": 8,
  "failed_count": 2
}
```

Ensure that `/app/reconcile.py` handles input correctly, adheres to all business specifications, and executes cleanly without uncaught exceptions.
