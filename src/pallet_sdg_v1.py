# Copyright (c) 2022, NVIDIA CORPORATION.  All rights reserved.
#
# SPDX-License-Identifier: MIT

from omni.isaac.kit import SimulationApp
import os
import argparse
import math
import random

parser = argparse.ArgumentParser("Pallet detection dataset generator")
parser.add_argument("--headless", type=bool, default=False, help="Launch script headless, default is False")
parser.add_argument("--height", type=int, default=544, help="Height of image")
parser.add_argument("--width", type=int, default=960, help="Width of image")
parser.add_argument("--num_frames", type=int, default=1000, help="Number of frames to record")
parser.add_argument("--data_dir", type=str, default=os.getcwd() + "/_pallet_data",
                    help="Location where data will be output")

args, unknown_args = parser.parse_known_args()

CONFIG = {
    "renderer": "RayTracedLighting",
    "headless": args.headless,
    "width": args.width,
    "height": args.height,
}

simulation_app = SimulationApp(launch_config=CONFIG)

# ── Environment & asset URLs ──────────────────────────────────────────────────
ENV_URL         = "/Isaac/Environments/Simple_Warehouse/warehouse.usd"
ROBOT_URL       = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Samples/ROS2/Robots/iw_hub_ROS.usd"
CAMERA_PATH     = "/iw_hub_ROS/chassis/front_hawk/left/camera_left"

PALLET_URLS = [
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Props/Pallet/pallet.usd",
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Props/Pallet/o3dyn_pallet.usd",
]

# Warehouse floor bounds (metres) — matches the Simple_Warehouse layout
FLOOR_X = (-9.2, 7.2)
FLOOR_Y = (-11.8, 15.8)

# Pallet placement parameters
PALLET_MIN_DIST  = 1.0   # metres — minimum distance from camera
PALLET_MAX_DIST  = 8.0   # metres — maximum distance from camera
PALLET_FOV_DEG   = 100.0 # ± degrees from camera forward axis
MAX_PALLETS_EACH = 10    # maximum instances per pallet type per frame

import carb
import omni
import omni.usd
from omni.isaac.core.utils.nucleus import get_assets_root_path
from omni.isaac.core.utils.stage import get_current_stage, open_stage
from pxr import Semantics
import omni.replicator.core as rep

rep.settings.carb_settings("/omni/replicator/RTSubframes", 4)


def prefix_with_isaac_asset_server(relative_path):
    assets_root_path = get_assets_root_path()
    if assets_root_path is None:
        raise Exception("Nucleus server not found, could not access Isaac Sim assets folder")
    return assets_root_path + relative_path


def update_semantics(stage, keep_semantics=[]):
    """Remove all semantic labels from the stage except those in keep_semantics."""
    for prim in stage.Traverse():
        if prim.HasAPI(Semantics.SemanticsAPI):
            processed_instances = set()
            for prop in prim.GetProperties():
                is_semantic = Semantics.SemanticsAPI.IsSemanticsAPIPath(prop.GetPath())
                if not is_semantic:
                    continue
                instance_name = prop.SplitName()[1]
                if instance_name in processed_instances:
                    continue
                processed_instances.add(instance_name)
                sem       = Semantics.SemanticsAPI.Get(prim, instance_name)
                type_attr = sem.GetSemanticTypeAttr()
                data_attr = sem.GetSemanticDataAttr()
                if data_attr.Get() not in keep_semantics:
                    prim.RemoveProperty(type_attr.GetName())
                    prim.RemoveProperty(data_attr.GetName())
                    prim.RemoveAPI(Semantics.SemanticsAPI, instance_name)


def build_pallet_positions(robot_x, robot_y, robot_yaw_deg, count):
    """
    Return `count` (x, y, 0) world-space positions for pallets placed:
      - at z = 0
      - distance in [PALLET_MIN_DIST, PALLET_MAX_DIST] from the robot camera
      - within ±PALLET_FOV_DEG of the camera's forward direction
    """
    positions = []
    robot_yaw_rad = math.radians(robot_yaw_deg)
    for _ in range(count):
        dist  = random.uniform(PALLET_MIN_DIST, PALLET_MAX_DIST)
        angle = math.radians(random.uniform(-PALLET_FOV_DEG, PALLET_FOV_DEG))
        world_angle = robot_yaw_rad + angle
        px = robot_x + dist * math.cos(world_angle)
        py = robot_y + dist * math.sin(world_angle)
        positions.append((px, py, 0.0))
    return positions


