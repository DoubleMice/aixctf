from __future__ import annotations

from pathlib import Path
from typing import Any

from runner.handoff_collector import HandoffCollector
from runner.strategy_selector import StrategySelector


class LoopCore:
    def __init__(self, agent_root: Path, workspace: Path):
        self.agent_root = agent_root
        self.workspace = workspace
        self.handoff_collector = HandoffCollector(workspace)
        self.strategy_selector = StrategySelector()

    def prepare_round(self, state: dict[str, Any], round_id: int) -> dict[str, Any]:
        strategy = self.strategy_selector.select(state)
        return {"active_strategy": strategy}

    def merge_subtasks(self, state: dict[str, Any], subtasks: list[dict[str, Any]]) -> dict[str, Any]:
        return self.handoff_collector.merge_subtasks(state, subtasks)
