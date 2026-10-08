"""
Spark-compatible session backed by a Databricks SQL warehouse.

STEP EXPLANATION:
  Notebooks hand the agent a SparkSession. A web app has none, so this adapter offers the three
  Spark calls our code uses (sql().collect(), createDataFrame().write...saveAsTable(), catalog.tableExists())
  and runs them on a SQL warehouse through the Databricks SDK. The agent and its tools are unchanged.
  Auth comes from the environment / CLI profile; no workspace values live in the repo.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

_INTS = {"BYTE", "SHORT", "INT", "LONG"}
_FLOATS = {"FLOAT", "DOUBLE", "DECIMAL"}


def _convert(value: Any, type_name: str) -> Any:
    if value is None:
        return None
    if type_name in _INTS:
        return int(value)
    if type_name in _FLOATS:
        return float(Decimal(value))
    if type_name == "BOOLEAN":
        return str(value).lower() == "true"
    if type_name == "DATE":
        return date.fromisoformat(value)
    if type_name.startswith("TIMESTAMP"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _literal(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, datetime):
        return f"TIMESTAMP '{v.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(v, date):
        return f"DATE '{v.isoformat()}'"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


class _Result:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def collect(self) -> list[SimpleNamespace]:
        return self._rows


class _Writer:
    def __init__(self, session: "WarehouseSession", rows: list[tuple], ddl: str) -> None:
        self._s, self._rows, self._ddl = session, rows, ddl

    def format(self, _fmt: str) -> "_Writer":
        return self

    def mode(self, _mode: str) -> "_Writer":
        return self  # we only ever append

    def saveAsTable(self, table: str) -> None:
        self._s.sql(f"CREATE TABLE IF NOT EXISTS {table} ({self._ddl}) USING DELTA")
        if self._rows:
            values = ", ".join("(" + ", ".join(_literal(v) for v in r) + ")" for r in self._rows)
            self._s.sql(f"INSERT INTO {table} VALUES {values}")


class _DataFrame:
    def __init__(self, session: "WarehouseSession", rows: list[tuple], ddl: str) -> None:
        self.write = _Writer(session, rows, ddl)


class _Catalog:
    def __init__(self, session: "WarehouseSession") -> None:
        self._s = session

    def tableExists(self, name: str) -> bool:
        try:
            self._s.sql(f"DESCRIBE TABLE {name}")
            return True
        except RuntimeError:
            return False


class WarehouseSession:
    def __init__(self, warehouse_id: str | None = None, client: Any | None = None, timeout_s: int = 300) -> None:
        if client is None:
            from databricks.sdk import WorkspaceClient  # lazy: only the web app needs it

            client = WorkspaceClient()
        self._w = client
        self._timeout = timeout_s
        self.warehouse_id = warehouse_id or os.environ.get("DATABRICKS_WAREHOUSE_ID") or self._discover()
        self.catalog = _Catalog(self)

    def _discover(self) -> str:
        warehouses = list(self._w.warehouses.list())
        if not warehouses:
            raise RuntimeError("No SQL warehouse found. Set DATABRICKS_WAREHOUSE_ID.")
        return warehouses[0].id

    def sql(self, statement: str) -> _Result:
        from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout, StatementState

        resp = self._w.statement_execution.execute_statement(
            statement=statement, warehouse_id=self.warehouse_id, wait_timeout="30s",
            on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
        )
        deadline = time.time() + self._timeout
        while resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
            if time.time() > deadline:
                raise RuntimeError("SQL warehouse timed out (is it starting up?)")
            time.sleep(1.5)
            resp = self._w.statement_execution.get_statement(resp.statement_id)
        if resp.status.state != StatementState.SUCCEEDED:
            msg = resp.status.error.message if resp.status.error else str(resp.status.state)
            raise RuntimeError(msg)

        cols = resp.manifest.schema.columns if resp.manifest and resp.manifest.schema else []
        names = [c.name for c in cols]
        types = [c.type_name.value if c.type_name else "STRING" for c in cols]
        data = (resp.result.data_array if resp.result else None) or []
        return _Result([SimpleNamespace(**{n: _convert(v, t) for n, t, v in zip(names, types, row)}) for row in data])

    def createDataFrame(self, rows: list[tuple], schema: str) -> _DataFrame:
        return _DataFrame(self, rows, schema)
