#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
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


# Detection utilities

DETECTION_LABEL_ALIAS = {
    "dog": "dog",
    "puppy": "dog",
    "cat": "cat",
    "person": "person",

    "sports_ball": "ball",
    "sports ball": "ball",
    "ball": "ball",

    "apple": "apple",
    "bowl": "apple",
    "cup": "apple",
    "dish": "apple",
    "plate": "apple",

    "bed": "bed",
    "couch": "bed",
    "sofa": "bed",

    "chair": "chair",

    "vase": "vase",
    "plant": "vase",
    "potted_plant": "vase",
}


def normalize_detection_label(label) -> str:
    normalized = str(label or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return DETECTION_LABEL_ALIAS.get(normalized, normalized)


def extract_detection_list(data: str) -> list[dict]:
    """
    Supported /vision/detections formats:

    1) [{"label":"apple"},{"label":"dog"}]
    2) {"detections":[{"label":"apple"}]}
    3) {"objects":[{"label":"apple"}]}
    4) {"label":"apple"}
    5) ["apple", "dog"]
    """

    try:
        payload = json.loads(data)
    except Exception:
        return []

    if isinstance(payload, list):
        detections = payload
    elif isinstance(payload, dict):
        if "label" in payload:
            detections = [payload]
        else:
            detections = (
                payload.get("detections")
                or payload.get("filtered_detections")
                or payload.get("objects")
                or []
            )
    else:
        detections = []

    normalized_detections = []

    for detection in detections:
        if isinstance(detection, dict):
            normalized_detections.append(detection)
        elif isinstance(detection, str):
            normalized_detections.append({"label": detection})

    return normalized_detections


def detection_matches_target(detection: dict, object_name: str) -> bool:
    label = normalize_detection_label(detection.get("label"))
    target = normalize_detection_label(object_name)
    return bool(label) and label == target


# Basic actions


def wait_action(duration_sec: float = 3.0) -> ActionStatus:
    duration_sec = max(float(duration_sec), 0.0)
    print(f"[WAIT] waiting for {duration_sec} sec")
    time.sleep(duration_sec)
    return ActionStatus.SUCCESS


def report_action(message: str = "sequence completed") -> ActionStatus:
    print(f"[REPORT] {message}")
    return ActionStatus.SUCCESS


def feed_action(
    object_name: str,
    item: str = "apple",
) -> ActionStatus:
    """
    현재 manipulation은 구현하지 않았으므로 task-level log로 처리.
    """
    print(f"[FEED] feeding {object_name} with {item}")
    return ActionStatus.SUCCESS


# Odom-based observe/search

def _publish_stop(publisher):
    try:
        from geometry_msgs.msg import Twist
        publisher.publish(Twist())
    except Exception:
        pass


def _spin_in_place(
    node,
    duration_sec: float,
    angular_speed: float = 0.35,
    cmd_vel_topic: str = "/cmd_vel",
) -> ActionStatus:
    """
    Odom demo용 제자리 회전.
    """
    import rclpy
    from geometry_msgs.msg import Twist

    duration_sec = max(float(duration_sec), 0.0)

    publisher = node.create_publisher(Twist, cmd_vel_topic, 10)
    deadline = time.monotonic() + duration_sec

    try:
        while rclpy.ok() and time.monotonic() < deadline:
            cmd = Twist()
            cmd.angular.z = float(angular_speed)
            publisher.publish(cmd)

            rclpy.spin_once(node, timeout_sec=0.05)
            time.sleep(0.05)

        _publish_stop(publisher)
        return ActionStatus.SUCCESS

    finally:
        _publish_stop(publisher)
        node.destroy_publisher(publisher)


def observe_action(
    object_name: str,
    duration_sec: float = 5.0,
    node=None,
    angular_speed: float = 0.35,
    cmd_vel_topic: str = "/cmd_vel",
) -> ActionStatus:
    """
    Odom demo용 observe.
    object_name_zone 좌표를 바라보도록 제자리 회전한 뒤 관찰한다.
    """

    import os
    import yaml
    import math
    import time
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry

    duration_sec = max(float(duration_sec), 0.0)
    print(f"[OBSERVE] observing {object_name} for {duration_sec} sec")

    if node is None:
        time.sleep(duration_sec)
        print(f"[OBSERVE] {object_name} observation finished")
        return ActionStatus.SUCCESS

    def normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def yaw_from_quaternion(q) -> float:
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def load_target(obj_name: str):
        target_name = f"{obj_name}_zone"

        candidate_paths = [
            os.path.join(os.getcwd(), "config", "target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/config/target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/install/pet_robot_pkg/share/pet_robot_pkg/config/target.yaml"),
        ]

        for path in candidate_paths:
            if not os.path.exists(path):
                continue

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data and "targets" in data and target_name in data["targets"]:
                target = data["targets"][target_name]
                return (
                    float(target["x"]),
                    float(target["y"]),
                    path,
                )

        raise FileNotFoundError(f"{target_name} not found in target.yaml")

    try:
        target_x, target_y, target_path = load_target(object_name)
    except Exception as e:
        print(f"[OBSERVE] failed to load {object_name}_zone: {e}")
        time.sleep(duration_sec)
        print(f"[OBSERVE] {object_name} observation finished")
        return ActionStatus.SUCCESS

    current = {
        "ready": False,
        "x": 0.0,
        "y": 0.0,
        "yaw": 0.0,
    }

    def odom_callback(msg: Odometry):
        current["x"] = msg.pose.pose.position.x
        current["y"] = msg.pose.pose.position.y
        current["yaw"] = yaw_from_quaternion(msg.pose.pose.orientation)
        current["ready"] = True

    cmd_pub = node.create_publisher(Twist, cmd_vel_topic, 10)
    odom_sub = node.create_subscription(Odometry, "/odom", odom_callback, 10)

    def stop_robot():
        cmd_pub.publish(Twist())

    try:
        wait_deadline = time.monotonic() + 5.0

        while rclpy.ok() and not current["ready"] and time.monotonic() < wait_deadline:
            rclpy.spin_once(node, timeout_sec=0.1)

        if not current["ready"]:
            print("[OBSERVE] /odom not received. fallback to wait.")
            time.sleep(duration_sec)
            print(f"[OBSERVE] {object_name} observation finished")
            return ActionStatus.SUCCESS

        print(
            f"[OBSERVE] turning toward {object_name}_zone "
            f"target=({target_x:.2f}, {target_y:.2f}), yaml={target_path}"
        )

        turn_deadline = time.monotonic() + 10.0

        while rclpy.ok() and time.monotonic() < turn_deadline:
            dx = target_x - current["x"]
            dy = target_y - current["y"]

            target_heading = math.atan2(dy, dx)
            yaw_error = normalize_angle(target_heading - current["yaw"])

            if abs(yaw_error) < 0.10:
                stop_robot()
                print(f"[OBSERVE] facing {object_name}, yaw_error={yaw_error:.2f}")
                break

            cmd = Twist()
            cmd.angular.z = clamp(1.0 * yaw_error, -0.45, 0.45)
            cmd_pub.publish(cmd)

            rclpy.spin_once(node, timeout_sec=0.1)
            time.sleep(0.05)

        stop_robot()

        observe_deadline = time.monotonic() + duration_sec
        while rclpy.ok() and time.monotonic() < observe_deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            time.sleep(0.05)

        print(f"[OBSERVE] {object_name} observation finished")
        return ActionStatus.SUCCESS

    finally:
        stop_robot()
        node.destroy_subscription(odom_sub)
        node.destroy_publisher(cmd_pub)


def search_action(
    node,
    object_name: str,
    timeout_sec: float = 45.0,
    scan_duration_sec: float = 4.0,
    angular_speed: float = 0.35,
    detection_topic: str = "/vision/detections",
    cmd_vel_topic: str = "/cmd_vel",
    patrol_objects=None,
    navigation_timeout_sec: float = 20.0,
    goal_tolerance_m: float = 0.35,
) -> ActionStatus:
    """
    Odom demo용 search.

    Nav2 patrol 이동을 완전히 제거했다.
    /vision/detections에서 target label을 확인하고,
    안 보이면 제자리 회전하면서 timeout까지 계속 확인한다.
    """

    import rclpy
    from geometry_msgs.msg import Twist
    from std_msgs.msg import String

    found = {"value": False}
    last_labels = {"value": []}

    def detection_callback(msg):
        detections = extract_detection_list(msg.data)
        labels = [
            normalize_detection_label(d.get("label"))
            for d in detections
            if isinstance(d, dict)
        ]
        labels = [label for label in labels if label]
        last_labels["value"] = labels

        for detection in detections:
            if detection_matches_target(detection, object_name):
                found["value"] = True
                return

    publisher = node.create_publisher(Twist, cmd_vel_topic, 10)
    subscription = node.create_subscription(String, detection_topic, detection_callback, 10)

    deadline = time.monotonic() + max(float(timeout_sec), 0.0)

    print(f"[SEARCH] searching for {object_name} using odom/in-place scan")

    try:
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)

            if found["value"]:
                _publish_stop(publisher)
                print(f"[SEARCH] {object_name} detected")
                return ActionStatus.SUCCESS

            cmd = Twist()
            cmd.angular.z = float(angular_speed)
            publisher.publish(cmd)

            time.sleep(0.05)

        _publish_stop(publisher)
        print(
            f"[SEARCH] {object_name} not detected before timeout. "
            f"last_labels={last_labels['value']}"
        )
        return ActionStatus.TIMEOUT

    finally:
        _publish_stop(publisher)
        node.destroy_subscription(subscription)
        node.destroy_publisher(publisher)


