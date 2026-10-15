#!/usr/bin/env python3
"""
gz_camera_view.py

Subscribes directly to a Gazebo camera topic and displays the live feed
with OpenCV. Uses Gazebo's own gz-transport Python bindings — no ROS,
no ros_gz_bridge, nothing related to MAVSDK/MAVLink.

Run this INSIDE the px4-dev container, while `make px4_sitl gz_x500`
(or similar) is already running in another shell in that same container.

Requirements (inside the container):
    sudo apt install python3-gz-transport13   # if not already present
    pip install opencv-python numpy --break-system-packages

Finding your camera's topic name:
    Run `gz topic -l` while the sim is running and look for something
    ending in .../image. Confirm its type with:
        gz topic -i -t <topic_name>
    It should say "gz.msgs.Image". Paste that exact name into
    CAMERA_TOPIC below.
"""

import sys

import cv2
import numpy as np
from gz.msgs10.image_pb2 import Image
from gz.transport13 import Node

# --- Configuration ----------------------------------------------------
# Replace this with your actual camera topic (see docstring above for
# how to find it with `gz topic -l`).
CAMERA_TOPIC = "/world/default/model/x500_0/link/camera_link/sensor/camera/image"

# gz-msgs PixelFormatType enum values (see gz/msgs/image.pb.h)
PIXEL_FORMAT_HANDLERS = {
    3: ("RGB_INT8", 3, cv2.COLOR_RGB2BGR),   # RGB_INT8  -> convert to BGR
    5: ("BGRA_INT8", 4, None),               # BGRA_INT8 -> already BGR-ish
    1: ("L_INT8", 1, cv2.COLOR_GRAY2BGR),    # grayscale -> convert to BGR
}


def image_callback(msg: Image) -> None:
    """Called by gz-transport every time a new frame arrives."""
    width = msg.width
    height = msg.height
    fmt = msg.pixel_format_type

    handler = PIXEL_FORMAT_HANDLERS.get(fmt)
    if handler is None:
        print(f"Unhandled pixel_format_type={fmt}. "
              "Add it to PIXEL_FORMAT_HANDLERS in this script.")
        return

    name, channels, conversion = handler

    frame = np.frombuffer(msg.data, dtype=np.uint8)
    expected_size = height * width * channels
    if frame.size != expected_size:
        print(f"Unexpected buffer size: got {frame.size}, "
              f"expected {expected_size} for {width}x{height}x{channels}")
        return

    frame = frame.reshape((height, width, channels))

    if channels == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    elif conversion is not None:
        frame = cv2.cvtColor(frame, conversion)

    cv2.imshow("Drone Camera", frame)
    cv2.waitKey(1)


def main() -> None:
    node = Node()

    subscribed = node.subscribe(Image, CAMERA_TOPIC, image_callback)
    if not subscribed:
        print(f"Failed to subscribe to '{CAMERA_TOPIC}'.")
        print("Run 'gz topic -l' (with the sim running) to list available "
              "topics and check the name/spelling.")
        sys.exit(1)

    print(f"Subscribed to {CAMERA_TOPIC}. Close the image window or press "
          "Ctrl+C in this terminal to stop.")

    try:
        while True:
            # gz-transport delivers messages on its own background thread;
            # this loop just keeps the process (and OpenCV's window) alive.
            if cv2.waitKey(1) == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()