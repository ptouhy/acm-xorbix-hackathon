"""
Web UI backend — runs the agent on a Databricks SQL warehouse and serves the single-page UI.

Run locally (from the repo root, with your Databricks CLI logged in):
    PYTHONPATH=src .venv/bin/uvicorn app.server:app --port 8000

The agent code is the same as in the bundle job; only the session differs (WarehouseSession instead of Spark).
Progress is polled (not streamed) so proxies can't break it. Runs are kept in memory (single instance).
"""

from __future__ import annotations

import dataclasses
import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent.agentic import AgenticBriefingAgent
from agent.measure import measure_outcomes
from agent.settings import load_settings
from agent.tools import QUEUE_TABLE
from agent.tracking import LEDGER_TABLE, log_run, record_recommendations
from agent.warehouse import WarehouseSession

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Revenue Briefing Agent")

_settings = load_settings()
_CATALOG, _SCHEMA = _settings["catalog"], _settings["schema"]
_session: WarehouseSession | None = None
_session_lock = threading.Lock()
RUNS: dict[str, dict] = {}


def session() -> WarehouseSession:
    global _session
    with _session_lock:
        if _session is None:
            _session = WarehouseSession()
        return _session


def _plain(obj: Any) -> Any:
    """Make agent output JSON-safe (dates, Decimals, dataclasses)."""
    if dataclasses.is_dataclass(obj):
        obj = dataclasses.asdict(obj)
    return json.loads(json.dumps(obj, default=str))


class Ask(BaseModel):
    question: str


class Approve(BaseModel):
    batch_id: str


def _work(run_id: str, question: str) -> None:
    run = RUNS[run_id]
    try:
        agent = AgenticBriefingAgent(session(), _CATALOG, _SCHEMA)
        for event in agent.run_stream(question):
            payload = event.to_dict()
            if event.type in ("final", "fallback"):
                result = event.data["result"]
                run["result"] = _plain(result)
                run["fell_back"] = event.type == "fallback"
                payload = {"type": event.type, **({"reason": event.data["reason"]} if "reason" in event.data else {})}
                if result.mode == "agentic":
                    try:  # Measure: remember who the agent told staff to contact (+ holdout)
                        record_recommendations(session(), _CATALOG, _SCHEMA, uuid.uuid4().hex, question, result)
                    except Exception as exc:
                        run["ledger_error"] = str(exc)
            run["events"].append(_plain(payload))
    except Exception as exc:
        run["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        run["done"] = True


@app.post("/api/ask")
def ask(body: Ask) -> dict:
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Question is empty")
    run_id = uuid.uuid4().hex[:10]
    RUNS[run_id] = {"events": [], "done": False, "result": None, "error": None}
    threading.Thread(target=_work, args=(run_id, question[:500]), daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, since: int = 0) -> dict:
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Unknown run")
    return {"events": run["events"][since:], "next": len(run["events"]), "done": run["done"],
            "error": run["error"], "result": run["result"] if run["done"] else None}


def _queue_table() -> str:
    return f"{_CATALOG}.{_SCHEMA}.{QUEUE_TABLE}"


@app.get("/api/queue")
def queue() -> dict:
    s = session()
    if not s.catalog.tableExists(_queue_table()):
        return {"batches": []}
    rows = s.sql(f"""
        SELECT batch_id, segment, status, COUNT(*) AS people, MIN(queued_at) AS first_queued,
               MAX(message_template) AS message
        FROM {_queue_table()} GROUP BY batch_id, segment, status
        ORDER BY first_queued DESC LIMIT 25
    """).collect()
    return {"batches": [_plain(vars(r)) for r in rows]}


@app.post("/api/queue/approve")
def approve(body: Approve) -> dict:
    if not re.fullmatch(r"[0-9a-f]{12}", body.batch_id):
        raise HTTPException(400, "Bad batch id")
    session().sql(f"UPDATE {_queue_table()} SET status = 'approved' "
                  f"WHERE batch_id = '{body.batch_id}' AND status = 'pending_approval'")
    return {"ok": True}


@app.get("/api/measure")
def measure() -> dict:
    s = session()
    if not s.catalog.tableExists(f"{_CATALOG}.{_SCHEMA}.{LEDGER_TABLE}"):
        return {"results": []}
    return {"results": _plain(measure_outcomes(s, _CATALOG, _SCHEMA))}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "catalog": _CATALOG, "schema": _SCHEMA, "model": _settings["agent"]["llm_endpoint"]}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")
