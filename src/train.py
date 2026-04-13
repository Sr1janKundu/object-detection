import ultralytics
ultralytics.checks()

import os

from ultralytics import RTDETR
model = RTDETR("rtdetr-l.pt")
results = model.train(data="/mnt/object-detection/synthetic_data/YOLO_CUSTOM_PALLET_DS_500/yolo.yaml", epochs=10, imgsz=640)
print(f"Model saved to: {model.trainer.save_dir}/weights/best.pt")
modele = RTDETR(f"{model.trainer.save_dir}/weights/best.pt")  # load a fine-tuned model
# Export the model
modele.export(format="onnx")