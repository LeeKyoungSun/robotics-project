import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ALLOWED_OBJECTS = ["dog", "chair", "bed", "potted plant"]
ALLOWED_ACTIONS = ["approach", "observe", "wait", "report"]

LABEL_ALIAS = {
    "kite": "bed",
    "cow": "dog",
    "couch": "bed",
    "sofa": "bed",
    "plant": "potted plant"
}


def normalize_label(label: str):
    label = label.lower().strip()

    if label in ALLOWED_OBJECTS:
        return label

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

Allowed objects:
{ALLOWED_OBJECTS}

Allowed actions:
{ALLOWED_ACTIONS}

User request:
{user_text}

Detected objects after normalization:
{normalized}

Rules:
1. Use only allowed objects.
2. Use only allowed actions.
3. If the user asks to check, monitor, or look at something, use observe.
4. If the robot needs to move close to an object first, use approach before observe.
5. If the user asks for a result, end with report.
6. Return JSON only.
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
                "schema": {
                    "type": "object",
                    "properties": {
                        "sequence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "action": {
                                        "type": "string",
                                        "enum": ALLOWED_ACTIONS
                                    },
                                    "object": {
                                        "type": "string",
                                        "enum": ALLOWED_OBJECTS
                                    }
                                },
                                "required": ["action", "object"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": ["sequence"],
                    "additionalProperties": False
                },
                "strict": True
            }
        }
    )

    return json.loads(response.output_text)


if __name__ == "__main__":
    user_text = "강아지가 침대 근처에 있는지 확인해줘"
    detected_labels = ["kite", "cow"]

    result = call_llm_api(user_text, detected_labels)

    print("===== ACTION SEQUENCE =====")
    print(json.dumps(result, indent=2, ensure_ascii=False))