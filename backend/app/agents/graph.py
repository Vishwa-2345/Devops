"""Actual LangGraph state graph wiring all self-healing agents together.

Graph topology:

    START -> entry --(monitoring)--> monitoring -> diagnosis -> planning -> risk
                 \\                                                        |
                  --(remediation)--> remediation -> verification -> END     |
                                          ^                                 |
                                          |                                 v
                                    approval_gate <------------------------
                                          |
                            (approved / not required) -> remediation
                            (pending / rejected / invalidated) -> END

The graph is invoked twice for approval-required plans: once to analyze
(``run_analysis``) and once after approval to execute (``run_execution``).
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.nodes.approval import approval_gate_node
from app.agents.nodes.diagnosis import diagnosis_node
from app.agents.nodes.monitoring import monitoring_node
from app.agents.nodes.planning import planning_node
from app.agents.nodes.remediation import remediation_node
from app.agents.nodes.risk import risk_node
from app.agents.nodes.verification import verification_node
from app.agents.state import AgentState


def _entry_node(state: AgentState) -> AgentState:
    return {"entry": state.get("entry", "monitoring")}


def _route_entry(state: AgentState) -> str:
    entry = state.get("entry")
    if entry == "remediation":
        return "remediation"
    if entry == "planning":
        return "planning"
    return "monitoring"


def _route_after_approval(state: AgentState) -> str:
    return "remediation" if state.get("next_step") == "remediation" else "end"


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("entry", _entry_node)
    builder.add_node("monitoring", monitoring_node)
    builder.add_node("diagnosis", diagnosis_node)
    builder.add_node("planning", planning_node)
    builder.add_node("risk", risk_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("remediation", remediation_node)
    builder.add_node("verification", verification_node)

    builder.add_edge(START, "entry")
    builder.add_conditional_edges(
        "entry",
        _route_entry,
        {"monitoring": "monitoring", "planning": "planning", "remediation": "remediation"},
    )
    builder.add_edge("monitoring", "diagnosis")
    builder.add_edge("diagnosis", "planning")
    builder.add_edge("planning", "risk")
    builder.add_edge("risk", "approval_gate")
    builder.add_conditional_edges(
        "approval_gate",
        _route_after_approval,
        {"remediation": "remediation", "end": END},
    )
    builder.add_edge("remediation", "verification")
    builder.add_edge("verification", END)
    return builder.compile()


@lru_cache
def get_compiled_graph():
    return build_graph()


def run_analysis(incident_id: int) -> AgentState:
    """Run monitoring -> diagnosis -> planning -> risk -> approval gate.

    Analysis never executes a remediation; execution is a separate, explicit step.
    """
    graph = get_compiled_graph()
    initial: AgentState = {
        "incident_id": incident_id,
        "entry": "monitoring",
        "execute_now": False,
        "events": [],
    }
    return graph.invoke(initial)


def run_planning(incident_id: int) -> AgentState:
    """Run planning -> risk -> approval gate using an existing diagnosis."""
    graph = get_compiled_graph()
    initial: AgentState = {
        "incident_id": incident_id,
        "entry": "planning",
        "execute_now": False,
        "events": [],
    }
    return graph.invoke(initial)


def run_execution(incident_id: int, plan_id: int, actor: str = "local-user") -> AgentState:
    """Run remediation -> verification for an approved plan."""
    graph = get_compiled_graph()
    initial: AgentState = {
        "incident_id": incident_id,
        "plan_id": plan_id,
        "entry": "remediation",
        "execute_now": True,
        "actor": actor,
        "events": [],
    }
    return graph.invoke(initial)


def run_full(incident_id: int, actor: str = "local-user") -> AgentState:
    """Run the entire pipeline end-to-end in a single invocation.

    Only auto-executes plans that do not require approval; approval-required
    plans stop at the approval gate.
    """
    graph = get_compiled_graph()
    initial: AgentState = {
        "incident_id": incident_id,
        "entry": "monitoring",
        "execute_now": True,
        "actor": actor,
        "events": [],
    }
    return graph.invoke(initial)
