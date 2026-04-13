from omni.isaac.kit import SimulationApp

CONFIG = {"renderer": "RayTracedLighting", "headless": True, "width": 960, "height": 544}
simulation_app = SimulationApp(launch_config=CONFIG)

import math, random, carb
import omni.replicator.core as rep
from omni.isaac.core.utils.nucleus import get_assets_root_path
from omni.isaac.core.utils.stage import open_stage, get_current_stage
from pxr import Semantics

# ── Asset URLs ────────────────────────────────────────────────────────────────
ENV_URL     = "/Isaac/Environments/Simple_Warehouse/warehouse.usd"
ROBOT_URL   = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Samples/ROS2/Robots/iw_hub_ROS.usd"
# CAMERA_PATH = "/iw_hub_ROS/chassis/front_hawk/left/camera_left"
PALLET_URLS = [
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Props/Pallet/pallet.usd",
    "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Props/Pallet/o3dyn_pallet.usd",
]

NUM_FRAMES   = 300
RESOLUTION   = (960, 544)
OUTPUT_DIR   = "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_4"

# Warehouse floor bounds
FLOOR_X = (-9.2, 7.2)
FLOOR_Y = (-11.8, 15.8)

# Pallet placement: z=0, 1–8 m ahead, within ±100° of camera forward
PALLET_MIN_DIST = 1.0
PALLET_MAX_DIST = 8.0
PALLET_FOV_DEG  = 100.0
MAX_PALLETS     = 5   # pool size — visibility per frame controlled by pose spread


def nucleus(path):
    root = get_assets_root_path()
    if root is None:
        raise RuntimeError("Nucleus server not found")
    return root + path


def strip_semantics(stage, keep=("pallet",)):
    for prim in stage.Traverse():
        if not prim.HasAPI(Semantics.SemanticsAPI):
            continue
        seen = set()
        for prop in prim.GetProperties():
            if not Semantics.SemanticsAPI.IsSemanticsAPIPath(prop.GetPath()):
                continue
            inst = prop.SplitName()[1]
            if inst in seen:
                continue
            seen.add(inst)
            sem = Semantics.SemanticsAPI.Get(prim, inst)
            t, d = sem.GetSemanticTypeAttr(), sem.GetSemanticDataAttr()
            if d.Get() not in keep:
                prim.RemoveProperty(t.GetName())
                prim.RemoveProperty(d.GetName())
                prim.RemoveAPI(Semantics.SemanticsAPI, inst)

def find_camera_path(stage, match: str) -> str:
    """Return the first Camera prim path whose string contains `match`."""
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if prim.GetTypeName() == "Camera" and match in path:
            return path
    raise RuntimeError(f"No Camera prim found matching '{match}'")

def main():
    # ── Stage ─────────────────────────────────────────────────────────────────
    open_stage(nucleus(ENV_URL))
    stage = get_current_stage()
    for _ in range(100):
        simulation_app.update()

    # ── Robot (1 instance) ────────────────────────────────────────────────────
    robot = rep.create.from_usd(ROBOT_URL, count=1)
    for _ in range(20):
        simulation_app.update()

    # ── Camera ────────────────────────────────────────────────────────────────
    # cam = rep.get.camera(path_match=CAMERA_PATH)
    cam_path = find_camera_path(stage, "chassis/front_hawk/left/camera_left")
    print(f"Using camera: {cam_path}")
    cam = rep.get.camera(path_match=cam_path)

    # ── Pallets (pool of MAX_PALLETS per type, labelled) ──────────────────────
    pallet_groups = [
        rep.create.from_usd(url, semantics=[("class", "pallet")], count=MAX_PALLETS)
        for url in PALLET_URLS
    ]
    for _ in range(20):
        simulation_app.update()

    strip_semantics(stage, keep=("pallet",))

    # ── Randomisation graph ───────────────────────────────────────────────────
    rep.settings.carb_settings("/omni/replicator/RTSubframes", 4)

    with rep.trigger.on_frame(num_frames=NUM_FRAMES):

        # Place robot randomly on warehouse floor
        with robot:
            rep.modify.pose(
                position=rep.distribution.uniform(
                    (FLOOR_X[0], FLOOR_Y[0], 0.0),
                    (FLOOR_X[1], FLOOR_Y[1], 0.0),
                ),
                rotation=rep.distribution.uniform((0, 0, 0), (0, 0, 360)),
            )

        # Scatter 1–5 pallets of each type across the warehouse floor.
        # NOTE: precise "in-front-of-camera" placement requires reading the
        # robot's live transform post-step (Phase 2). For now, pallets are
        # placed randomly on the floor and the robot is aimed toward the scene
        # centre so overlap with the camera FOV is frequent.
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

    # ── Writer ────────────────────────────────────────────────────────────────
    writer = rep.WriterRegistry.get("KittiWriter")
    writer.initialize(output_dir=OUTPUT_DIR, omit_semantic_type=True)
    writer.attach(rep.create.render_product(cam, RESOLUTION))

    # ── Run ───────────────────────────────────────────────────────────────────
    rep.orchestrator.run()
    while not rep.orchestrator.get_is_started():
        simulation_app.update()
    while rep.orchestrator.get_is_started():
        simulation_app.update()
    rep.BackendDispatch.wait_until_done()
    rep.orchestrator.stop()
    simulation_app.update()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        carb.log_error(f"Exception: {e}")
        import traceback; traceback.print_exc()
    finally:
        simulation_app.close()
