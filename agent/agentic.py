"""
Agentic orchestrator — an LLM decides which tools to call, in a loop.

STEP EXPLANATION:
  question -> LLM picks tools -> we run them -> results go back to the LLM ->
  repeat until the LLM answers (or max_steps). Every step is emitted as an event so a
  UI can stream the agent's "thinking". If the LLM is unreachable, we fall back to the
  deterministic RevenueBriefingAgent so the demo never dies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterator

from agent.briefing import BriefingResult, RevenueBriefingAgent, format_briefing, rank_actions
from agent.llm import DatabricksLLM, LLMClient
from agent.registry import RANK_TOOL, run_spark_tool, spark_tool_names, tool_specs
from agent.settings import load_settings

SYSTEM_PROMPT = """You are the Revenue Briefing Agent for a chiropractic clinic.
Your job: answer the staff member's question with a short, prioritized plan that has dollar impact.

Rules:
- Choose only the tools relevant to the question. A broad question ("what should we focus on?")
  needs all analysis tools; a narrow one ("how are our leads?") needs only the lead tools.
- Never invent numbers or do your own arithmetic. Every figure you state must come from a tool
  result. For the total, copy total_estimated_impact_usd from rank_actions exactly.
- Always run at least one analysis tool before anything else. rank_actions only works AFTER
  analysis tools have returned results; call it once, last, then write the final answer.
- Final answer: markdown, a one-line headline with the total estimated opportunity, then a
  numbered list of actions ordered by estimated impact. Each action: the focus area
  (LEADS / RETENTION / PRICING), the $ impact, and a concrete next step. No filler.
"""


@dataclass
class AgentEvent:
    """One step of the agent loop. type: tool_call | tool_result | final | fallback"""

    type: str
    data: dict

    def to_dict(self) -> dict:
        return {"type": self.type, **self.data}


class AgenticBriefingAgent:
    def __init__(
        self,
        spark: Any,
        catalog: str | None = None,
        schema: str | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.spark = spark
        self.settings = load_settings()
        self.catalog = catalog or self.settings["catalog"]
        self.schema = schema or self.settings["schema"]
        cfg = self.settings["agent"]
        self.max_steps = cfg.get("max_steps", 6)
        self.llm = llm or DatabricksLLM(cfg["llm_endpoint"], cfg.get("temperature", 0.1))

    # -- public API ---------------------------------------------------------

    def run(self, question: str | None = None) -> BriefingResult:
        """Run the loop to completion and return a BriefingResult (with .trace)."""
        trace: list[dict] = []
        result: BriefingResult | None = None
        for event in self.run_stream(question):
            trace.append(event.to_dict())
            if event.type in ("final", "fallback"):
                result = event.data["result"]
        assert result is not None
        result.trace = [t for t in trace if t["type"] in ("tool_call", "tool_result")]
        return result

    def run_stream(self, question: str | None = None) -> Iterator[AgentEvent]:
        question = question or self.settings["agent"]["default_question"]
        collected: dict[str, dict] = {}  # tool name -> output (also acts as a cache)
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        final_text: str | None = None

        try:
            for _ in range(self.max_steps):
                reply = self.llm.chat(messages, tool_specs())
                calls = reply["tool_calls"]
                if not calls:
                    final_text = reply["content"]
                    break

                messages.append({
                    "role": "assistant",
                    "content": reply["content"],
                    "tool_calls": [
                        {"id": c["id"], "type": "function",
                         "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                        for c in calls
                    ],
                })
                for call in calls:
                    yield AgentEvent("tool_call", {"tool": call["name"]})
                    output = self._execute(call["name"], collected)
                    yield AgentEvent("tool_result", {"tool": call["name"], "output": output})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(output, default=str),
                    })
        except Exception as exc:  # LLM/endpoint failure -> deterministic briefing
            yield AgentEvent("fallback", {
                "reason": f"{type(exc).__name__}: {exc}",
                "result": self._fallback(question),
            })
            return

        # Rank whatever the LLM gathered (even if it never called rank_actions itself).
        outputs = list(collected.values())
        if not outputs:
            yield AgentEvent("fallback", {
                "reason": "LLM called no tools",
                "result": self._fallback(question),
            })
            return

        actions = rank_actions(outputs)
        total = sum(a["estimated_impact_usd"] for a in actions)
        text = final_text or format_briefing(question, actions, total)
        yield AgentEvent("final", {"result": BriefingResult(
            question=question,
            actions=actions,
            total_estimated_impact_usd=total,
            tool_outputs=outputs,
            briefing_text=text,
        )})

    # -- internals ----------------------------------------------------------

    def _execute(self, name: str, collected: dict[str, dict]) -> dict:
        """Run one tool call. Errors are returned to the LLM instead of raised."""
        if name == RANK_TOOL:
            if not collected:
                return {"error": "Nothing to rank yet. Call the relevant analysis tools first, then call rank_actions."}
            actions = rank_actions(list(collected.values()))
            return {
                "ranked_actions": actions,
                "total_estimated_impact_usd": round(sum(a["estimated_impact_usd"] for a in actions), 2),
            }
        if name not in spark_tool_names():
            return {"error": f"Unknown tool '{name}'. Available: {spark_tool_names() + [RANK_TOOL]}"}
        if name in collected:
            return {**collected[name], "note": "already run; cached result"}
        try:
            collected[name] = run_spark_tool(name, self.spark, self.catalog, self.schema, self.settings)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        return collected[name]

    def _fallback(self, question: str) -> BriefingResult:
        return RevenueBriefingAgent(self.spark, self.catalog, self.schema).run(question)
