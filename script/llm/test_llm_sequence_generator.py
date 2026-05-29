#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

try:
    from script.llm.llm_sequence_generator import (
        build_prompt,
        coerce_action_sequence,
        smart_plan_sequence,
    )
except ImportError:
    from llm_sequence_generator import (
        build_prompt,
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


def test_coerce_preserves_llm_multi_step_plan():
    actual = coerce_action_sequence(
        {
            "sequence": [
                {
                    "step_id": 10,
                    "action": "approach",
                    "object": "bed",
                    "params": {"retry_count": 1},
                },
                {
                    "step_id": 20,
                    "action": "wait",
                    "object": None,
                    "params": {"duration_sec": 3.0},
                },
                {
                    "step_id": 30,
                    "action": "observe",
                    "object": "dog",
                    "params": {},
                },
                {
                    "step_id": 40,
                    "action": "report",
                    "object": None,
                    "params": {"message": "custom plan completed"},
                },
            ]
        },
        user_text="check the bed, wait, then observe the dog",
        detected_labels=["bed", "dog"],
    )

    assert actual == [
        {
            "step_id": 1,
            "action": "approach",
            "object": "bed",
            "params": {
                "timeout_sec": 60.0,
                "goal_tolerance_m": 0.25,
                "retry_count": 1,
            },
        },
        {
            "step_id": 2,
            "action": "wait",
            "object": None,
            "params": {
                "duration_sec": 3.0,
            },
        },
        {
            "step_id": 3,
            "action": "observe",
            "object": "dog",
            "params": {
                "duration_sec": 5.0,
            },
        },
        {
            "step_id": 4,
            "action": "report",
            "object": None,
            "params": {
                "message": "custom plan completed",
            },
        },
    ]


def test_prompt_requests_intermediate_step_planning():
    prompt = build_prompt(
        "침대 확인하고 잠시 기다린 다음 강아지 상태 알려줘",
        ["bed", "dog"],
    )

    assert "You must decide the intermediate steps yourself" in prompt
    assert "Do not only classify the" in prompt
    assert "If the user requests multiple targets, preserve the requested order" in prompt


def main():
    test_smart_planner_cases()
    test_coerce_blocks_potted_plant_approach()
    test_coerce_fills_executor_params_and_step_ids()
    test_coerce_preserves_llm_multi_step_plan()
    test_prompt_requests_intermediate_step_planning()
    print("LLM sequence generator tests passed")


if __name__ == "__main__":
    main()
