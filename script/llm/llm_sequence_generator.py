#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from script.action_schema import ActionStatus, validate_step
except ImportError:
    try:
        from action_schema import ActionStatus, validate_step
    except ImportError:
        ActionStatus = None
        validate_step = None

if load_dotenv is not None:
    load_dotenv()


ALLOWED_OBJECTS = [
    "dog",
    "cat",
    "apple",
    "ball",
    "bed",
    "chair",
    "vase",
]

KNOWN_WORLD_OBJECTS = [
    "dog",
    "cat",
    "apple",
    "ball",
    "bed",
    "chair",
    "vase",
]

ALLOWED_ACTIONS = [
    "approach",
    "observe",
    "wait",
    "report",
]

APPROACH_PARAMS = {
    "timeout_sec": 60.0,
    "goal_tolerance_m": 0.25,
    "retry_count": 2,
}

OBSERVE_PARAMS = {
    "duration_sec": 5.0,
}

WAIT_PARAMS = {
    "duration_sec": 2.0,
}

REPORT_MESSAGES = {
    "feeding": "feeding scenario completed",
    "play": "play scenario completed",
    "pet_monitoring": "pet monitoring completed",
    "vase_safety": (
        "vase is observe-only target. approach blocked for safety"
    ),
    "bed_check": "bed check completed",
    "chair_check": "chair check completed",
    "apple_check": "apple check completed",
    "ball_check": "ball check completed",
    "no_valid_target": "no valid target detected",
}

LABEL_ALIAS = {
    "dog": "dog",
    "puppy": "dog",
    "강아지": "dog",
    "개": "dog",
    "cat": "cat",
    "고양이": "cat",
    "apple": "apple",
    "cup": "apple",
    "dish": "apple",
    "plate": "apple",
    "그릇": "apple",
    "밥그릇": "apple",
    "ball": "ball",
    "sports ball": "ball",
    "sports_ball": "ball",
    "공": "ball",
    "bed": "bed",
    "couch": "bed",
    "sofa": "bed",
    "침대": "bed",
    "chair": "chair",
    "의자": "chair",
    "vase": "vase",
    "plant": "vase",
    "airplane": "vase",
    "화분": "vase",
}

ACTION_ALIAS = {
    "approach": "approach",
    "move": "approach",
    "go": "approach",
    "navigate": "approach",
    "접근": "approach",
    "이동": "approach",
    "가까이": "approach",
    "observe": "observe",
    "watch": "observe",
    "check": "observe",
    "inspect": "observe",
    "관찰": "observe",
    "확인": "observe",
    "살펴": "observe",
    "wait": "wait",
    "기다": "wait",
    "대기": "wait",
    "report": "report",
    "보고": "report",
    "알려": "report",
}

APPROACH_OBJECTS = {
    "dog",
    "cat",
    "apple",
    "ball",
    "bed",
    "chair",
}

OBSERVE_OBJECTS = {
    "dog",
    "cat",
    "vase",
}

ACTION_SEQUENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "sequence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "integer"},
                    "action": {
                        "type": "string",
                        "enum": ALLOWED_ACTIONS,
                    },
                    "object": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": ALLOWED_OBJECTS,
                            },
                            {"type": "null"},
                        ]
                    },
                    "params": {
                        "type": "object",
                        "properties": {
                            "timeout_sec": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"},
                                ]
                            },
                            "goal_tolerance_m": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"},
                                ]
                            },
                            "retry_count": {
                                "anyOf": [
                                    {"type": "integer"},
                                    {"type": "null"},
                                ]
                            },
                            "duration_sec": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"},
                                ]
                            },
                            "message": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"},
                                ]
                            },
                        },
                        "required": [
                            "timeout_sec",
                            "goal_tolerance_m",
                            "retry_count",
                            "duration_sec",
                            "message",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": [
                    "step_id",
                    "action",
                    "object",
                    "params",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sequence"],
    "additionalProperties": False,
}


def normalize_label(label: str | None) -> str | None:
    if label is None:
        return None

    normalized = str(label).lower().strip().replace("-", " ")
    normalized = normalized.replace("_", " ")

    if normalized.replace(" ", "_") in ALLOWED_OBJECTS:
        return normalized.replace(" ", "_")

    return LABEL_ALIAS.get(normalized)


