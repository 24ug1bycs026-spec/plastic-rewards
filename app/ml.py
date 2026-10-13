import os
import random
import numpy as np
from PIL import Image

# Must match the order printed by class_names in your Colab notebook.
CLASS_NAMES = [
    "non_recyclable_plastic",
    "not_plastic",
    "pet_bottle",
    "plastic_bag",
    "plastic_container",
]

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "model.keras")
_model = None

def _load_model():
    global _model
    if _model is None and os.path.exists(MODEL_PATH):
        import tensorflow as tf
        _model = tf.keras.models.load_model(MODEL_PATH)
    return _model

def predict(image_path):
    """Return (class_name, confidence)."""
    model = _load_model()
    if model is None:
        # DEV ONLY: lets you build the rest of the app before training finishes
        return random.choice(CLASS_NAMES), round(random.uniform(0.75, 0.99), 2)

    img = Image.open(image_path).convert("RGB").resize((224, 224))
    arr = np.expand_dims(np.array(img, dtype="float32"), axis=0)
    probs = model.predict(arr, verbose=0)[0]
    i = int(np.argmax(probs))
    return CLASS_NAMES[i], float(probs[i])