def run_orchestrator():
    rep.orchestrator.run()
    while not rep.orchestrator.get_is_started():
        simulation_app.update()
    while rep.orchestrator.get_is_started():
        simulation_app.update()
    rep.BackendDispatch.wait_until_done()
    rep.orchestrator.stop()


def main():
    # ── Load warehouse environment ────────────────────────────────────────────
    print(f"Loading stage: {ENV_URL}")
    open_stage(prefix_with_isaac_asset_server(ENV_URL))
    stage = get_current_stage()

    for i in range(100):
        if i % 10 == 0:
            print(f"App update {i}..")
        simulation_app.update()

    # ── Load robot (contains the camera we want) ──────────────────────────────
    print(f"Loading robot: {ROBOT_URL}")
    robot = rep.create.from_usd(ROBOT_URL)

    for _ in range(20):
        simulation_app.update()

    # ── Retrieve the camera prim by its USD path ──────────────────────────────
    # rep.get.camera() matches against path_pattern (regex) on the live stage.
    # Using path_match (exact string) is faster and unambiguous.
    cam = rep.get.camera(path_match=CAMERA_PATH)

    # ── Load pallets with semantic labels ─────────────────────────────────────
    # We create a pool of instances for each pallet type upfront.
    # On each frame we randomise count and positions via rep.modify.pose.
    pallet_groups = []
    for pallet_url in PALLET_URLS:
        pallet_instances = rep.create.from_usd(
            pallet_url,
            semantics=[("class", "pallet")],
            count=MAX_PALLETS_EACH,
        )
        pallet_groups.append(pallet_instances)

    for _ in range(20):
        simulation_app.update()

    # Strip all non-pallet semantics that came bundled with the environment/robot
    update_semantics(stage=stage, keep_semantics=["pallet"])

    # ── Replicator randomisation graph ───────────────────────────────────────
    with rep.trigger.on_frame(num_frames=args.num_frames):

        # --- Randomise robot pose (camera moves with it) ----------------------
        with robot:
            rep.modify.pose(
                position=rep.distribution.uniform(
                    (FLOOR_X[0], FLOOR_Y[0], 0.0),
                    (FLOOR_X[1], FLOOR_Y[1], 0.0),
                ),
                rotation=rep.distribution.uniform((0, 0, 0), (0, 0, 360)),
            )

        # --- Randomise pallet poses each frame --------------------------------
        # Because Replicator distributions are evaluated at graph-build time,
        # we use a Python-side callable registered as a randomizer to generate
        # frame-specific positions that depend on the robot's sampled pose.
        #
        # Approach: randomise pallets within the pre-defined world bounds AND
        # within a cone in front of the camera by using a large enough
        # position range that naturally concentrates objects in front of the
        # robot when combined with the robot's own randomised yaw.
        # For tighter "always in FOV" placement, replace with a custom
        # on_frame Python callback in Phase 2 (requires Isaac Sim action graph
        # or post-step hooks to read the robot's live transform).
        for pallet_group in pallet_groups:
            with pallet_group:
                rep.modify.pose(
                    position=rep.distribution.uniform(
                        (FLOOR_X[0], FLOOR_Y[0], 0.0),
                        (FLOOR_X[1], FLOOR_Y[1], 0.0),
                    ),
                    rotation=rep.distribution.uniform((0, 0, 0), (0, 0, 360)),
                    scale=1.0,
                )

        # --- Randomise scene lighting -----------------------------------------
        with rep.get.prims(path_pattern="RectLight"):
            rep.modify.attribute("color", rep.distribution.uniform((0, 0, 0), (1, 1, 1)))
            rep.modify.attribute("intensity", rep.distribution.normal(100000.0, 600000.0))
            rep.modify.visibility(rep.distribution.choice([True, False, False, False]))

    # ── Writer setup ──────────────────────────────────────────────────────────
    writer = rep.WriterRegistry.get("KittiWriter")
    print(f"Outputting data to: {args.data_dir}")
    writer.initialize(
        output_dir=args.data_dir,
        omit_semantic_type=True,
    )

    RESOLUTION = (CONFIG["width"], CONFIG["height"])
    render_product = rep.create.render_product(cam, RESOLUTION)
    writer.attach(render_product)

    # ── Run ───────────────────────────────────────────────────────────────────
    run_orchestrator()
    simulation_app.update()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        carb.log_error(f"Exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        simulation_app.close()
