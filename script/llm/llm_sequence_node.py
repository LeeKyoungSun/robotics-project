#!/usr/bin/env python3

import json
from collections import Counter

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from llm_sequence_generator import (
    call_llm_api,
    normalize_label,
)


def build_dynamic_user_text(labels):
    label_set = set(labels)

    if "potted_plant" in label_set:
        return (
            "화분은 안전상 접근하지 말고 "
            "관찰만 수행한 뒤 결과를 보고해줘"
        )

    if "bowl" in label_set and "dog" in label_set:
        return "강아지 급식 시나리오를 수행해줘"

    if "ball" in label_set and "dog" in label_set:
        return "강아지 놀이 시나리오를 수행해줘"

    if {"bowl", "bed", "chair"}.issubset(label_set):
        return (
            "그릇, 침대, 의자를 순서대로 확인하는 "
            "static multi target 시나리오를 수행해줘"
        )

    if "dog" in label_set:
        return "강아지 상태를 관찰하고 결과를 보고해줘"

    if "cat" in label_set:
        return "고양이 상태를 관찰하고 결과를 보고해줘"

    if "bed" in label_set:
        return "침대 쪽을 확인하고 결과를 보고해줘"

    if "chair" in label_set:
        return "의자 쪽을 확인하고 결과를 보고해줘"

    return (
        "유효한 target이 보이지 않으면 "
        "잠시 기다린 뒤 결과를 보고해줘"
    )


class LLMSequenceNode(Node):
    def __init__(self):
        super().__init__("llm_sequence_node")

        self.detected_labels = []
        self.last_valid_labels = []
        self.last_sequence_key = None

        # detection 안정화용 history
        self.label_history = []

        self.detection_sub = self.create_subscription(
            String,
            "/vision/detections",
            self.detection_callback,
            10
        )

        self.sequence_pub = self.create_publisher(
            String,
            "/vision/action_sequence",
            10
        )

        self.timer = self.create_timer(
            5.0,
            self.generate_sequence
        )

        self.get_logger().info(
            "LLM sequence node started."
        )

    def detection_callback(self, msg):
        try:
            detections = json.loads(msg.data)

            labels = []

            for det in detections:
                if "label" not in det:
                    continue

                normalized = normalize_label(
                    det["label"]
                )

                if normalized and normalized not in labels:
                    labels.append(normalized)

            # detection memory
            if labels:
                self.last_valid_labels = labels
            else:
                labels = self.last_valid_labels

            # voting filter
            self.label_history.extend(labels)

            if len(self.label_history) > 10:
                self.label_history.pop(0)

            counter = Counter(self.label_history)

            stable_labels = [
                label
                for label, count in counter.items()
                if count >= 3
            ]

            self.detected_labels = stable_labels

            self.get_logger().info(
                f"Detected labels: "
                f"{self.detected_labels}"
            )

        except Exception as e:
            self.get_logger().error(
                f"Detection parse error: {e}"
            )

    def generate_sequence(self):
        if not self.detected_labels:
            self.get_logger().info(
                "No valid labels yet. Skip LLM call."
            )
            return

        # duplicate blocking
        sequence_key = tuple(
            sorted(self.detected_labels)
        )

        if sequence_key == self.last_sequence_key:
            return

        self.last_sequence_key = sequence_key

        try:
            user_text = build_dynamic_user_text(
                self.detected_labels
            )

            result = call_llm_api(
                user_text,
                self.detected_labels
            )

            msg = String()

            msg.data = json.dumps(
                result,
                ensure_ascii=False
            )

            self.sequence_pub.publish(msg)

            self.get_logger().info(
                f"User text: {user_text}"
            )

            self.get_logger().info(
                f"Published action sequence: "
                f"{msg.data}"
            )

        except Exception as e:
            self.get_logger().error(
                f"LLM API error: {e}"
            )


def main(args=None):
    rclpy.init(args=args)

    node = LLMSequenceNode()

    rclpy.spin(node)

    node.destroy_node()

    rclpy.shutdown()


if __name__ == "__main__":
    main()