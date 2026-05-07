from enum import Enum


class ActionStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RUNNING = "RUNNING"
    TIMEOUT = "TIMEOUT"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    INVALID_ACTION = "INVALID_ACTION"
    INVALID_OBJECT = "INVALID_OBJECT"
    NOT_ALLOWED = "NOT_ALLOWED"


VALID_ACTIONS = {
    "approach",
    "observe",
    "follow",
    "wait",
    "report",
}


VALID_OBJECTS = {
    "dog",
    "cat",
    "person",
    "ball",
    "bowl",
    "bed",
    "chair",
    "potted_plant",
}


ACTION_OBJECT_RULES = {
    "approach": {
        "dog": True,
        "cat": True,
        "person": True,
        "ball": True,
        "bowl": True,
        "bed": True,
        "chair": True,
        "potted_plant": False,
    },
    "observe": {
        "dog": True,
        "cat": True,
        "person": True,
        "ball": True,
        "bowl": True,
        "bed": True,
        "chair": True,
        "potted_plant": True,
    },
    "follow": {
        "dog": True,
        "cat": True,
        "person": True,
        "ball": True,
        "bowl": False,
        "bed": False,
        "chair": False,
        "potted_plant": False,
    },
}


def validate_step(step: dict) -> ActionStatus:
    action = step.get("action")
    object_name = step.get("object")

    if action not in VALID_ACTIONS:
        return ActionStatus.INVALID_ACTION

    if action in {"wait", "report"}:
        return ActionStatus.SUCCESS

    if object_name not in VALID_OBJECTS:
        return ActionStatus.INVALID_OBJECT

    allowed = ACTION_OBJECT_RULES.get(action, {}).get(object_name, False)

    if not allowed:
        return ActionStatus.NOT_ALLOWED

    return ActionStatus.SUCCESS