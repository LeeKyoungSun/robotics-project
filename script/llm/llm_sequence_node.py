#!/usr/bin/env python3

import json
from collections import Counter

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    from .llm_sequence_generator import (
        call_llm_api,
        normalize_label,
    )
except ImportError:
    from llm_sequence_generator import (
        call_llm_api,
        normalize_label,
    )


def build_dynamic_user_text(labels):
    label_set = set(labels)

    if "potted_plant" in label_set:
        return "화분은 접근하지 말고 관찰한 뒤 결과를 보고해줘"

    if "bowl" in label_set and "dog" in label_set:
        return "강아지 급식 시나리오를 수행해줘"

    if "ball" in label_set and "dog" in label_set:
        return "강아지 놀이 시나리오를 수행해줘"

    if {"bowl", "bed", "chair"}.issubset(label_set):
        return "그릇, 침대, 의자를 순서대로 확인해줘"

    if "dog" in label_set:
        return "강아지 상태를 관찰하고 결과를 보고해줘"

    if "cat" in label_set:
        return "고양이 상태를 관찰하고 결과를 보고해줘"

    if "bed" in label_set:
        return "침대 쪽을 확인하고 결과를 보고해줘"

    if "chair" in label_set:
        return "의자 쪽을 확인하고 결과를 보고해줘"

    return "유효한 target이 보이지 않으면 잠시 기다린 뒤 결과를 보고해줘"


def parse_user_request(data: str) -> str:
    text = data.strip()
    if not text:
        return ""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(payload, dict):
        value = payload.get("text") or payload.get("request") or payload.get("user_text")
        return str(value).strip() if value else ""

    if isinstance(payload, str):
        return payload.strip()

    return ""


class LLMSequenceNode(Node):
    def __init__(self):
        super().__init__("llm_sequence_node")

        self.declare_parameter("detection_topic", "/vision/detections")
        self.declare_parameter("user_request_topic", "/llm/user_request")
        self.declare_parameter("action_sequence_topic", "/vision/action_sequence")
        self.declare_parameter("timer_period_sec", 5.0)
        self.declare_parameter("require_user_request", False)

        self.detected_labels = []
        self.last_valid_labels = []
        self.last_sequence_key = None
        self.latest_user_request = ""
        self.user_request_id = 0
        self.consumed_user_request_id = 0
        self.require_user_request = self.get_bool_parameter("require_user_request")

        self.label_history = []

        self.detection_sub = self.create_subscription(
            String,
            str(self.get_parameter("detection_topic").value),
            self.detection_callback,
            10,
        )

        self.user_request_sub = self.create_subscription(
            String,
            str(self.get_parameter("user_request_topic").value),
            self.user_request_callback,
            10,
        )

        self.sequence_pub = self.create_publisher(
            String,
            str(self.get_parameter("action_sequence_topic").value),
            10,
        )

        timer_period_sec = max(
            0.5,
            float(self.get_parameter("timer_period_sec").value),
        )
        self.timer = self.create_timer(timer_period_sec, self.generate_sequence)

        self.get_logger().info(
            "LLM sequence node started. "
            f"user_request_topic={self.get_parameter('user_request_topic').value}"
        )

    def get_bool_parameter(self, name):
        value = self.get_parameter(name).value

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return bool(value)

    def user_request_callback(self, msg):
        user_request = parse_user_request(msg.data)
        if not user_request:
            self.get_logger().warn("Ignored empty user request.")
            return

        self.latest_user_request = user_request
        self.user_request_id += 1
        self.get_logger().info(f"User request received: {user_request}")

    def detection_callback(self, msg):
        try:
            detections = json.loads(msg.data)

            if isinstance(detections, dict):
                detections = (
                    detections.get("detections")
                    or detections.get("filtered_detections")
                    or detections.get("objects")
                    or []
                )

            if not isinstance(detections, list):
                self.get_logger().warn(
                    "Detection payload must be a list or a dict containing detections."
                )
                return

            labels = []

            for det in detections:
                if not isinstance(det, dict) or "label" not in det:
                    continue

                normalized = normalize_label(det["label"])

                if normalized and normalized not in labels:
                    labels.append(normalized)

            if labels:
                self.last_valid_labels = labels
            else:
                labels = self.last_valid_labels

            self.label_history.extend(labels)

            if len(self.label_history) > 10:
                self.label_history.pop(0)

            counter = Counter(self.label_history)

            self.detected_labels = [
                label
                for label, count in counter.items()
                if count >= 3
            ]

            self.get_logger().info(f"Detected labels: {self.detected_labels}")

        except Exception as e:
            self.get_logger().error(f"Detection parse error: {e}")

    def select_user_text(self):
        if self.user_request_id > self.consumed_user_request_id:
            return self.latest_user_request, True

        if self.require_user_request:
            return "", False

        if self.detected_labels:
            return build_dynamic_user_text(self.detected_labels), False

        return "", False

    def generate_sequence(self):
        user_text, from_user = self.select_user_text()

        if not user_text:
            self.get_logger().info("No user request or valid labels yet. Skip LLM call.")
            return

        detected_labels = list(self.detected_labels)

        if from_user:
            sequence_key = (
                "user",
                self.user_request_id,
                tuple(sorted(detected_labels)),
            )
        else:
            sequence_key = (
                "auto",
                tuple(sorted(detected_labels)),
            )

        if sequence_key == self.last_sequence_key:
            return

        self.last_sequence_key = sequence_key

        try:
            result = call_llm_api(user_text, detected_labels)

            msg = String()
            msg.data = json.dumps(result, ensure_ascii=False)
            self.sequence_pub.publish(msg)

            if from_user:
                self.consumed_user_request_id = self.user_request_id

            self.get_logger().info(f"User text: {user_text}")
            self.get_logger().info(f"Published action sequence: {msg.data}")

        except Exception as e:
            self.get_logger().error(f"LLM API error: {e}")


def main(args=None):
    rclpy.init(args=args)

    node = LLMSequenceNode()

    rclpy.spin(node)

    node.destroy_node()

    rclpy.shutdown()


if __name__ == "__main__":
    main()
