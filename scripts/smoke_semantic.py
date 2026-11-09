"""Live CPU smoke test for the pinned multilingual FastEmbed model."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import semantic

english = semantic.embed_text("The sun provides energy to the Earth.")
persian = semantic.embed_text("خورشید به زمین انرژی می‌رساند.")

assert len(english) == semantic.DIMENSION
assert len(persian) == semantic.DIMENSION
assert all(math.isfinite(value) for value in english + persian)
assert abs(sum(value * value for value in english) - 1.0) < 1e-4
assert abs(sum(value * value for value in persian) - 1.0) < 1e-4
assert semantic.model_loaded()

print({
    "ok": True,
    "model": semantic.MODEL_NAME,
    "dimension": semantic.DIMENSION,
    "languages": ["English", "Persian"],
    "inference": "local-cpu",
})
