#!/usr/bin/env python3

from __future__ import annotations

import json
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


DEFAULT_TASK = "\uc694\uccad\ud558\uc2e0 \uc791\uc5c5\uc744"
EMPTY_MESSAGE = "agent: \ub0b4\uc6a9\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694."
FLOW_LABEL = "\uc2e4\ud589 \ud750\ub984"


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def summarize_request(user_text: str) -> str:
    summary = (user_text or "").strip()
    summary = summary.rstrip(".!? ")

    for suffix in (
        "\ud574\uc8fc\uc138\uc694",
        "\ud574 \uc8fc\uc138\uc694",
        "\ud574\uc918",
        "\ud574 \uc918",
        "\uc8fc\uc138\uc694",
        "\uc918",
    ):
        if summary.endswith(suffix):
            summary = summary[: -len(suffix)].strip()
            break

    return summary or DEFAULT_TASK


def build_ack(user_text: str) -> str:
    return f"agent: \ub124, {summarize_request(user_text)} \ud558\uaca0\uc2b5\ub2c8\ub2e4."


class AgentConsole(Node):
    def __init__(self):
        super().__init__("agent_console")

        self.declare_parameter("user_request_topic", "/llm/user_request")
        self.declare_parameter("agent_response_topic", "/llm/agent_response")
        self.declare_parameter("show_auto_responses", False)

        self.show_auto_responses = parse_bool(
            self.get_parameter("show_auto_responses").value
        )

        self.user_request_pub = self.create_publisher(
            String,
            str(self.get_parameter("user_request_topic").value),
            10,
        )
        self.agent_response_sub = self.create_subscription(
            String,
            str(self.get_parameter("agent_response_topic").value),
            self.agent_response_callback,
            10,
        )

        self.input_thread = threading.Thread(
            target=self.input_loop,
            daemon=True,
        )
        self.input_thread.start()

    def input_loop(self):
        while rclpy.ok():
            try:
                user_text = input("user: ").strip()
            except EOFError:
                return
            except KeyboardInterrupt:
                rclpy.shutdown()
                return

            if not user_text:
                print(EMPTY_MESSAGE, flush=True)
                continue

            msg = String()
            msg.data = json.dumps({"text": user_text}, ensure_ascii=False)
            self.user_request_pub.publish(msg)

            print(build_ack(user_text), flush=True)

    def agent_response_callback(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            print(f"agent: {msg.data}", flush=True)
            return

        if not isinstance(payload, dict):
            return

        if not payload.get("from_user") and not self.show_auto_responses:
            return

        flow = str(payload.get("flow") or "").strip()
        if flow:
            print(f"agent: {FLOW_LABEL}: {flow}", flush=True)


def main(args=None):
    rclpy.init(args=args)
    node = AgentConsole()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
