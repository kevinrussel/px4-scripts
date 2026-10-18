#!/usr/bin/env python3
"""
gz_camera_view.py

Subscribes directly to a Gazebo camera topic and displays the live feed
with OpenCV. Uses Gazebo's own gz-transport Python bindings: no ROS,
no ros_gz_bridge, nothing related to MAVSDK/MAVLink.

Run this INSIDE the px4-dev container, while the sim is already running
in another shell in that same container. The plain `gz_x500` model has NO
camera, so launch a camera model, e.g.:

    make px4_sitl gz_x500_mono_cam
    PX4_GZ_WORLD=baylands make px4_sitl gz_x500_mono_cam

Requirements (inside the container; setup_container.sh installs them):
    apt install python3-gz-transport13
    pip install opencv-python numpy --break-system-packages

Finding your camera's topic name:
    Run `gz topic -l | grep camera` while the sim is running and pick the
    line ending in /sensor/camera/image. The world name (default, baylands...)
    and the model name (x500_mono_cam_0) both appear in it and must match.

IMPORTANT: the gz-transport callback runs on its own background thread.
OpenCV's GUI calls (imshow/waitKey) are NOT thread-safe, so the callback
only stores the latest frame; all GUI calls happen on the main thread.
"""

import sys
import threading
import time

import cv2
import numpy as np
from gz.msgs10.image_pb2 import Image
from gz.transport13 import Node
import socket
# --- Configuration ----------------------------------------------------
CAMERA_TOPIC = "/world/default/model/x500_mono_cam_0/link/camera_link/sensor/camera/image"

# Seconds to wait for the first frame before printing a hint.
NO_FRAME_WARN_S = 5.0

# --- Box detection (yellow color threshold in HSV) --------------------
# OpenCV hue runs 0-179; yellow is about 20-35. Tune these if the box is
# missed or the wrong things light up.
YELLOW_LOWER = np.array([20, 100, 100])
YELLOW_UPPER = np.array([35, 255, 255])
MIN_AREA_PX = 30   # ignore yellow blobs smaller than this many pixels

# gz-msgs PixelFormatType enum values (see gz/msgs/image.pb.h)
PIXEL_FORMAT_HANDLERS = {
    3: ("RGB_INT8", 3, cv2.COLOR_RGB2BGR),   # RGB_INT8  -> convert to BGR
    5: ("BGRA_INT8", 4, None),               # BGRA_INT8 -> handled below
    1: ("L_INT8", 1, cv2.COLOR_GRAY2BGR),    # grayscale -> convert to BGR
}

# Shared between the gz-transport callback thread (writer) and the main
# thread (reader), protected by a lock.
latest_frame = None
frame_lock = threading.Lock()


def image_callback(msg: Image) -> None:
    """Runs on gz-transport's background thread. Stores the frame only;
    no GUI calls here."""
    global latest_frame

    width = msg.width
    height = msg.height
    fmt = msg.pixel_format_type

    handler = PIXEL_FORMAT_HANDLERS.get(fmt)
    if handler is None:
        print(f"Unhandled pixel_format_type={fmt}. "
              "Add it to PIXEL_FORMAT_HANDLERS in this script.")
        return

    name, channels, conversion = handler

    buf = np.frombuffer(msg.data, dtype=np.uint8)
    expected_size = height * width * channels
    if buf.size != expected_size:
        print(f"Unexpected buffer size: got {buf.size}, "
              f"expected {expected_size} for {width}x{height}x{channels}")
        return

    frame = buf.reshape((height, width, channels))

    if channels == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    elif conversion is not None:
        frame = cv2.cvtColor(frame, conversion)

    with frame_lock:
        # .copy() so the buffer isn't reused by gz-transport while the
        # main thread is still reading it.
        latest_frame = frame.copy()


def detect_box(frame):
    """Find the yellow box in a BGR frame.

    Returns (x, y, w, h) of its bounding rectangle in pixels, or None if
    nothing yellow big enough is visible. The flight code only needs this
    one function: the box center is (x + w/2, y + h/2) and its size (w*h)
    grows as the drone gets closer.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, YELLOW_LOWER, YELLOW_UPPER)

    # Remove speckle noise.
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    biggest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(biggest) < MIN_AREA_PX:
        return None

    return cv2.boundingRect(biggest)


def main() -> None:
    node = Node()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    target_host = "127.0.0.1"
    target_port = 6969
    message = b"Hello, UDP Server!"



    subscribed = node.subscribe(Image, CAMERA_TOPIC, image_callback)
    if not subscribed:
        print(f"Failed to subscribe to '{CAMERA_TOPIC}'.")
        print("Run 'gz topic -l | grep camera' (with the sim running) to "
              "check the name/spelling.")
        sys.exit(1)

    print(f"Subscribed to {CAMERA_TOPIC}.")
    print("Press 'q' in the image window, or Ctrl+C here, to stop.")

    start = time.time()
    warned = False

    try:
        while True:
            with frame_lock:
                frame = latest_frame

            if frame is not None:
                box = detect_box(frame)

                if box is not None:
                    x, y, w, h = box
                    cv2.rectangle(frame, (x, y), (x + w, y + h),
                                  (0, 255, 0), 2)
                    cv2.putText(frame, f"box center=({x + w // 2},{y + h // 2}) "
                                f"size={w}x{h}", (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.imshow("Drone Camera", frame)
                sock.sendto(message, (target_host, target_port))
            elif not warned and time.time() - start > NO_FRAME_WARN_S:
                # Subscribing to a topic that doesn't exist still "succeeds",
                # so say something instead of failing silently.
                print(f"No frames after {NO_FRAME_WARN_S:.0f}s. Is the sim "
                      "running with a camera model (gz_x500_mono_cam), and "
                      "does CAMERA_TOPIC match `gz topic -l | grep camera`?")
                warned = True

            # All GUI calls happen here, on the main thread only.
            if cv2.waitKey(30) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()