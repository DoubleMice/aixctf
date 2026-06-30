from __future__ import annotations


class StrategySelector:
    def next_phase(self, current: str, solved: bool = False) -> str:
        if solved:
            return "solved"
        order = ["init", "classify", "triage", "hypothesis", "exploit", "verify", "solved"]
        if current not in order:
            return "triage"
        return order[min(order.index(current) + 1, len(order) - 2)]

    def select(self, state: dict) -> str:
        research = state.get("research_loop", {})
        if research.get("active_strategy"):
            return research["active_strategy"]
        category = state.get("category")
        if category == "pwn":
            return "pwn_triage"
        if category == "web":
            return "web_triage"
        return "classification"
