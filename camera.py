#!/usr/bin/env python3
"""
camera.py

Subscribes to a Gazebo camera topic and displays the live feed with
OpenCV. Uses Gazebo's own gz-transport Python bindings directly — no
ROS involved.

IMPORTANT: the gz-transport callback runs on its own background thread.
OpenCV's GUI calls (imshow/waitKey) are NOT thread-safe, so the callback
only stores the latest frame — all cv2.imshow()/cv2.waitKey() calls
happen in the main thread's loop instead. Mixing the two across threads
is what causes a window to show one frame and then freeze.
"""

import sys
import threading

import cv2
import numpy as np
from gz.msgs10.image_pb2 import Image
from gz.transport13 import Node

# --- Configuration ----------------------------------------------------
# Update this to match your current world + model. Confirm with:
#   gz topic -l | grep camera
CAMERA_TOPIC = "/world/baylands/model/x500_mono_cam_0/link/camera_link/sensor/camera/image"

# gz-msgs PixelFormatType enum values (see gz/msgs/image.pb.h)
PIXEL_FORMAT_HANDLERS = {
    3: ("RGB_INT8", 3, cv2.COLOR_RGB2BGR),   # RGB_INT8  -> convert to BGR
    5: ("BGRA_INT8", 4, None),               # BGRA_INT8 -> handled below
    1: ("L_INT8", 1, cv2.COLOR_GRAY2BGR),    # grayscale -> convert to BGR
}

# Shared state between the gz-transport callback thread and the main
# (display) thread. Protected by a lock since it's written from one
# thread and read from another.
latest_frame = None
frame_lock = threading.Lock()


def image_callback(msg: Image) -> None:
    """Runs on gz-transport's background thread. Stores the frame only —
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
        # .copy() so the buffer isn't reused/overwritten by gz-transport
        # while the main thread is still reading it.
        latest_frame = frame.copy()


def main() -> None:
    node = Node()

    subscribed = node.subscribe(Image, CAMERA_TOPIC, image_callback)
    if not subscribed:
        print(f"Failed to subscribe to '{CAMERA_TOPIC}'.")
        print("Run 'gz topic -l | grep camera' to check the exact topic name.")
        sys.exit(1)

    print(f"Subscribed to {CAMERA_TOPIC}.")
    print("Press 'q' in the image window, or Ctrl+C here, to stop.")

    try:
        while True:
            with frame_lock:
                frame = latest_frame

            if frame is not None:
                cv2.imshow("Drone Camera", frame)

            # All GUI calls happen here, on the main thread only.
            key = cv2.waitKey(30) & 0xFF
            if key == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
