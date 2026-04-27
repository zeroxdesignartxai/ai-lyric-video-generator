from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_SIZE = (1920, 1080)


def validate_image_file(image_path: str | None) -> Path:
    if not image_path:
        raise ValueError("Please upload an image.")

    path = Path(image_path)
    if not path.exists():
        raise ValueError("Uploaded image file could not be found.")

    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image type. Upload a jpg, png, or webp file.")

    return path


def resize_crop_image(image_path: str, output_path: str, size: tuple[int, int] = VIDEO_SIZE) -> str:
    path = validate_image_file(image_path)
    target_w, target_h = size
    with Image.open(path) as image:
        image = image.convert("RGB")
        scale = max(target_w / image.width, target_h / image.height)
        new_size = (int(image.width * scale), int(image.height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        left = (image.width - target_w) // 2
        top = (image.height - target_h) // 2
        image = image.crop((left, top, left + target_w, top + target_h))
        image = ImageEnhance.Color(image).enhance(1.08)
        image = ImageEnhance.Contrast(image).enhance(1.06)
        image.save(output_path, format="JPEG", quality=94)
    return output_path


def add_vignette(frame: np.ndarray, strength: float = 0.45) -> np.ndarray:
    height, width = frame.shape[:2]
    y = np.linspace(-1, 1, height)[:, None]
    x = np.linspace(-1, 1, width)[None, :]
    distance = np.sqrt(x * x + y * y)
    mask = np.clip(1 - strength * (distance ** 1.65), 0.25, 1.0)
    return np.clip(frame.astype(np.float32) * mask[..., None], 0, 255).astype(np.uint8)


def add_grain(frame: np.ndarray, amount: float = 5.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, amount, frame.shape)
    return np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def add_dark_overlay(frame: np.ndarray, opacity: float = 0.28) -> np.ndarray:
    return np.clip(frame.astype(np.float32) * (1.0 - opacity), 0, 255).astype(np.uint8)


def add_soft_glow(frame: np.ndarray) -> np.ndarray:
    image = Image.fromarray(frame)
    glow = image.filter(ImageFilter.GaussianBlur(radius=18))
    blended = Image.blend(image, glow, 0.16)
    return np.array(blended)
