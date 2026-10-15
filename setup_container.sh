#!/usr/bin/env bash
# setup_container.sh
#
# One command to restore the Python side of the px4-dev container after it
# has been recreated (docker rm + docker run). Run it INSIDE the container:
#
#   bash /src/PX4-Autopilot/scripts/setup_container.sh
#
# Safe to re-run: apt and pip both skip things that are already installed.
#
# This does NOT replace Tools/setup/ubuntu.sh, which installs PX4's build
# toolchain and Gazebo Harmonic. Run that first on a brand-new container.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> apt: Gazebo Python bindings"
apt-get update
apt-get install -y python3-gz-transport13

echo "==> pip: packages from requirements.txt"
pip install -r "${SCRIPT_DIR}/requirements.txt" --break-system-packages

echo "==> Done. Quick check:"
python3 -c "from gz.transport13 import Node; from gz.msgs10.pose_v_pb2 import Pose_V; import cv2, numpy, mavsdk; print('all imports OK')"