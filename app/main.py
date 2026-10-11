from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query


app = FastAPI(
    title="Batch Operations Mock API",
    description="Local, simulated counterparty credit risk batch status and logs.",
    version="0.1.0",
)

LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"

JOB_NAMES = [
    "Pre Load",
    "Load Market Data",
    "Load Trade Data",
    "Load Counterparty Data",
    "Load Collateral Data",
    "Validate Inputs",
    "Calculate Counterparty Risk",
    "Aggregate Risk Results",
    "Quality Checks",
    "Run Reports",
]

# Source loads run in parallel after Pre Load. Every later step waits for its
# direct prerequisites. IDs are local to a run date, like the sample payload.
DEPENDENCIES = {
    1: [],
    2: [1],
    3: [1],
    4: [1],
    5: [1],
    6: [2, 3, 4, 5],
    7: [6],
    8: [7],
    9: [8],
    10: [9],
}


def make_waiting_on(job_id, status):
    if status in {"Waiting", "Blocked"} and job_id > 1:
        return {
            "type": "tasks",
            "tasks": DEPENDENCIES[job_id],
            "reason": "upstream_task_incomplete",
        }
    return None


def build_daily_batches():
    """Build ten simulated daily runs with useful success and failure cases."""
    today = datetime.now(timezone.utc).date()
    scenarios = [
        ["Completed"] * 10,
        ["Completed", "Completed", "Failed", "Completed", "Completed", "Blocked", "Blocked", "Blocked", "Blocked", "Blocked"],
        ["Completed"] * 10,
        ["Completed", "Completed", "Completed", "Completed", "Completed", "Completed", "Running", "Waiting", "Waiting", "Waiting"],
        ["Completed"] * 10,
        ["Queued"] * 10,
        ["Completed", "Failed", "Completed", "Completed", "Completed", "Blocked", "Blocked", "Blocked", "Blocked", "Blocked"],
        ["Completed"] * 10,
        ["Completed", "Completed", "Completed", "Completed", "Failed", "Blocked", "Blocked", "Blocked", "Blocked", "Blocked"],
        ["Completed"] * 10,
    ]
    batches = {}

    for days_ago, statuses in enumerate(scenarios):
        run_date = today - timedelta(days=days_ago)
        date_text = run_date.isoformat()
        tasks = []
        for job_id, (name, status) in enumerate(zip(JOB_NAMES, statuses), start=1):
            start_time = f"{date_text}T10:00:00Z"
            finished = status in {"Completed", "Failed", "Blocked", "Skipped"}
            end_time = f"{date_text}T10:30:00Z" if finished else None
            tasks.append(
                {
                    "id": job_id,
                    "name": name,
                    "status": status,
                    "start_time": start_time,
                    "end_time": end_time,
                    "last_ran": end_time,
                    "depends_on": DEPENDENCIES[job_id],
                    "waiting_on": make_waiting_on(job_id, status),
                }
            )

        if "Failed" in statuses:
            batch_status = "Failed"
        elif "Running" in statuses:
            batch_status = "Running"
        elif "Waiting" in statuses:
            batch_status = "Waiting"
        elif "Queued" in statuses:
            batch_status = "Queued"
        else:
            batch_status = "Completed"

        batches[date_text] = {
            "id": f"credit-risk-{date_text}",
            "name": "Counterparty Credit Risk Calculation",
            "run_date": date_text,
            "status": batch_status,
            "tasks": tasks,
        }

    return batches


BATCHES = build_daily_batches()


def parse_run_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD format")


def get_batch_for_date(run_date: str):
    parsed_date = parse_run_date(run_date)
    batch = BATCHES.get(parsed_date)
    if batch is None:
        raise HTTPException(status_code=404, detail="No batch data for this date")
    return batch


def get_task_for_date(task_id: int, run_date: str):
    batch = get_batch_for_date(run_date)
    for task in batch["tasks"]:
        if task["id"] == task_id:
            return task
    raise HTTPException(status_code=404, detail="Task not found")


def task_log_path(run_date: str, task_id: int) -> Path:
    return LOG_DIR / run_date / f"{task_id:02d}.log"


