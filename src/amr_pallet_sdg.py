#!/usr/bin/env python3

"""
Synthetic data generation script that spawns the full AMR USD file
and captures images from its specific camera_left
"""

from omni.isaac.kit import SimulationApp
import os
import argparse
import omni.usd
from pxr import Usd
import omni.replicator.core as rep
from omni.isaac.core.utils.nucleus import get_assets_root_path
from omni.isaac.core.utils.stage import get_current_stage, open_stage
import carb

# Import paths from our existing script
import sys

sys.path.append("/media/srijan/New Volume/work/object-detection/src")
from get_cam_info import (
    AMR_USD_PATH,
    LOCAL_AMR_USD_PATH,
    cam_prim_path,
)

# Increase subframes if shadows/ghosting appears of moving objects
rep.settings.carb_settings("/omni/replicator/RTSubframes", 4)

# Pallet URLs to use
PALLET_URLS = [
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Props/Pallet/pallet.usd",
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Props/Pallet/o3dyn_pallet.usd",
]


def prefix_with_isaac_asset_server(relative_path):
    """Convert relative Isaac Sim path to full asset server path"""
    assets_root_path = get_assets_root_path()
    if assets_root_path is None:
        raise Exception(
            "Nucleus server not found, could not access Isaac Sim assets folder"
        )
    return assets_root_path + relative_path


def add_pallets():
    """Add pallets to the scene with semantics for detection"""
    rep_obj_list = [
        rep.create.from_usd(pallet_path, semantics=[("class", "pallet")], count=5)
        for pallet_path in PALLET_URLS
    ]
    rep_pallet_group = rep.create.group(rep_obj_list)
    return rep_pallet_group


def main():
    parser = argparse.ArgumentParser("AMR-based Pallet Synthetic Data Generator")
    parser.add_argument(
        "--headless",
        type=bool,
        default=False,
        help="Launch script headless, default is False",
    )
    parser.add_argument("--height", type=int, default=544, help="Height of image")
    parser.add_argument("--width", type=int, default=960, help="Width of image")
    parser.add_argument(
        "--num_frames", type=int, default=1000, help="Number of frames to record"
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        default="/media/srijan/New Volume/work/object-detection/synthetic-data",
        help="Location where data will be output",
    )

    args, unknown_args = parser.parse_known_args()

    # Simulation configuration
    CONFIG = {
        "renderer": "RayTracedLighting",
        "headless": args.headless,
        "width": args.width,
        "height": args.height,
        "num_frames": args.num_frames,
    }

    # Initialize simulation
    simulation_app = SimulationApp(launch_config=CONFIG)

    try:
        # Load the warehouse environment first
        warehouse_url = prefix_with_isaac_asset_server(
            "/Isaac/Environments/Simple_Warehouse/warehouse.usd"
        )
        print(f"Loading warehouse stage: {warehouse_url}")
        open_stage(warehouse_url)
        stage = get_current_stage()

        # Allow stage to load
        for i in range(50):
            simulation_app.update()

        print("Adding pallets to the scene...")
        # Add pallets
        pallet_group = add_pallets()

        print(f"Spawning AMR USD from: {AMR_USD_PATH}")
        # Spawn the entire AMR USD file into the scene
        # This will bring in the robot with all its components including the camera
        amr_group = rep.create.from_usd(
            AMR_USD_PATH, semantics=[("class", "amr")], count=1
        )

        print("Setting up Replicator pipeline...")
        # Trigger replicator pipeline
        with rep.trigger.on_frame(num_frames=CONFIG["num_frames"]):
            # Add slight randomization to pallet poses for variety
            with pallet_group:
                rep.modify.pose(
                    position=rep.distribution.uniform((-5, -5, 0), (5, 5, 0)),
                    rotation=rep.distribution.uniform((0, 0, 0), (0, 0, 360)),
                )

            # Add slight randomization to AMR pose (keep it mostly in place)
            with amr_group:
                rep.modify.pose(
                    position=rep.distribution.uniform((-1, -1, 0), (1, 1, 0.2)),
                    rotation=rep.distribution.uniform((0, 0, -15), (0, 0, 15)),
                )

            # Randomize lighting
            with rep.get.prims(path_pattern="RectLight"):
                rep.modify.attribute(
                    "color", rep.distribution.uniform((0.8, 0.8, 0.8), (1.0, 1.0, 1.0))
                )
                rep.modify.attribute(
                    "intensity", rep.distribution.normal(50000.0, 20000.0)
                )

        print("Setting up writer...")
        # Set up the writer for KITTI format output
        writer = rep.WriterRegistry.get("KittiWriter")

        # Output directory
        output_directory = args.data_dir
        os.makedirs(output_directory, exist_ok=True)
        print(f"Outputting data to: {output_directory}")

        # Initialize writer
        writer.initialize(output_dir=output_directory, omit_semantic_type=True)

        # Create a render product using the specific camera from the spawned AMR
        # The camera path will be relative to where the USD was spawned
        # Since we spawned it without a specific path, it will be at the default location
        # We need to construct the full path to the camera
        camera_path = (
            "/amr" + cam_prim_path
        )  # /amr/iw_hub_ROS/chassis/front_hawk/left/camera_left
        print(f"Creating render product for camera at: {camera_path}")

        RESOLUTION = (CONFIG["width"], CONFIG["height"])
        render_product = rep.create.render_product(camera_path, RESOLUTION)
        writer.attach(render_product)

        print("Starting data generation...")
        # Run the replicator pipeline
        rep.orchestrator.run()

        # Wait for completion
        while rep.orchestrator.get_is_started():
            simulation_app.update()

        rep.BackendDispatch.wait_until_done()
        rep.orchestrator.stop()

        print(f"Synthetic data generation complete! Data saved to: {output_directory}")

    except Exception as e:
        carb.log_error(f"Exception during execution: {e}")
        import traceback

        traceback.print_exc()

    finally:
        simulation_app.close()


if __name__ == "__main__":
    main()
