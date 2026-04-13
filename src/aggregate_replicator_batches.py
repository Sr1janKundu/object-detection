import os
import shutil

# List your source folders in order
source_dirs = [
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_1",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_2",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_3",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_4",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_5",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_6",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_7",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_8",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_9",
    "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100_10",
]

# Destination folders
dest_images = "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100"
dest_labels = "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_100"

os.makedirs(dest_images, exist_ok=True)
os.makedirs(dest_labels, exist_ok=True)

counter = 0

for folder in source_dirs:
    for i in range(50):  # since each folder has 0–49
        img_src = os.path.join(folder, f"{i}.png")
        lbl_src = os.path.join(folder, f"{i}.txt")

        img_dst = os.path.join(dest_images, f"{counter}.png")
        lbl_dst = os.path.join(dest_labels, f"{counter}.txt")

        shutil.copy(img_src, img_dst)
        shutil.copy(lbl_src, lbl_dst)

        counter += 1

print(f"Done. Total files: {counter}")
