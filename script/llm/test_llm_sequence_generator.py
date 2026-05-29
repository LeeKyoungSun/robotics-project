#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

try:
    from script.llm.llm_sequence_generator import (
        coerce_action_sequence,
        smart_plan_sequence,
    )
except ImportError:
    from llm_sequence_generator import (
        coerce_action_sequence,
        smart_plan_sequence,
    )


def load_cases() -> list[dict]:
    case_file = Path(__file__).with_name("test_cases.json")
    return json.loads(case_file.read_text(encoding="utf-8"))


def test_smart_planner_cases():
    for case in load_cases():
        actual = smart_plan_sequence(
            case["user_text"],
            case["detected_labels"],
        )
        assert actual == case["expected_sequence"], case["scenario"]


def test_coerce_blocks_potted_plant_approach():
    actual = coerce_action_sequence(
        {
            "sequence": [
                {
                    "step_id": 99,
                    "action": "approach",
                    "object": "potted plant",
                    "params": {
                        "timeout_sec": 10.0,
                        "goal_tolerance_m": 0.1,
                        "retry_count": 0,
                    },
                }
            ]
        },
        user_text="화분으로 가까이 가줘",
        detected_labels=["potted_plant"],
    )

    assert actual == load_cases()[2]["expected_sequence"]


def test_coerce_fills_executor_params_and_step_ids():
    actual = coerce_action_sequence(
        {
            "sequence": [
                {
                    "step_id": 7,
                    "action": "navigate",
                    "object": "chair",
                    "params": {},
                },
                {
                    "step_id": 8,
                    "action": "report",
                    "object": "chair",
                    "params": {"message": "done"},
                },
            ]
        },
        user_text="의자 쪽을 확인해줘",
        detected_labels=["chair"],
    )

    assert actual == [
        {
            "step_id": 1,
            "action": "approach",
            "object": "chair",
            "params": {
                "timeout_sec": 60.0,
                "goal_tolerance_m": 0.25,
                "retry_count": 2,
            },
        },
        {
            "step_id": 2,
            "action": "report",
            "object": None,
            "params": {
                "message": "done",
            },
        },
    ]


def main():
    test_smart_planner_cases()
    test_coerce_blocks_potted_plant_approach()
    test_coerce_fills_executor_params_and_step_ids()
    print("LLM sequence generator tests passed")


if __name__ == "__main__":
    main()
