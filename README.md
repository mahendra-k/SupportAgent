# Batch Operations Intelligence Agent

A learning project that simulates a counterparty credit risk batch system and uses a Gemini model to answer operator questions about daily task status and logs.

All batch data, task logs, and operations are simulated locally. The agent currently has read-only tools; it cannot restart services, rerun batches, or change data.

## Requirements

- Python 3.10 or later
- A Gemini API key for the agent (the local mock API does not need a key)

## Setup (Windows PowerShell)

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set the Gemini API key in the current PowerShell session before starting the agent:

```powershell
$env:GEMINI_API_KEY = "your-gemini-api-key"
```

Optionally choose a model or log verbosity. The default model is `gemini-3.8-flash`; logging defaults to `INFO`.

```powershell
$env:GEMINI_MODEL = "gemini-3.8-flash"
$env:LOG_LEVEL = "INFO"
```

## Run the local mock API

In the first terminal, with the virtual environment active:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

## Run the agent

In a second terminal, activate the virtual environment, set `GEMINI_API_KEY`, then run:

```powershell
python -m app.agent
```

Type a question at the `you>` prompt. Type `exit` to quit. For more detail in the timing, token usage, and Gemini response logs, set `$env:LOG_LEVEL = "DEBUG"` before launching.

## Mock API endpoints

The API simulates the most recent ten UTC run dates. Each date has ten dependent or parallel tasks and simulated statuses.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Check that the mock API is running |
| `GET /batches?date=YYYY-MM-DD` | Get the ten task records for a run date |
| `GET /batches/{batch_id}` | Get a batch and its tasks by ID, such as `credit-risk-2026-10-11` |
| `GET /tasks/{task_id}?date=YYYY-MM-DD` | Get one task and its dependency information |
| `GET /tasks/{task_id}/logs?date=YYYY-MM-DD&tail_lines=100` | Get the requested number of recent simulated log lines |

Task logs are generated locally when first requested and stored under `data/logs/`. They are runtime data and are excluded from Git.

## Agent tools and safety

The Gemini agent can call two explicitly defined tools:

- `get_daily_batch`: read task statuses and dependencies for one date.
- `get_task_logs`: read log lines for a task on one date.

The application validates tool names and arguments before making local API requests. The configured API URL is restricted to `localhost` or `127.0.0.1`. No production services or Azure resources are contacted. Prompts and returned simulated data are sent to the Gemini API for model responses.