LOG_EVENT_DETAILS = {
    1: ("run metadata", "business date and run configuration"),
    2: ("market data", "prices, FX rates, and interest rate curves"),
    3: ("trade data", "trade records and product identifiers"),
    4: ("counterparty data", "counterparty identifiers and credit ratings"),
    5: ("collateral data", "collateral balances and agreement records"),
    6: ("input validation", "file completeness, schemas, and record reconciliation"),
    7: ("risk calculation", "expected exposure, PFE, and CVA measures"),
    8: ("risk aggregation", "trade-level results grouped by counterparty"),
    9: ("quality checks", "totals, missing values, and exposure thresholds"),
    10: ("report output", "counterparty and portfolio risk reports"),
}


def make_task_log(batch, task):
    """Create a detailed, deterministic 100-line simulated task log."""
    date_text = batch["run_date"]
    job_id = task["id"]
    subject, activity = LOG_EVENT_DETAILS[job_id]
    start = datetime.fromisoformat(f"{date_text}T10:00:00+00:00")
    lines = []
    for index in range(1, 101):
        timestamp = (start + timedelta(seconds=index * 18)).strftime("%Y-%m-%dT%H:%M:%SZ")
        counterparty = f"CP-{((index - 1) % 20) + 1:04d}"
        if index == 1:
            message = f"INFO task_started run_id={batch['id']} task_id={job_id} task_name=\"{task['name']}\""
        elif index == 2:
            message = f"INFO business_date={date_text} mode=simulated source=local_fixture"
        elif index == 3:
            dependency_status = "incomplete" if task["status"] in {"Waiting", "Blocked", "Queued"} else "ready"
            message = f"INFO dependencies={task['depends_on']} dependency_status={dependency_status}"
        elif index == 100:
            message = f"INFO task_finished status={task['status']} duration_seconds=1800"
        elif task["status"] in {"Waiting", "Blocked", "Queued"}:
            reason = task["waiting_on"] or {"type": "scheduler", "reason": "run_not_started"}
            if index % 10 == 0:
                message = f"INFO state_checkpoint status={task['status']} blocker={reason}"
            else:
                message = f"INFO scheduler_heartbeat status={task['status']} task_id={job_id} blocker={reason}"
        elif task["status"] == "Failed" and index >= 91:
            if index == 91:
                message = f"ERROR simulated_failure subject=\"{subject}\" code=SOURCE_RECONCILIATION_MISMATCH"
            else:
                message = f"WARN failure_cleanup step={index - 91} temporary_data=retained_for_investigation"
        elif index == 99:
            message = f"INFO summary subject=\"{subject}\" records_processed=12500 warnings=0"
        elif index % 10 == 0:
            message = f"INFO progress={index}% subject=\"{subject}\" records_processed={index * 125}"
        elif index % 7 == 0:
            message = f"INFO database_write table=staging_{job_id} rows={index * 25} commit=simulated"
        elif index % 5 == 0:
            message = f"INFO counterparty={counterparty} {activity} result=accepted"
        else:
            message = f"INFO {activity}; counterparty={counterparty} record={index:05d} source=simulated"
        lines.append(f"{timestamp} {message}")
    return "\n".join(lines) + "\n"


def ensure_task_log(batch, task):
    path = task_log_path(batch["run_date"], task["id"])
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(make_task_log(batch, task), encoding="utf-8")
    return path


@app.get("/health")
def health():
    return {"status": "ok", "mode": "simulated"}


@app.get("/batches")
def list_batches(date: str = Query(..., description="Run date in YYYY-MM-DD format")):
    """Return the ten job records for one day, including dependency details."""
    return get_batch_for_date(date)["tasks"]


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    prefix = "credit-risk-"
    if not batch_id.startswith(prefix):
        raise HTTPException(status_code=404, detail="Batch not found")
    return get_batch_for_date(batch_id.removeprefix(prefix))


@app.get("/tasks/{task_id}")
def get_task(task_id: int, date: str = Query(..., description="Run date in YYYY-MM-DD format")):
    return get_task_for_date(task_id, date)


@app.get("/tasks/{task_id}/logs")
def get_task_logs(
    task_id: int,
    date: str = Query(..., description="Run date in YYYY-MM-DD format"),
    tail_lines: int = Query(default=1000, ge=1, le=5000),
):
    batch = get_batch_for_date(date)
    task = get_task_for_date(task_id, date)
    log_path = ensure_task_log(batch, task)
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return {"date": batch["run_date"], "task_id": task_id, "lines": lines[-tail_lines:]}
