#!/usr/bin/env python3

import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class InitialScanRotator(Node):
    def __init__(self):
        super().__init__("initial_scan_rotator")

        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("angular_speed", 0.35)
        self.declare_parameter("duration_sec", 18.0)
        self.declare_parameter("start_delay_sec", 3.0)
        self.declare_parameter("publish_rate_hz", 10.0)

        self.cmd_vel_topic = str(self.get_parameter("cmd_vel_topic").value)
        self.angular_speed = float(self.get_parameter("angular_speed").value)
        self.duration_sec = max(0.0, float(self.get_parameter("duration_sec").value))
        self.start_delay_sec = max(
            0.0,
            float(self.get_parameter("start_delay_sec").value),
        )
        publish_rate_hz = max(
            1.0,
            float(self.get_parameter("publish_rate_hz").value),
        )

        self.publisher = self.create_publisher(Twist, self.cmd_vel_topic, 10)
        self.start_time = time.monotonic() + self.start_delay_sec
        self.stop_publish_count = 0
        self.timer = self.create_timer(1.0 / publish_rate_hz, self.tick)

        self.get_logger().info(
            "[INITIAL_SCAN] waiting "
            f"{self.start_delay_sec:.1f}s, then rotating for "
            f"{self.duration_sec:.1f}s at angular.z={self.angular_speed:.2f}"
        )

    def tick(self):
        now = time.monotonic()
        command = Twist()

        if now < self.start_time:
            return

        elapsed = now - self.start_time
        if elapsed < self.duration_sec:
            command.angular.z = self.angular_speed
            self.publisher.publish(command)
            return

        self.publisher.publish(command)
        self.stop_publish_count += 1

        if self.stop_publish_count == 1:
            self.get_logger().info("[INITIAL_SCAN] complete; stopping robot")

        if self.stop_publish_count >= 5:
            rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = InitialScanRotator()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            zero = Twist()
            node.publisher.publish(zero)
            rclpy.shutdown()
        node.destroy_node()


if __name__ == "__main__":
    main()
