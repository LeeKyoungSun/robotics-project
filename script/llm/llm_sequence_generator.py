import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ALLOWED_OBJECTS = [
    "dog",
    "cat",
    "bowl",
    "ball",
    "bed",
    "chair",
    "potted_plant",
]

ALLOWED_ACTIONS = [
    "approach",
    "observe",
    "wait",
    "report",
]

LABEL_ALIAS = {
    "potted plant": "potted_plant",
    "plant": "potted_plant",
    "airplane": "potted_plant",
    "sports ball": "ball",
    "cup": "bowl",
    "dish": "bowl",
    "plate": "bowl",
    "kite": "bed",
    "couch": "bed",
    "sofa": "bed",
    "horse": "dog",
    "cow": "dog",
}

ACTION_SEQUENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "sequence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {
                        "type": "integer"
                    },
                    "action": {
                        "type": "string",
                        "enum": ALLOWED_ACTIONS
                    },
                    "object": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": ALLOWED_OBJECTS
                            },
                            {
                                "type": "null"
                            }
                        ]
                    },
                    "params": {
                        "type": "object",
                        "properties": {
                            "timeout_sec": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"}
                                ]
                            },
                            "goal_tolerance_m": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"}
                                ]
                            },
                            "retry_count": {
                                "anyOf": [
                                    {"type": "integer"},
                                    {"type": "null"}
                                ]
                            },
                            "duration_sec": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"}
                                ]
                            },
                            "message": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"}
                                ]
                            }
                        },
                        "required": [
                            "timeout_sec",
                            "goal_tolerance_m",
                            "retry_count",
                            "duration_sec",
                            "message"
                        ],
                        "additionalProperties": False
                    }
                },
                "required": [
                    "step_id",
                    "action",
                    "object",
                    "params"
                ],
                "additionalProperties": False
            }
        }
    },
    "required": ["sequence"],
    "additionalProperties": False
}

def normalize_label(label: str):
    label = label.lower().strip().replace(" ", "_")

    reverse_alias_key = label.replace("_", " ")

    if label in ALLOWED_OBJECTS:
        return label

    if reverse_alias_key in LABEL_ALIAS:
        return LABEL_ALIAS[reverse_alias_key]

    if label in LABEL_ALIAS:
        return LABEL_ALIAS[label]

    return None


def build_prompt(user_text: str, detected_labels: list[str]) -> str:
    normalized = []

    for label in detected_labels:
        obj = normalize_label(label)
        if obj and obj not in normalized:
            normalized.append(obj)

    return f"""
You are a robot action planner for a pet-care robot.

Your task is to convert a Korean user request into an executable action sequence.

Allowed objects:
{ALLOWED_OBJECTS}

Allowed actions:
{ALLOWED_ACTIONS}

Detected objects after normalization:
{normalized}

User request:
{user_text}

Use the following scenario patterns.

1. Feeding scenario:
- If the request is about feeding, meal, food, rice, 밥, 밥그릇, 급식, 배고픔:
  step 1: approach bowl with timeout_sec=60.0, goal_tolerance_m=0.25, retry_count=2
  step 2: wait with object null and duration_sec=2.0
  step 3: observe dog with duration_sec=5.0
  step 4: report with object null and message "feeding scenario completed"

2. Play scenario:
- If the request is about play, toy, ball, 심심함, 놀아주기:
  step 1: approach ball with timeout_sec=60.0, goal_tolerance_m=0.25, retry_count=2
  step 2: observe dog with duration_sec=5.0
  step 3: report with object null and message "play scenario completed"

3. Potted plant safety scenario:
- potted_plant is observe-only.
- Never approach potted_plant.
- If the request asks to approach potted_plant, replace it with:
  step 1: observe potted_plant with duration_sec=5.0
  step 2: report with object null and message "potted plant is observe-only target. approach blocked for safety"

4. Static multi-target scenario:
- If the request asks to check bowl, bed, and chair in sequence:
  step 1: approach bowl with timeout_sec=60.0, goal_tolerance_m=0.25, retry_count=2
  step 2: approach bed with timeout_sec=60.0, goal_tolerance_m=0.25, retry_count=2
  step 3: approach chair with timeout_sec=60.0, goal_tolerance_m=0.25, retry_count=2

5. Monitoring scenario:
- If the request is only about checking the pet condition:
  step 1: observe dog or cat with duration_sec=5.0
  step 2: report with object null and message "pet monitoring completed"

Rules:
1. Return JSON only.
2. Use only allowed objects.
3. Use only allowed actions.
4. object may be null only for wait and report.
5. step_id must start from 1 and increase by 1.
6. approach params must include timeout_sec, goal_tolerance_m, retry_count.
7. observe params must include duration_sec.
8. wait params must include duration_sec.
9. report params must include message.
10. Never approach potted_plant.
11. If the request is ambiguous, choose the most likely scenario based on the detected objects. If no scenario matches, return an empty sequence.
12. Always try to include an observe step before report to confirm the action result, unless the scenario is clearly about waiting or reporting without observation.
13. Keep the sequence as short as possible while fulfilling the user request and following the rules.
14. For params, always include all five keys: timeout_sec, goal_tolerance_m, retry_count, duration_sec, message. For unused params, use null.
"""


def call_llm_api(user_text: str, detected_labels: list[str]):
    prompt = build_prompt(user_text, detected_labels)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "action_sequence",
                "schema": ACTION_SEQUENCE_SCHEMA,
                "strict": True
            }
        }
    )

    return json.loads(response.output_text)


if __name__ == "__main__":
    user_text = "강아지 밥 챙겨줘"
    detected_labels = ["dog"]

    result = call_llm_api(user_text, detected_labels)

    print("===== ACTION SEQUENCE =====")
    print(json.dumps(result, indent=2, ensure_ascii=False))