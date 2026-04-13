import os
import random
import cv2

base_dir = "/media/srijan/New Volume/object-detection/synthetic_data/YOLO_CUSTOM_PALLET_DS_500"
output_dir = "/media/srijan/New Volume/object-detection/synthetic_data/yolo500_bbox_check"

os.makedirs(output_dir, exist_ok=True)

splits = ["train", "val", "test"]
num_samples_total = 100

all_images = []

# collect all image paths with split info
for split in splits:
    images_dir = os.path.join(base_dir, "images", split)
    for f in os.listdir(images_dir):
        if f.endswith((".png", ".jpg", ".jpeg")):
            all_images.append((split, f))

# random sample
samples = random.sample(all_images, min(num_samples_total, len(all_images)))

for idx, (split, img_file) in enumerate(samples):
    img_path = os.path.join(base_dir, "images", split, img_file)
    label_path = os.path.join(base_dir, "labels", split, os.path.splitext(img_file)[0] + ".txt")

    img = cv2.imread(img_path)
    if img is None:
        print(f"Failed to read {img_path}")
        continue

    H, W, _ = img.shape

    if os.path.exists(label_path):
        with open(label_path, "r") as f:
            lines = f.readlines()

        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue

            class_id, x_c, y_c, w, h = map(float, parts)

            # YOLO → pixel
            x_c *= W
            y_c *= H
            w *= W
            h *= H

            xmin = int(x_c - w / 2)
            ymin = int(y_c - h / 2)
            xmax = int(x_c + w / 2)
            ymax = int(y_c + h / 2)

            # draw box
            cv2.rectangle(img, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)

            # label
            cv2.putText(img, str(int(class_id)), (xmin, ymin - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # save image
    out_name = f"{idx:03d}_{split}_{img_file}"
    out_path = os.path.join(output_dir, out_name)
    cv2.imwrite(out_path, img)

print(f"Saved {len(samples)} images to {output_dir}")