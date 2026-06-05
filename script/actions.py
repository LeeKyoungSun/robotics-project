#!/usr/bin/env python3

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

try:
    from script.action_schema import ActionStatus
except ImportError:
    from action_schema import ActionStatus

if TYPE_CHECKING:
    try:
        from script.nav2_goal_sender import Nav2GoalSender
    except ImportError:
        from nav2_goal_sender import Nav2GoalSender


def approach_action(
    node: Nav2GoalSender,
    object_name: str,
    timeout_sec: float = 60.0,
    goal_tolerance_m: float = 0.25,
) -> ActionStatus:
    """
    target object 위치로 한 번 이동하는 action.
    retry는 sequence_executor에서 담당
    """

    node.get_logger().info(f"[APPROACH] start approach to {object_name}")

    result = node.navigate_to_object(
        object_name=object_name,
        timeout_sec=timeout_sec,
        goal_tolerance_m=goal_tolerance_m,
    )

    if result.success:
        node.get_logger().info(f"[APPROACH] {object_name} SUCCESS")
        return ActionStatus.SUCCESS

    node.get_logger().warn(
        f"[APPROACH] {object_name} failed: {result.state.value}"
    )

    if result.state.value == "TIMEOUT":
        return ActionStatus.TIMEOUT

    if result.state.value == "REJECTED":
        return ActionStatus.REJECTED

    return ActionStatus.FAILED


def wait_action(duration_sec: float = 3.0) -> ActionStatus:
    """
    지정된 시간 동안 대기하는 action
    """

    print(f"[WAIT] waiting for {duration_sec} sec")
    time.sleep(duration_sec)
    return ActionStatus.SUCCESS


def observe_action(
    object_name: str,
    duration_sec: float = 5.0,
) -> ActionStatus:
    """
    object를 관찰하는 action
    아직 Vision 미연동 상태이므로 placeholder로 구현
    """

    print(f"[OBSERVE] observing {object_name} for {duration_sec} sec")
    time.sleep(duration_sec)
    print(f"[OBSERVE] {object_name} observation finished")
    return ActionStatus.SUCCESS


def normalize_detection_label(label) -> str:
    return str(label or "").strip().lower().replace("-", "_").replace(" ", "_")


def detection_matches_target(detection: dict, object_name: str) -> bool:
    label = normalize_detection_label(detection.get("label"))
    target = normalize_detection_label(object_name)

    return bool(label) and label == target


def extract_detection_list(data: str) -> list[dict]:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        detections = (
            payload.get("detections")
            or payload.get("filtered_detections")
            or payload.get("objects")
            or []
        )
    elif isinstance(payload, list):
        detections = payload
    else:
        detections = []

    return [
        detection
        for detection in detections
        if isinstance(detection, dict)
    ]


def search_action(
    node: Nav2GoalSender,
    object_name: str,
    timeout_sec: float = 45.0,
    scan_duration_sec: float = 4.0,
    angular_speed: float = 0.35,
    detection_topic: str = "/vision/detections",
    cmd_vel_topic: str = "/cmd_vel",
    patrol_objects: list[str] | None = None,
    navigation_timeout_sec: float = 20.0,
    goal_tolerance_m: float = 0.35,
) -> ActionStatus:
    """
    Search for an object using live detections.

    The action rotates in place while watching the detection topic. If patrol
    objects are provided, it moves through those known locations and scans at
    each stop until the target is detected or the timeout expires.
    """

    import rclpy
    from geometry_msgs.msg import Twist
    from std_msgs.msg import String

    found = {
        "value": False,
    }

    def detection_callback(msg):
        for detection in extract_detection_list(msg.data):
            if detection_matches_target(detection, object_name):
                found["value"] = True
                return

    publisher = node.create_publisher(Twist, cmd_vel_topic, 10)
    subscription = node.create_subscription(
        String,
        detection_topic,
        detection_callback,
        10,
    )

    deadline = time.monotonic() + max(timeout_sec, 0.0)
    scan_duration_sec = max(scan_duration_sec, 0.2)
    patrol_objects = list(patrol_objects or [])

    def stop_robot():
        publisher.publish(Twist())

    def spin_scan(duration_sec: float) -> bool:
        scan_deadline = min(time.monotonic() + duration_sec, deadline)

        while (
            rclpy.ok()
            and not found["value"]
            and time.monotonic() < scan_deadline
        ):
            command = Twist()
            command.angular.z = angular_speed
            publisher.publish(command)
            rclpy.spin_once(node, timeout_sec=0.1)

        stop_robot()
        return found["value"]

    try:
        print(f"[SEARCH] searching for {object_name}")

        if spin_scan(scan_duration_sec):
            print(f"[SEARCH] {object_name} detected")
            return ActionStatus.SUCCESS

        for patrol_object in patrol_objects:
            if found["value"] or time.monotonic() >= deadline:
                break

            if hasattr(node, "navigate_to_object"):
                remaining_sec = deadline - time.monotonic()
                nav_timeout_sec = min(max(navigation_timeout_sec, 0.1), remaining_sec)

                print(f"[SEARCH] moving to scan point: {patrol_object}")
                result = node.navigate_to_object(
                    object_name=patrol_object,
                    timeout_sec=nav_timeout_sec,
                    goal_tolerance_m=goal_tolerance_m,
                )

                if found["value"]:
                    print(f"[SEARCH] {object_name} detected")
                    return ActionStatus.SUCCESS

                if not result.success:
                    print(
                        f"[SEARCH] scan point {patrol_object} navigation failed: "
                        f"{result.state.value}"
                    )

            if spin_scan(scan_duration_sec):
                print(f"[SEARCH] {object_name} detected")
                return ActionStatus.SUCCESS

        print(f"[SEARCH] {object_name} not detected before timeout")
        return ActionStatus.TIMEOUT

    finally:
        stop_robot()
        node.destroy_subscription(subscription)
        node.destroy_publisher(publisher)


def follow_action(
    object_name: str,
    duration_sec: float = 10.0,
    safe_distance_m: float = 1.0,
) -> ActionStatus:
    """
    object를 따라가는 action
    Vision 연동 전까지는 실제 구현하지 않고 SKIPPED 반환
    """

    print(
        f"[FOLLOW] follow {object_name} for {duration_sec} sec "
        f"with safe distance {safe_distance_m} m"
    )
    print("[FOLLOW] not implemented yet. skipped.")
    return ActionStatus.SKIPPED


def feed_action(
    object_name: str,
    item: str = "apple",
) -> ActionStatus:
    """
    Feed a pet target with the prepared food item.
    """

    print(f"[FEED] feeding {object_name} with {item}")
    return ActionStatus.SUCCESS


def report_action(message: str = "sequence completed") -> ActionStatus:
    """
    현재 상태나 결과 메시지를 출력하는 action
    """

    print(f"[REPORT] {message}")
    return ActionStatus.SUCCESS
