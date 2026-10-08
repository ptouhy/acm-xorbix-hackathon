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
  needs the analysis tools; a narrow one ("how are our leads?") needs only the lead tools.
- Tool kinds: ANALYSIS tools size an opportunity in dollars. DIAGNOSTIC tools explain WHY
  (use them for "why" questions, and for the top pricing/leads finding on broad questions).
  The ACTION tool draft_outreach builds today's contact list and message.
- Never invent numbers or do your own arithmetic. Every figure you state must come from a tool
  result. For the total, copy total_estimated_impact_usd from rank_actions exactly.
- Always run at least one analysis tool before anything else. rank_actions only works AFTER
  analysis tools have returned results; call it once, last, then write the final answer.
- For the top-ranked action that involves contacting people (stale leads or churn risk), call
  draft_outreach and include a short, personalized version of its message_template plus the
  first few targets, so staff can act immediately.
- If a diagnostic tool ran, the answer MUST include a "Why" section quoting its specific findings
  (segment names and rates) before the action list. Do not replace findings with generic advice.
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


def _evidence_sections(outputs: list[dict]) -> str:
    """Append diagnostic findings and outreach lists verbatim, so they never depend on the LLM."""
    why = [o for o in outputs if o.get("kind") == "diagnostic"]
    acts = [o for o in outputs if o.get("kind") == "action"]
    lines: list[str] = []
    if why:
        lines += ["", "## Why (diagnostics)"] + [f"- **{o['tool']}**: {o['recommendation']}" for o in why]
    for o in acts:
        m = o["metrics"]
        lines += ["", f"## Act now: {m['segment'].replace('_', ' ')} ({m['batch_size']} of {m['segment_size']:,})",
                  f"_{o['recommendation']}_", "", f"> {o['message_template']}", ""]
        for t in o["targets"][:5]:
            ident = t.get("lead_id") or t.get("patient_id")
            detail = ", ".join(f"{k}={v}" for k, v in t.items() if k not in ("lead_id", "patient_id"))
            lines.append(f"- {ident}: {detail}")
    return "\n".join(lines)


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
                    yield AgentEvent("tool_call", {"tool": call["name"], "args": call["arguments"]})
                    output = self._execute(call["name"], call["arguments"], collected)
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
        text = (final_text or format_briefing(question, actions, total)) + _evidence_sections(outputs)
        yield AgentEvent("final", {"result": BriefingResult(
            question=question,
            actions=actions,
            total_estimated_impact_usd=total,
            tool_outputs=outputs,
            briefing_text=text,
        )})

    # -- internals ----------------------------------------------------------

    def _execute(self, name: str, args: dict, collected: dict[str, dict]) -> dict:
        """Run one tool call. Errors are returned to the LLM instead of raised."""
        if name == RANK_TOOL:
            if not any(r.get("kind", "analysis") == "analysis" for r in collected.values()):
                return {"error": "Nothing to rank yet. Call the relevant analysis tools first, then call rank_actions."}
            actions = rank_actions(list(collected.values()))
            return {
                "ranked_actions": actions,
                "total_estimated_impact_usd": round(sum(a["estimated_impact_usd"] for a in actions), 2),
            }
        if name not in spark_tool_names():
            return {"error": f"Unknown tool '{name}'. Available: {spark_tool_names() + [RANK_TOOL]}"}
        key = name if not args else f"{name}:{json.dumps(args, sort_keys=True)}"
        if key in collected:
            return {**collected[key], "note": "already run; cached result"}
        try:
            collected[key] = run_spark_tool(name, self.spark, self.catalog, self.schema, self.settings, args)
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        return collected[key]

    def _fallback(self, question: str) -> BriefingResult:
        return RevenueBriefingAgent(self.spark, self.catalog, self.schema).run(question)
