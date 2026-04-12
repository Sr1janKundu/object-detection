#!/usr/bin/env python3

"""
Synthetic data generation script for pallet detection using AMR camera properties
"""

from omni.isaac.kit import SimulationApp
import os
import argparse
import omni.usd
from pxr import Usd, UsdGeom
import omni.replicator.core as rep
from omni.isaac.core.utils.nucleus import get_assets_root_path
from omni.isaac.core.utils.stage import get_current_stage, open_stage
from omni.isaac.core.utils.semantics import get_semantics
import carb

# Import camera info from our existing script
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


def get_camera_properties_from_usd(usd_path, cam_path):
    """
    Extract camera properties from a USD file by opening it in a temporary stage

    Args:
        usd_path (str): Path to the USD file
        cam_path (str): Path to the camera prim within the USD

    Returns:
        dict: Dictionary containing all camera properties or None if failed
    """
    # Save the current stage to restore later
    current_stage = omni.usd.get_context().get_stage()

    try:
        # Open the USD file in a new stage
        temp_stage = omni.usd.get_context().open_stage(usd_path)

        # Get the camera prim
        camera_prim = temp_stage.GetPrimAtPath(cam_path)
        if not camera_prim or not camera_prim.IsValid():
            print(f"Error: Camera prim not found at path {cam_path} in {usd_path}")
            return None

        # Check if it's actually a camera
        if not camera_prim.IsA(UsdGeom.Camera):
            print(f"Error: Prim at {cam_path} is not a camera")
            return None

        camera = UsdGeom.Camera(camera_prim)

        # Get all camera properties
        camera_info = {}

        # Basic transform information
        xform = UsdGeom.Xformable(camera_prim)
        transform = xform.ComputeLocalToWorldTransform(0)  # Get transform at time 0
        camera_info["position"] = [transform[3][0], transform[3][1], transform[3][2]]

        # Extract rotation (we'll use look_at approach instead of complex rotation conversion)
        # For now we'll calculate a look-at based on the position and assuming it looks at origin
        # A more sophisticated approach would extract the actual orientation

        # Camera attributes
        camera_info["focal_length"] = camera.GetFocalLengthAttr().Get()
        camera_info["horizontal_aperture"] = camera.GetHorizontalApertureAttr().Get()
        camera_info["vertical_aperture"] = camera.GetVerticalApertureAttr().Get()
        camera_info["focus_distance"] = camera.GetFocusDistanceAttr().Get()
        camera_info["f_stop"] = camera.GetFStopAttr().Get()

        # Clipping planes
        clipping_range = camera.GetClippingRangeAttr().Get()
        camera_info["near_clipping_range"] = clipping_range[0]
        camera_info["far_clipping_range"] = clipping_range[1]

        # Projection type
        camera_info["projection"] = camera.GetProjectionAttr().Get()

        return camera_info

    except Exception as e:
        print(f"Error extracting camera properties from USD: {e}")
        return None
    finally:
        # Restore the original stage
        if current_stage:
            omni.usd.get_context().set_stage(current_stage)


def add_pallets():
    """Add pallets to the scene with semantics for detection"""
    rep_obj_list = [
        rep.create.from_usd(pallet_path, semantics=[("class", "pallet")], count=5)
        for pallet_path in PALLET_URLS
    ]
    rep_pallet_group = rep.create.group(rep_obj_list)
    return rep_pallet_group


def setup_camera_from_usd():
    """
    Setup camera using properties from the AMR USD file
    """
    # Get camera properties from the USD file
    camera_info = get_camera_properties_from_usd(LOCAL_AMR_USD_PATH, cam_prim_path)
    if not camera_info:
        raise Exception("Failed to get camera info from AMR USD")

    # Create a camera using Replicator and set its properties to match the USD camera
    cam = rep.create.camera()

    # Apply the camera properties from the USD file
    with cam:
        # Set position
        rep.modify.pose(position=camera_info["position"])

        # Set orientation - looking at origin (0,0,0) as a reasonable default
        # In a production system, you might want to extract the actual orientation
        # from the USD camera's transform matrix
        rep.modify.pose(look_at=(0, 0, 0))

        # Set camera intrinsics
        rep.modify.attribute("focalLength", camera_info["focal_length"])
        rep.modify.attribute("horizontalAperture", camera_info["horizontal_aperture"])
        rep.modify.attribute("verticalAperture", camera_info["vertical_aperture"])
        rep.modify.attribute("focusDistance", camera_info["focus_distance"])
        rep.modify.attribute("fStop", camera_info["f_stop"])
        rep.modify.attribute(
            "clippingRange",
            (camera_info["near_clipping_range"], camera_info["far_clipping_range"]),
        )
        rep.modify.attribute("projection", camera_info["projection"])

    return cam


def main():
    parser = argparse.ArgumentParser("Pallet Synthetic Data Generator")
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
        # Load the warehouse environment
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

        # Add semantics for pallets (already done in add_pallets)

        print("Setting up camera from AMR USD properties...")
        # Setup camera using properties from the AMR USD file
        cam = setup_camera_from_usd()

        print("Setting up Replicator pipeline...")
        # Trigger replicator pipeline
        with rep.trigger.on_frame(num_frames=CONFIG["num_frames"]):
            # Add slight randomization to pallet poses for variety
            with pallet_group:
                rep.modify.pose(
                    position=rep.distribution.uniform((-5, -5, 0), (5, 5, 0)),
                    rotation=rep.distribution.uniform((0, 0, 0), (0, 0, 360)),
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

        # Attach camera render products to writer
        RESOLUTION = (CONFIG["width"], CONFIG["height"])
        render_product = rep.create.render_product(cam, RESOLUTION)
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
