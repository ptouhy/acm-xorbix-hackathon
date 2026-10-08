"""WarehouseSession adapter tests with a fake Databricks client (no network)."""

from datetime import date, datetime, timezone
from types import SimpleNamespace as NS

import pytest

from agent.warehouse import WarehouseSession, _convert, _literal


def test_convert_maps_warehouse_strings_to_python_types():
    assert _convert("42", "LONG") == 42 and _convert("3.5", "DOUBLE") == 3.5
    assert _convert("1234.50", "DECIMAL") == 1234.5
    assert _convert("true", "BOOLEAN") is True and _convert("false", "BOOLEAN") is False
    assert _convert("2026-10-08", "DATE") == date(2026, 10, 8)
    assert _convert("2026-10-08T01:02:03Z", "TIMESTAMP").year == 2026
    assert _convert(None, "LONG") is None and _convert("x", "STRING") == "x"


def test_literal_escapes_quotes_and_backslashes_and_formats_types():
    assert _literal("it's") == "'it\\'s'" and _literal("a\\b") == "'a\\\\b'"
    assert _literal(None) == "NULL" and _literal(True) == "TRUE" and _literal(2.5) == "2.5"
    assert _literal(datetime(2026, 10, 8, 1, 2, 3, tzinfo=timezone.utc)) == "TIMESTAMP '2026-10-08 01:02:03'"


class FakeClient:
    def __init__(self, columns=(), rows=(), state="SUCCEEDED", error=None):
        self.statements = []
        outer = self

        def execute_statement(statement, warehouse_id, wait_timeout, on_wait_timeout):
            outer.statements.append(statement)
            return self._resp()

        self.statement_execution = NS(execute_statement=execute_statement,
                                      get_statement=lambda _id: self._resp())
        self.warehouses = NS(list=lambda: [NS(id="wh1")])
        self._columns, self._rows, self._state, self._error = columns, rows, state, error

    def _resp(self):
        from databricks.sdk.service.sql import StatementState
        cols = [NS(name=n, type_name=NS(value=t)) for n, t in self._columns]
        return NS(statement_id="s", status=NS(state=StatementState(self._state), error=self._error),
                  manifest=NS(schema=NS(columns=cols)), result=NS(data_array=[list(r) for r in self._rows]))


def test_sql_returns_typed_attribute_rows():
    client = FakeClient(columns=[("n", "LONG"), ("name", "STRING")], rows=[("7", "a")])
    rows = WarehouseSession(client=client).sql("SELECT 1").collect()
    assert rows[0].n == 7 and rows[0].name == "a"


def test_sql_failure_raises_runtime_error_with_the_warehouse_message():
    client = FakeClient(state="FAILED", error=NS(message="TABLE_OR_VIEW_NOT_FOUND"))
    with pytest.raises(RuntimeError, match="TABLE_OR_VIEW_NOT_FOUND"):
        WarehouseSession(client=client).sql("SELECT * FROM nope")


def test_table_exists_and_append_write_create_then_insert():
    client = FakeClient()
    s = WarehouseSession(client=client)
    assert s.catalog.tableExists("c.s.t") is True
    s.createDataFrame([("a", 1)], schema="x STRING, y INT").write.format("delta").mode("append").saveAsTable("c.s.t")
    assert client.statements[-2].startswith("CREATE TABLE IF NOT EXISTS c.s.t (x STRING, y INT)")
    assert client.statements[-1] == "INSERT INTO c.s.t VALUES ('a', 1)"
    assert s.warehouse_id == "wh1"
