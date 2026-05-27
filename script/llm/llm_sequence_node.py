#!/usr/bin/env python3

import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from llm_sequence_generator import call_llm_api


class LLMSequenceNode(Node):
    def __init__(self):
        super().__init__("llm_sequence_node")

        self.detected_labels = []

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

        self.timer = self.create_timer(5.0, self.generate_sequence)

        self.user_text = "강아지가 침대 근처에 있는지 확인해줘"

        self.get_logger().info("LLM sequence node started.")

    def detection_callback(self, msg):
        try:
            detections = json.loads(msg.data)

            labels = []

            for det in detections:
                if "label" in det:
                    labels.append(det["label"])

            self.detected_labels = labels

            self.get_logger().info(
                f"Detected labels: {self.detected_labels}"
            )

        except Exception as e:
            self.get_logger().error(
                f"Detection parse error: {e}"
            )

    def generate_sequence(self):
        if not self.detected_labels:
            self.get_logger().info("No detected labels yet.")
            return

        try:
            result = call_llm_api(self.user_text, self.detected_labels)

            msg = String()
            msg.data = json.dumps(result, ensure_ascii=False)

            self.sequence_pub.publish(msg)

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