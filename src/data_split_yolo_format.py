import os
import shutil
import random

# paths
images_dir = "/media/srijan/New Volume/object-detection/synthetic_data/replicator_kitti/pallet_500/camera_left/rgb"
labels_dir = "/media/srijan/New Volume/object-detection/synthetic_data/yolo_500"
output_dir = "/media/srijan/New Volume/object-detection/synthetic_data/YOLO_CUSTOM_PALLET_DS_500"

# split ratios
train_ratio = 0.7
val_ratio = 0.2
test_ratio = 0.1

# create output dirs
for split in ["train", "val", "test"]:
    os.makedirs(os.path.join(output_dir, "images", split), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "labels", split), exist_ok=True)

# get all image files
image_files = [f for f in os.listdir(images_dir) if f.endswith((".png", ".jpg", ".jpeg"))]

# shuffle
random.shuffle(image_files)

# split indices
n = len(image_files)
train_end = int(n * train_ratio)
val_end = train_end + int(n * val_ratio)

train_files = image_files[:train_end]
val_files = image_files[train_end:val_end]
test_files = image_files[val_end:]

def copy_files(file_list, split):
    for img_file in file_list:
        label_file = os.path.splitext(img_file)[0] + ".txt"

        src_img = os.path.join(images_dir, img_file)
        src_lbl = os.path.join(labels_dir, label_file)

        dst_img = os.path.join(output_dir, "images", split, img_file)
        dst_lbl = os.path.join(output_dir, "labels", split, label_file)

        shutil.copy2(src_img, dst_img)

        # copy label if exists, else create empty file
        if os.path.exists(src_lbl):
            shutil.copy2(src_lbl, dst_lbl)
            print(f"Copied: {img_file} with label")
        else:
            open(dst_lbl, "w").close()
            print(f"Copied: {img_file} without label")

# copy splits
copy_files(train_files, "train")
copy_files(val_files, "val")
copy_files(test_files, "test")

print(f"Done. Total: {n}")
print(f"Train: {len(train_files)}, Val: {len(val_files)}, Test: {len(test_files)}")