from __future__ import annotations

from typing import Any


class ReflectionEngine:
    def build_loop(self, state: dict[str, Any], parsed: dict[str, Any], observations: list[str], artifacts: list[str]) -> dict[str, Any]:
        research = state.get("research_loop", {})
        question = parsed.get("research_question") or research.get("current_question") or default_question(state)
        hypothesis = parsed.get("hypothesis") or research.get("current_hypothesis") or default_hypothesis(state)
        experiment = parsed.get("experiment") or parsed.get("next_action") or "Run the next bounded challenge experiment."
        conclusion = parsed.get("conclusion") or infer_conclusion(parsed, observations)
        next_experiment = parsed.get("next_experiment") or parsed.get("next_plan") or "Continue with the lowest-cost experiment that can change state."
        return {
            "research_question": question,
            "hypothesis": hypothesis,
            "experiment": experiment,
            "observation": observations,
            "evidence": sorted(dict.fromkeys((parsed.get("evidence") or []) + artifacts)),
            "conclusion": conclusion,
            "state_delta": parsed.get("state_delta") or {},
            "next_experiment": next_experiment,
        }


def default_question(state: dict[str, Any]) -> str:
    phase = state.get("phase", "init")
    if phase in {"init", "classify"}:
        return "What category and initial attack surface does this challenge expose?"
    return "What is the next experiment that can advance the solve state?"


def default_hypothesis(state: dict[str, Any]) -> str:
    category = state.get("category", "unknown")
    if category == "pwn":
        return "The challenge can be advanced by binary triage and exploit-path confirmation."
    if category == "web":
        return "The challenge can be advanced by HTTP/source triage and vulnerability probing."
    return "Basic challenge triage will reveal the category and next strategy."


def infer_conclusion(parsed: dict[str, Any], observations: list[str]) -> str:
    if parsed.get("failure_reason"):
        return f"Experiment did not solve the challenge: {parsed['failure_reason']}."
    if parsed.get("confirmed_flag"):
        return "Flag is confirmed with evidence."
    if observations:
        return observations[-1]
    return "Experiment completed without a specific conclusion."
