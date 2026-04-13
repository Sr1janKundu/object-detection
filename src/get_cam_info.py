AMR_USD_PATH = 'https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Samples/ROS2/Robots/iw_hub_ROS.usd'
LOCAL_AMR_USD_PATH = '/home/srijan/Downloads/iw_hub_ros.usd/iw_hub_ros.usd'

cam_prim_path = '/iw_hub_ROS/chassis/front_hawk/left/camera_left'

import omni.usd
from pxr import Usd, UsdGeom, Gf
import carb.settings
def get_camera_info(camera_path=cam_prim_path):
    """
    Get all properties of a camera at the specified path
    
    Args:
        camera_path (str): Path to the camera prim in the stage
        
    Returns:
        dict: Dictionary containing all camera properties
    """
    # Get the stage
    stage = omni.usd.get_context().get_stage()
    if not stage:
        print("Error: Could not get USD stage")
        return None
    
    # Get the camera prim
    camera_prim = stage.GetPrimAtPath(camera_path)
    if not camera_prim or not camera_prim.IsValid():
        print(f"Error: Camera prim not found at path {camera_path}")
        return None
        
    # Check if it's actually a camera
    if not camera_prim.IsA(UsdGeom.Camera):
        print(f"Error: Prim at {camera_path} is not a camera")
        return None
    
    camera = UsdGeom.Camera(camera_prim)
    
    # Get all camera properties
    camera_info = {}
    
    # Basic transform information
    xform = UsdGeom.Xformable(camera_prim)
    transform = xform.ComputeLocalToWorldTransform(0)  # Get transform at time 0
    camera_info['position'] = [transform[3][0], transform[3][1], transform[3][2]]
    
    # Extract rotation (simplified)
    rotation_matrix = transform.ExtractRotationMatrix()
    camera_info['rotation_matrix'] = [
        [rotation_matrix[0][0], rotation_matrix[0][1], rotation_matrix[0][2]],
        [rotation_matrix[1][0], rotation_matrix[1][1], rotation_matrix[1][2]],
        [rotation_matrix[2][0], rotation_matrix[2][1], rotation_matrix[2][2]]
    ]
    
    # Camera attributes
    camera_info['focal_length'] = camera.GetFocalLengthAttr().Get()
    camera_info['horizontal_aperture'] = camera.GetHorizontalApertureAttr().Get()
    camera_info['vertical_aperture'] = camera.GetVerticalApertureAttr().Get()
    camera_info['focus_distance'] = camera.GetFocusDistanceAttr().Get()
    camera_info['f_stop'] = camera.GetFStopAttr().Get()
    
    # Clipping planes
    clipping_range = camera.GetClippingRangeAttr().Get()
    camera_info['near_clipping_range'] = clipping_range[0]
    camera_info['far_clipping_range'] = clipping_range[1]
    
    # Projection type
    camera_info['projection'] = camera.GetProjectionAttr().Get()
    
    # If using Isaac Sim Camera API (alternative approach)
    try:
        from isaacsim.sensors.camera import Camera
        cam = Camera(prim_path=camera_path)
        if cam.is_initialized():
            # Get intrinsics if available
            try:
                intrinsics = cam.get_intrinsics_matrix()
                camera_info['intrinsics_matrix'] = intrinsics.tolist() if hasattr(intrinsics, 'tolist') else intrinsics
            except:
                pass
                
            # Get extrinsics if available
            try:
                position, orientation = cam.get_world_pose()
                camera_info['world_position'] = position.tolist() if hasattr(position, 'tolist') else list(position)
                camera_info['world_orientation'] = orientation.tolist() if hasattr(orientation, 'tolist') else list(orientation)
            except:
                pass
    except ImportError:
        print("Note: Isaac Sim Camera API not available, using USD API only")
    
    return camera_info
def print_camera_info(camera_info):
    """Pretty print camera information"""
    if not camera_info:
        print("No camera information to display")
        return
        
    print("=== Camera Information ===")
    for key, value in camera_info.items():
        if isinstance(value, list) and len(value) > 4:
            # Truncate long lists for readability
            print(f"{key}: [{value[0]}, {value[1]}, ...] (length: {len(value)})")
        else:
            print(f"{key}: {value}")
def list_all_cameras_in_stage():
    """List all camera prims in the stage"""
    stage = omni.usd.get_context().get_stage()
    if not stage:
        print("Error: Could not get USD stage")
        return []
        
    cameras = []
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Camera):
            cameras.append({
                'path': str(prim.GetPath()),
                'name': prim.GetName()
            })
    
    return cameras
if __name__ == "__main__":
    print("Isaac Sim Camera Information Script")
    print("=" * 40)
    
    # List all cameras in the stage
    cameras = list_all_cameras_in_stage()
    if cameras:
        print(f"Found {len(cameras)} camera(s) in the stage:")
        for i, cam in enumerate(cameras):
            print(f"  {i+1}. {cam['name']} at {cam['path']}")
        print()
    else:
        print("No cameras found in the stage")
        print()
    
    # Get info for the first camera or a specific one
    target_camera_path = "/World/Camera"  # Default path
    
    # If we found cameras, use the first one
    if cameras:
        target_camera_path = cameras[0]['path']
        print(f"Getting information for camera at: {target_camera_path}")
    else:
        print(f"No cameras found. Trying default path: {target_camera_path}")
    
    # Get camera information
    camera_info = get_camera_info(target_camera_path)
    
    # Print the information
    print_camera_info(camera_info)
    
    print("\nScript completed.")