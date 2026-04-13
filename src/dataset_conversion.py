import os
from PIL import Image

# paths
kitti_labels_dir = "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_500/camera_left/object_detection"
images_dir = "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_500/camera_left/rgb"
yolo_labels_dir = "/media/srijan/New Volume/object-detection/synthetic_data/yolo_500"

os.makedirs(yolo_labels_dir, exist_ok=True)

# define class mapping
class_map = {
    "pallet": 0
}

for label_file in os.listdir(kitti_labels_dir):
    if not label_file.endswith(".txt"):
        continue

    kitti_path = os.path.join(kitti_labels_dir, label_file)
    yolo_path = os.path.join(yolo_labels_dir, label_file)

    # corresponding image
    image_file = label_file.replace(".txt", ".png")  # or .jpg
    image_path = os.path.join(images_dir, image_file)

    # get image size
    with Image.open(image_path) as img:
        W, H = img.size

    with open(kitti_path, "r") as f:
        lines = f.readlines()

    yolo_lines = []

    for line in lines:
        parts = line.strip().split()

        if len(parts) == 0:
            continue  # skip empty lines

        class_name = parts[0]

        if class_name not in class_map:
            continue  # skip unknown classes

        class_id = class_map[class_name]

        xmin = float(parts[4])
        ymin = float(parts[5])
        xmax = float(parts[6])
        ymax = float(parts[7])

        # convert
        x_center = ((xmin + xmax) / 2) / W
        y_center = ((ymin + ymax) / 2) / H
        width = (xmax - xmin) / W
        height = (ymax - ymin) / H

        yolo_lines.append(f"{class_id} {x_center} {y_center} {width} {height}")

    # write file (IMPORTANT: even if empty)
    with open(yolo_path, "w") as f:
        for line in yolo_lines:
            f.write(line + "\n")