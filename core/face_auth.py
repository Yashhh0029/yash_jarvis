# core/face_auth.py
"""
SAFE DUMMY FACE AUTH MODULE
---------------------------------
This prevents DeepFace/TensorFlow import errors.
It never uses heavy models, and always returns verified.
"""

def verify_face():
    # Always return True
    return True

def load():
    print("📸 FaceAuth dummy loaded — always verified (no DeepFace).")

# auto-run
load()