# Odom-based approach

def approach_action(
    node,
    object_name: str,
    timeout_sec: float = 60.0,
    goal_tolerance_m: float = 0.35,
    retry_count: int = 0,
):
    node.get_logger().info(
        f"[APPROACH] using direct odom approach for {object_name}"
    )

    return direct_odom_approach_action(
        node=node,
        object_name=object_name,
        timeout_sec=timeout_sec,
        goal_tolerance_m=goal_tolerance_m,
    )


def direct_odom_approach_action(
    node,
    object_name: str,
    timeout_sec: float = 60.0,
    goal_tolerance_m: float = 0.35,
):
    import yaml
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry

    def normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def yaw_from_quaternion(q) -> float:
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def load_target_from_yaml(obj_name: str):
        target_name = f"{obj_name}_zone"

        candidate_paths = [
            os.path.join(os.getcwd(), "config", "target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/config/target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/src/robotics-project/config/target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/install/pet_robot_pkg/share/pet_robot_pkg/config/target.yaml"),
        ]

        for path in candidate_paths:
            if not os.path.exists(path):
                continue

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "targets" not in data:
                continue

            if target_name not in data["targets"]:
                continue

            target = data["targets"][target_name]
            return (
                target_name,
                float(target["x"]),
                float(target["y"]),
                float(target.get("yaw", 0.0)),
                path,
            )

        raise FileNotFoundError(
            f"{target_name} not found in target.yaml. Checked: "
            + ", ".join(candidate_paths)
        )

    try:
        target_name, target_x, target_y, _, target_path = load_target_from_yaml(object_name)
    except Exception as e:
        node.get_logger().error(f"[DIRECT_APPROACH] failed to load target: {e}")
        return ActionStatus.FAILED

    current = {
        "ready": False,
        "x": 0.0,
        "y": 0.0,
        "yaw": 0.0,
    }

    def odom_callback(msg: Odometry):
        current["x"] = msg.pose.pose.position.x
        current["y"] = msg.pose.pose.position.y
        current["yaw"] = yaw_from_quaternion(msg.pose.pose.orientation)
        current["ready"] = True

    cmd_pub = node.create_publisher(Twist, "/cmd_vel", 10)
    odom_sub = node.create_subscription(Odometry, "/odom", odom_callback, 10)

    def publish_stop():
        cmd_pub.publish(Twist())

    node.get_logger().info(
        f"[DIRECT_APPROACH] {object_name} -> {target_name}, "
        f"target=({target_x:.2f}, {target_y:.2f}), "
        f"tolerance={goal_tolerance_m:.2f}, yaml={target_path}"
    )

    deadline = time.monotonic() + float(timeout_sec)

    try:
        time.sleep(0.5)

        while rclpy.ok() and not current["ready"] and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)

        if not current["ready"]:
            node.get_logger().error("[DIRECT_APPROACH] /odom not received")
            publish_stop()
            return ActionStatus.TIMEOUT

        last_log_time = 0.0

        while rclpy.ok() and time.monotonic() < deadline:
            dx = target_x - current["x"]
            dy = target_y - current["y"]
            distance = math.hypot(dx, dy)

            target_heading = math.atan2(dy, dx)
            yaw_error = normalize_angle(target_heading - current["yaw"])

            if distance <= goal_tolerance_m:
                publish_stop()
                node.get_logger().info(
                    f"[DIRECT_APPROACH] {object_name} SUCCESS "
                    f"distance={distance:.2f} <= {goal_tolerance_m:.2f}"
                )
                return ActionStatus.SUCCESS

            cmd = Twist()

            if abs(yaw_error) > 0.30:
                cmd.linear.x = 0.0
                cmd.angular.z = clamp(1.2 * yaw_error, -0.45, 0.45)
            else:
                cmd.linear.x = clamp(0.35 * distance, 0.08, 0.18)
                cmd.angular.z = clamp(0.8 * yaw_error, -0.25, 0.25)

            cmd_pub.publish(cmd)

            now = time.monotonic()
            if now - last_log_time >= 0.5:
                node.get_logger().info(
                    f"[DIRECT_APPROACH] current=({current['x']:.2f}, {current['y']:.2f}, yaw={current['yaw']:.2f}) "
                    f"target=({target_x:.2f}, {target_y:.2f}) "
                    f"heading={target_heading:.2f} yaw_error={yaw_error:.2f} "
                    f"dist={distance:.2f} cmd=({cmd.linear.x:.2f}, {cmd.angular.z:.2f})"
                )
                last_log_time = now

            rclpy.spin_once(node, timeout_sec=0.1)
            time.sleep(0.05)

        publish_stop()
        node.get_logger().warn(f"[DIRECT_APPROACH] {object_name} TIMEOUT")
        return ActionStatus.TIMEOUT

    finally:
        publish_stop()
        node.destroy_subscription(odom_sub)
        node.destroy_publisher(cmd_pub)