def normalize_labels(labels: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized = []

    for label in labels or []:
        object_name = normalize_label(label)
        if object_name and object_name not in normalized:
            normalized.append(object_name)

    return normalized


def normalize_action(action: str | None) -> str | None:
    if action is None:
        return None

    normalized = str(action).lower().strip()

    if normalized in ALLOWED_ACTIONS:
        return normalized

    for keyword, mapped_action in ACTION_ALIAS.items():
        if keyword in normalized:
            return mapped_action

    return None


def make_step(
    step_id: int,
    action: str,
    object_name: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "action": action,
        "object": object_name,
        "params": dict(params or {}),
    }


def approach_step(step_id: int, object_name: str) -> dict[str, Any]:
    return make_step(step_id, "approach", object_name, APPROACH_PARAMS)


def observe_step(step_id: int, object_name: str) -> dict[str, Any]:
    return make_step(step_id, "observe", object_name, OBSERVE_PARAMS)


def wait_step(step_id: int) -> dict[str, Any]:
    return make_step(step_id, "wait", None, WAIT_PARAMS)


def report_step(step_id: int, message: str) -> dict[str, Any]:
    return make_step(step_id, "report", None, {"message": message})


def feeding_sequence() -> list[dict[str, Any]]:
    return [
        approach_step(1, "apple"),
        wait_step(2),
        observe_step(3, "dog"),
        report_step(4, REPORT_MESSAGES["feeding"]),
    ]


def play_sequence() -> list[dict[str, Any]]:
    return [
        approach_step(1, "ball"),
        observe_step(2, "dog"),
        report_step(3, REPORT_MESSAGES["play"]),
    ]


def vase_safety_sequence() -> list[dict[str, Any]]:
    return [
        observe_step(1, "vase"),
        report_step(2, REPORT_MESSAGES["vase_safety"]),
    ]


def static_multi_target_sequence() -> list[dict[str, Any]]:
    return [
        approach_step(1, "apple"),
        approach_step(2, "bed"),
        approach_step(3, "chair"),
    ]


def pet_monitoring_sequence(object_name: str) -> list[dict[str, Any]]:
    return [
        observe_step(1, object_name),
        report_step(2, REPORT_MESSAGES["pet_monitoring"]),
    ]


def multi_pet_monitoring_sequence(object_names: list[str]) -> list[dict[str, Any]]:
    sequence = [
        observe_step(index, object_name)
        for index, object_name in enumerate(object_names, start=1)
    ]
    sequence.append(
        report_step(len(sequence) + 1, REPORT_MESSAGES["pet_monitoring"])
    )
    return sequence


def object_check_sequence(object_name: str) -> list[dict[str, Any]]:
    message_key = f"{object_name}_check"
    return [
        approach_step(1, object_name),
        report_step(2, REPORT_MESSAGES.get(message_key, f"{object_name} check completed")),
    ]


def no_valid_target_sequence() -> list[dict[str, Any]]:
    return [
        wait_step(1),
        report_step(2, REPORT_MESSAGES["no_valid_target"]),
    ]


def has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


OBJECT_REQUEST_KEYWORDS = [
    ("dog", ["dog", "puppy", "강아지", "개"]),
    ("cat", ["cat", "고양이"]),
    ("apple", ["apple", "사과", "밥", "급식", "먹이", "food", "meal", "feed", "rice"]),
    ("ball", ["ball", "공", "장난감", "toy", "play"]),
    ("bed", ["bed", "침대"]),
    ("chair", ["chair", "의자"]),
    ("vase", ["vase", "화분", "plant", "potted"]),
]


def requested_objects_from_text(user_text: str) -> list[str]:
    text = (user_text or "").lower()
    requested = []

    for object_name, keywords in OBJECT_REQUEST_KEYWORDS:
        if object_name not in KNOWN_WORLD_OBJECTS:
            continue

        match_positions = [
            text.find(keyword)
            for keyword in keywords
            if keyword in text
        ]
        if match_positions:
            requested.append((min(match_positions), object_name))

    return [
        object_name
        for _, object_name in sorted(requested)
    ]


def sequence_object_names(sequence: list[dict[str, Any]]) -> set[str]:
    return {
        step["object"]
        for step in sequence
        if isinstance(step, dict)
        and step.get("action") in {"approach", "observe", "follow"}
        and step.get("object")
    }


def multi_object_check_sequence(object_names: list[str]) -> list[dict[str, Any]]:
    return [
        approach_step(index, object_name)
        for index, object_name in enumerate(object_names, start=1)
    ]


def smart_plan_sequence(
    user_text: str,
    detected_labels: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Deterministic planner used as a local fallback and as a guardrail around
    LLM output. It maps requests to the predefined executor action vocabulary.
    """

    text = (user_text or "").lower()
    labels = set(normalize_labels(detected_labels))
    requested_objects = requested_objects_from_text(text)

    if "vase" in requested_objects:
        return vase_safety_sequence()

    if has_any(text, ["밥", "급식", "먹이", "food", "meal", "feed", "rice", "배고픔"]):
        return feeding_sequence()

    if has_any(text, ["놀이", "놀아", "장난감", "공", "toy", "ball", "play", "심심"]):
        return play_sequence()

    requested_pets = [
        object_name
        for object_name in requested_objects
        if object_name in {"dog", "cat"}
    ]
    if len(requested_pets) > 1:
        return multi_pet_monitoring_sequence(requested_pets)

    requested_static_targets = [
        object_name
        for object_name in requested_objects
        if object_name in {"apple", "bed", "chair", "ball"}
    ]
    if len(requested_static_targets) > 1:
        return multi_object_check_sequence(requested_static_targets)

    multi_text = all(keyword in text for keyword in ["그릇", "침대", "의자"])
    if multi_text:
        return static_multi_target_sequence()

    static_target_keywords = [
        ("bed", ["침대", "bed"]),
        ("chair", ["의자", "chair"]),
        ("apple", ["사과", "apple", "그릇", "밥그릇"]),
        ("ball", ["공", "ball"]),
    ]

    for object_name, keywords in static_target_keywords:
        if has_any(text, keywords):
            return object_check_sequence(object_name)

    monitoring_requested = has_any(
        text,
        ["상태", "condition", "monitor", "관찰", "확인", "살펴", "체크"],
    )

    if has_any(text, ["강아지", "dog"]) and not labels.intersection(
        {"bed", "chair", "apple", "ball"}
    ):
        return pet_monitoring_sequence("dog")

    if has_any(text, ["고양이", "cat"]) and not labels.intersection(
        {"bed", "chair", "apple", "ball"}
    ):
        return pet_monitoring_sequence("cat")

    if "dog" in requested_objects:
        return pet_monitoring_sequence("dog")

    if "cat" in requested_objects:
        return pet_monitoring_sequence("cat")

    if "vase" in labels:
        return vase_safety_sequence()

    multi_labels = {"apple", "bed", "chair"}.issubset(labels)
    if multi_labels:
        return static_multi_target_sequence()

    if "dog" in labels and monitoring_requested:
        return pet_monitoring_sequence("dog")

    if "cat" in labels and monitoring_requested:
        return pet_monitoring_sequence("cat")

    for object_name, _ in static_target_keywords:
        if object_name in labels:
            return object_check_sequence(object_name)

    if "dog" in labels:
        return pet_monitoring_sequence("dog")

    if "cat" in labels:
        return pet_monitoring_sequence("cat")

    return no_valid_target_sequence()


def param_value(params: dict[str, Any], key: str, default: Any) -> Any:
    value = params.get(key)
    return default if value is None else value


def compact_params(action: str, params: dict[str, Any] | None) -> dict[str, Any]:
    params = params or {}

    if action == "approach":
        return {
            "timeout_sec": float(
                param_value(params, "timeout_sec", APPROACH_PARAMS["timeout_sec"])
            ),
            "goal_tolerance_m": float(
                param_value(
                    params,
                    "goal_tolerance_m",
                    APPROACH_PARAMS["goal_tolerance_m"],
                )
            ),
            "retry_count": int(
                param_value(params, "retry_count", APPROACH_PARAMS["retry_count"])
            ),
        }

    if action == "observe":
        return {
            "duration_sec": float(
                param_value(params, "duration_sec", OBSERVE_PARAMS["duration_sec"])
            ),
        }

    if action == "wait":
        return {
            "duration_sec": float(
                param_value(params, "duration_sec", WAIT_PARAMS["duration_sec"])
            ),
        }

    if action == "report":
        message = params.get("message") or "sequence completed"
        return {
            "message": str(message),
        }

    return {}


def is_valid_step(step: dict[str, Any]) -> bool:
    if validate_step is None or ActionStatus is None:
        action = step.get("action")
        object_name = step.get("object")

        if action not in ALLOWED_ACTIONS:
            return False

        if action in {"wait", "report"}:
            return object_name is None

        if action == "approach":
            return object_name in APPROACH_OBJECTS

        if action == "observe":
            return object_name in OBSERVE_OBJECTS

        return False

    return validate_step(step) == ActionStatus.SUCCESS


def coerce_action_sequence(
    llm_output: dict[str, Any] | list[dict[str, Any]] | None,
    user_text: str = "",
    detected_labels: list[str] | None = None,
) -> list[dict[str, Any]]:
    if llm_output is None:
        return smart_plan_sequence(user_text, detected_labels)

    raw_sequence = llm_output.get("sequence", []) if isinstance(llm_output, dict) else llm_output

    if not isinstance(raw_sequence, list):
        return smart_plan_sequence(user_text, detected_labels)

    coerced: list[dict[str, Any]] = []

    for raw_step in raw_sequence:
        if not isinstance(raw_step, dict):
            continue

        action = normalize_action(raw_step.get("action"))
        object_name = normalize_label(raw_step.get("object"))
        params = raw_step.get("params")
        params = params if isinstance(params, dict) else {}

        if object_name == "vase" and action == "approach":
            return vase_safety_sequence()

        if action in {"wait", "report"}:
            object_name = None

        if action is None:
            if object_name == "vase":
                action = "observe"
            elif object_name in APPROACH_OBJECTS:
                action = "approach"
            else:
                continue

        step = make_step(
            len(coerced) + 1,
            action,
            object_name,
            compact_params(action, params),
        )

        if is_valid_step(step):
            coerced.append(step)

    if not coerced:
        return smart_plan_sequence(user_text, detected_labels)

    requested_objects = set(requested_objects_from_text(user_text))
    planned_objects = sequence_object_names(coerced)
    if requested_objects and not requested_objects.issubset(planned_objects):
        return smart_plan_sequence(user_text, detected_labels)

    return [
        {
            **step,
            "step_id": index,
        }
        for index, step in enumerate(coerced, start=1)
    ]


def build_prompt(user_text: str, detected_labels: list[str]) -> str:
    normalized = normalize_labels(detected_labels)

    return f"""
You are a robot action planner for a pet-care robot.

Plan the full executable action sequence for the Korean user request.

You must decide the intermediate steps yourself. Do not only classify the
request into a fixed scenario. Choose the target objects, action order, waits,
observations, and final report based on the user request, detected objects, and
safety rules.

Known world objects:
{KNOWN_WORLD_OBJECTS}

Allowed objects:
{ALLOWED_OBJECTS}

Allowed actions:
{ALLOWED_ACTIONS}

Detected objects after normalization:
{normalized}

User request:
{user_text}

Planning policy:
- Prefer the user's explicit request over automatic scenario assumptions.
- Build the scenario from Known world objects and the user's explicit request.
- Use detected objects only as visibility context. Do not choose a detected
  object as the task target when the user explicitly requested another known
  world object.
- Keep the sequence as short as possible while still completing the request.
- Add intermediate steps only when they are useful for the task.
- Use approach for reachable navigation targets.
- Use observe to inspect or confirm pet/object state.
- Use wait when the task implies feeding time, delay, or a short pause.
- Use report when the user asks to be told the result, or when reporting is the
  natural final step of the task.
- If the user requests multiple targets, preserve the requested order.
- If the user asks for an unsafe or impossible action, produce the safest
  executable alternative and report why.

Safety and object rules:
- Never approach vase. It is observe-only.
- If the user asks to approach vase, replace it with observe
  vase and report "{REPORT_MESSAGES["vase_safety"]}".
- object may be null only for wait and report.
- Do not invent objects outside the allowed object list.

Examples of valid plans:
- "강아지 밥 챙겨줘" with dog visible:
  approach apple -> wait -> observe dog -> report
- "침대 보고 의자도 확인해줘":
  approach bed -> approach chair -> report
- "화분으로 가까이 가줘":
  observe vase -> report
- "강아지 상태 알려줘":
  observe dog -> report

Output rules:
1. Return JSON only.
2. Use only allowed objects and actions.
3. object may be null only for wait and report.
4. step_id must start from 1 and increase by 1.
5. approach params: timeout_sec=60.0, goal_tolerance_m=0.25, retry_count=2.
6. observe params: duration_sec=5.0.
7. wait params: duration_sec=2.0 unless requested otherwise.
8. report params: message.
9. If no executable plan can be made, return wait 2 seconds and report
   "no valid target detected".
10. For params, include all five schema keys. Use null for unused params.
"""


def parse_response_json(output_text: str) -> dict[str, Any]:
    parsed = json.loads(output_text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object")
    return parsed


def call_llm_api(
    user_text: str,
    detected_labels: list[str],
    *,
    use_fallback: bool = True,
) -> dict[str, list[dict[str, Any]]]:
    prompt = build_prompt(user_text, detected_labels)
    api_key = os.getenv("OPENAI_API_KEY")

    if OpenAI is None or not api_key:
        if not use_fallback:
            raise RuntimeError("OpenAI client or OPENAI_API_KEY is not available")
        return {
            "sequence": smart_plan_sequence(user_text, detected_labels),
        }

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "action_sequence",
                    "schema": ACTION_SEQUENCE_SCHEMA,
                    "strict": True,
                }
            },
        )
        raw_result = parse_response_json(response.output_text)
        return {
            "sequence": coerce_action_sequence(
                raw_result,
                user_text=user_text,
                detected_labels=detected_labels,
            )
        }

    except Exception:
        if not use_fallback:
            raise
        return {
            "sequence": smart_plan_sequence(user_text, detected_labels),
        }


if __name__ == "__main__":
    result = call_llm_api("강아지 밥 챙겨줘", ["dog"])

    print("===== ACTION SEQUENCE =====")
    print(json.dumps(result, indent=2, ensure_ascii=False))
