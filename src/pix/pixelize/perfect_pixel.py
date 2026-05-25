"""AI 生图结果的 perfectPixel 风格网格对齐预处理。

算法流程参考 theamusing/perfectPixel 的 MIT 轻量后端思路：FFT 估计像素网格、
Sobel/梯度峰值细化网格线，再按网格采样得到对齐后的低分辨率像素图。
这里保留 Pix 自身的 Pillow/NumPy 接口、RGBA 支持和失败回退语义，不新增运行时依赖。
"""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from functools import lru_cache
import importlib.util
import io
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image

GeneratedPreprocessMethod = Literal["legacy", "none", "perfect_pixel"]
SampleMethod = Literal["center", "median"]


@dataclass(frozen=True)
class GeneratedPreprocessResult:
    image: Image.Image
    meta: dict


def normalize_generated_preprocess_method(value: str | None) -> GeneratedPreprocessMethod:
    text = (value or "legacy").strip().lower().replace("-", "_")
    if text in {"perfect", "perfectpixel", "perfect_pixel"}:
        return "perfect_pixel"
    if text in {"none", "off", "disabled", "disable"}:
        return "none"
    return "legacy"


def preprocess_generated_image(
    image: Image.Image,
    *,
    method: str | None,
    target_size: tuple[int, int] | None,
    sample_method: SampleMethod = "center",
    min_size: float = 4.0,
    peak_width: int = 6,
    refine_intensity: float = 0.25,
) -> GeneratedPreprocessResult:
    """按生成图预处理策略返回图像和可追踪 metadata。

    直接传入 ``legacy`` / ``none`` 时不改变图像。``perfect_pixel`` 会优先使用
    ``target_size`` 作为目标网格尺寸，避免 perfectPixel 自动检测出的低分辨率网格
    与 Pix 最终 output_size 不一致而产生二次缩放。
    """
    normalized = normalize_generated_preprocess_method(method)
    base_meta = {
        "method": normalized,
        "applied": False,
        "reason": "disabled" if normalized in {"legacy", "none"} else None,
        "original_size": list(image.size),
        "target_size": list(target_size) if target_size else None,
        "sample_method": sample_method,
    }
    if normalized != "perfect_pixel":
        return GeneratedPreprocessResult(image=image, meta=base_meta)

    try:
        refined_w, refined_h, refined, details = _get_external_perfect_pixel(
            image,
            grid_size=target_size,
            sample_method=sample_method,
            min_size=min_size,
            peak_width=peak_width,
            refine_intensity=refine_intensity,
        )
    except Exception as external_exc:  # noqa: BLE001 - 外部 perfectPixel 不可用时回退内置实现
        try:
            refined_w, refined_h, refined, details = _get_perfect_pixel_like(
                image,
                grid_size=target_size,
                sample_method=sample_method,
                min_size=min_size,
                peak_width=peak_width,
                refine_intensity=refine_intensity,
            )
            details = {
                **details,
                "backend": "builtin_numpy",
                "external_backend_error": str(external_exc),
            }
        except Exception as exc:  # noqa: BLE001 - 预处理失败必须回退旧流程
            return GeneratedPreprocessResult(
                image=image,
                meta={**base_meta, "reason": "error", "error": str(exc), "external_backend_error": str(external_exc)},
            )

    if refined_w is None or refined_h is None or refined is None:
        return GeneratedPreprocessResult(
            image=image,
            meta={**base_meta, "reason": details.get("reason", "failed"), **details},
        )
    target_mismatch = target_size is not None and (int(refined_w), int(refined_h)) != (int(target_size[0]), int(target_size[1]))
    if target_mismatch and details.get("backend") != "perfectPixel-main/noCV2":
        return GeneratedPreprocessResult(
            image=image,
            meta={
                **base_meta,
                "reason": "size_mismatch",
                "refined_size": [int(refined_w), int(refined_h)],
                **details,
            },
        )

    mode = "RGBA" if refined.ndim == 3 and refined.shape[2] == 4 else "RGB"
    out = Image.fromarray(refined.astype(np.uint8), mode=mode)
    return GeneratedPreprocessResult(
        image=out,
        meta={
            **base_meta,
            "applied": True,
            "reason": "target_size_mismatch_accepted" if target_mismatch else "ok",
            "refined_size": [int(refined_w), int(refined_h)],
            "target_size_mismatch": bool(target_mismatch),
            "output_size": list(out.size),
            **details,
        },
    )


@lru_cache(maxsize=1)
def _load_external_perfect_pixel():
    """优先加载仓库根目录下的 theamusing/perfectPixel 源码。"""
    repo_root = Path(__file__).resolve().parents[3]
    module_path = repo_root / "perfectPixel-main" / "src" / "perfect_pixel" / "perfect_pixel_noCV2.py"
    if not module_path.exists():
        raise FileNotFoundError(str(module_path))
    spec = importlib.util.spec_from_file_location("pix_external_perfect_pixel_noCV2", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 perfectPixel 模块：{module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    get_perfect_pixel = getattr(module, "get_perfect_pixel", None)
    if get_perfect_pixel is None:
        raise ImportError(f"perfectPixel 模块缺少 get_perfect_pixel：{module_path}")
    return get_perfect_pixel, module_path


def _get_external_perfect_pixel(
    image: Image.Image,
    *,
    grid_size: tuple[int, int] | None,
    sample_method: SampleMethod,
    min_size: float,
    peak_width: int,
    refine_intensity: float,
) -> tuple[int | None, int | None, np.ndarray | None, dict]:
    get_perfect_pixel, module_path = _load_external_perfect_pixel()
    has_alpha = "A" in image.getbands() or "transparency" in image.info
    sample_image = image.convert("RGBA" if has_alpha else "RGB")
    sample_arr = np.asarray(sample_image, dtype=np.uint8)
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        refined_w, refined_h, refined = get_perfect_pixel(
            sample_arr,
            sample_method=sample_method,
            grid_size=grid_size,
            min_size=min_size,
            peak_width=peak_width,
            refine_intensity=refine_intensity,
            fix_square=True,
            debug=False,
        )
    if refined is not None:
        refined = np.asarray(refined, dtype=np.uint8)
    return refined_w, refined_h, refined, {
        "backend": "perfectPixel-main/noCV2",
        "backend_path": str(module_path),
        "grid_size": list(grid_size) if grid_size else None,
        "stdout": stdout.getvalue().strip(),
    }


def _get_perfect_pixel_like(
    image: Image.Image,
    *,
    grid_size: tuple[int, int] | None,
    sample_method: SampleMethod,
    min_size: float,
    peak_width: int,
    refine_intensity: float,
) -> tuple[int | None, int | None, np.ndarray | None, dict]:
    has_alpha = "A" in image.getbands() or "transparency" in image.info
    sample_image = image.convert("RGBA" if has_alpha else "RGB")
    sample_arr = np.asarray(sample_image, dtype=np.uint8)
    rgb_arr = np.asarray(sample_image.convert("RGB"), dtype=np.uint8)
    height, width = rgb_arr.shape[:2]
    if width < 2 or height < 2:
        return None, None, None, {"reason": "image_too_small"}

    coord_fallback = False
    if grid_size is not None:
        grid_w, grid_h = int(grid_size[0]), int(grid_size[1])
        grid_source = "target_size"
    else:
        detected = _detect_grid_scale(rgb_arr, peak_width=peak_width, min_size=min_size)
        if detected is None:
            return None, None, None, {"reason": "grid_detection_failed"}
        grid_w, grid_h = detected
        grid_source = "auto_detect"
    if grid_w < 1 or grid_h < 1:
        return None, None, None, {"reason": "invalid_grid_size", "grid_size": [grid_w, grid_h]}

    x_coords, y_coords = _refine_grids(
        rgb_arr,
        grid_w=grid_w,
        grid_h=grid_h,
        refine_intensity=refine_intensity,
    )
    if grid_size is not None and (len(x_coords) != grid_w + 1 or len(y_coords) != grid_h + 1):
        x_coords = _even_grid_coords(width, grid_w)
        y_coords = _even_grid_coords(height, grid_h)
        coord_fallback = True
    if len(x_coords) < 2 or len(y_coords) < 2:
        return None, None, None, {"reason": "not_enough_grid_lines", "grid_size": [grid_w, grid_h]}

    if sample_method == "median":
        out = _sample_median(sample_arr, x_coords, y_coords)
    else:
        out = _sample_center(sample_arr, x_coords, y_coords)
    refined_h, refined_w = out.shape[:2]
    return refined_w, refined_h, out, {
        "grid_size": [int(grid_w), int(grid_h)],
        "grid_source": grid_source,
        "coord_fallback": coord_fallback,
        "grid_lines": {"x": len(x_coords), "y": len(y_coords)},
        "refine_intensity": float(refine_intensity),
        "peak_width": int(peak_width),
        "min_size": float(min_size),
    }


def _rgb_to_gray(image_rgb: np.ndarray) -> np.ndarray:
    img = image_rgb.astype(np.float32, copy=False)
    if img.ndim == 2:
        return img
    return (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).astype(np.float32)


def _normalize_minmax(values: np.ndarray) -> np.ndarray:
    data = values.astype(np.float32, copy=False)
    mn = float(data.min())
    mx = float(data.max())
    if mx - mn < 1e-8:
        return np.zeros_like(data, dtype=np.float32)
    return ((data - mn) / (mx - mn)).astype(np.float32)


def _conv2d_same(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    img = image.astype(np.float32, copy=False)
    ker = kernel.astype(np.float32, copy=False)
    kh, kw = ker.shape
    ph, pw = kh // 2, kw // 2
    padded = np.pad(img, ((ph, ph), (pw, pw)), mode="reflect")
    out = np.zeros_like(img, dtype=np.float32)
    for dy in range(kh):
        for dx in range(kw):
            weight = ker[dy, dx]
            if weight == 0:
                continue
            out += weight * padded[dy:dy + img.shape[0], dx:dx + img.shape[1]]
    return out


def _sobel_xy(gray: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    kx = np.array(
        [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]],
        dtype=np.float32,
    )
    ky = np.array(
        [[-1, -2, -1], [0, 0, 0], [1, 2, 1]],
        dtype=np.float32,
    )
    return _conv2d_same(gray, kx), _conv2d_same(gray, ky)


def _compute_fft_magnitude(gray_image: np.ndarray) -> np.ndarray:
    freq = np.fft.fft2(gray_image.astype(np.float32))
    shifted = np.fft.fftshift(freq)
    mag = 1 - np.log1p(np.abs(shifted))
    return _normalize_minmax(mag)


def _smooth_1d(values: np.ndarray, k: int = 17) -> np.ndarray:
    safe_k = int(k)
    if safe_k < 3:
        return values
    if safe_k % 2 == 0:
        safe_k += 1
    sigma = safe_k / 6.0
    x = np.arange(safe_k) - safe_k // 2
    kernel = np.exp(-(x * x) / (2 * sigma * sigma))
    kernel = kernel / (kernel.sum() + 1e-8)
    return np.convolve(values, kernel, mode="same")


def _detect_peak(proj: np.ndarray, peak_width: int = 6, rel_thr: float = 0.35, min_dist: int = 6) -> float | None:
    center = len(proj) // 2
    mx = float(proj.max())
    if mx < 1e-6:
        return None
    threshold = mx * float(rel_thr)
    candidates: list[dict[str, float]] = []
    safe_width = max(1, int(peak_width))
    for i in range(1, len(proj) - 1):
        is_peak = True
        for j in range(1, safe_width):
            if i - j < 0 or i + j >= len(proj):
                continue
            if proj[i - j + 1] < proj[i - j] or proj[i + j - 1] < proj[i + j]:
                is_peak = False
                break
        if not is_peak or proj[i] < threshold:
            continue
        left_climb = 0.0
        for k in range(i, 0, -1):
            if proj[k] > proj[k - 1]:
                left_climb = abs(float(proj[i] - proj[k - 1]))
            else:
                break
        right_fall = 0.0
        for k in range(i, len(proj) - 1):
            if proj[k] > proj[k + 1]:
                right_fall = abs(float(proj[i] - proj[k + 1]))
            else:
                break
        candidates.append({"index": float(i), "score": max(left_climb, right_fall)})
    if not candidates:
        return None
    left = [item for item in candidates if item["index"] < center - min_dist and item["index"] > center * 0.25]
    right = [item for item in candidates if item["index"] > center + min_dist and item["index"] < center * 1.75]
    left.sort(key=lambda item: item["score"], reverse=True)
    right.sort(key=lambda item: item["score"], reverse=True)
    if not left or not right:
        return None
    return abs(right[0]["index"] - left[0]["index"]) / 2.0


def _estimate_grid_fft(gray: np.ndarray, *, peak_width: int) -> tuple[float, float] | None:
    height, width = gray.shape
    mag = _compute_fft_magnitude(gray)
    band_row = width // 2
    band_col = height // 2
    row_sum = np.sum(mag[:, width // 2 - band_row: width // 2 + band_row], axis=1)
    col_sum = np.sum(mag[height // 2 - band_col: height // 2 + band_col, :], axis=0)
    row_sum = _smooth_1d(_normalize_minmax(row_sum).flatten(), k=17)
    col_sum = _smooth_1d(_normalize_minmax(col_sum).flatten(), k=17)
    scale_row = _detect_peak(row_sum, peak_width=peak_width)
    scale_col = _detect_peak(col_sum, peak_width=peak_width)
    if scale_row is None or scale_col is None or scale_col <= 0:
        return None
    return scale_col, scale_row


def _estimate_grid_gradient(gray: np.ndarray, *, rel_thr: float = 0.2) -> tuple[int, int] | None:
    height, width = gray.shape
    grad_x, grad_y = _sobel_xy(gray)
    grad_x_sum = np.sum(np.abs(grad_x), axis=0).reshape(-1)
    grad_y_sum = np.sum(np.abs(grad_y), axis=1).reshape(-1)
    threshold_x = float(rel_thr) * float(grad_x_sum.max())
    threshold_y = float(rel_thr) * float(grad_y_sum.max())
    min_interval = 4
    peak_x: list[int] = []
    peak_y: list[int] = []
    for i in range(1, len(grad_x_sum) - 1):
        if grad_x_sum[i] > grad_x_sum[i - 1] and grad_x_sum[i] > grad_x_sum[i + 1] and grad_x_sum[i] >= threshold_x:
            if not peak_x or i - peak_x[-1] >= min_interval:
                peak_x.append(i)
    for i in range(1, len(grad_y_sum) - 1):
        if grad_y_sum[i] > grad_y_sum[i - 1] and grad_y_sum[i] > grad_y_sum[i + 1] and grad_y_sum[i] >= threshold_y:
            if not peak_y or i - peak_y[-1] >= min_interval:
                peak_y.append(i)
    if len(peak_x) < 4 or len(peak_y) < 4:
        return None
    intervals_x = [peak_x[i] - peak_x[i - 1] for i in range(1, len(peak_x))]
    intervals_y = [peak_y[i] - peak_y[i - 1] for i in range(1, len(peak_y))]
    scale_x = width / np.median(intervals_x)
    scale_y = height / np.median(intervals_y)
    return int(round(scale_x)), int(round(scale_y))


def _detect_grid_scale(
    image_rgb: np.ndarray,
    *,
    peak_width: int,
    max_ratio: float = 1.5,
    min_size: float = 4.0,
) -> tuple[int, int] | None:
    gray = _rgb_to_gray(image_rgb)
    height, width = gray.shape
    detected = _estimate_grid_fft(gray, peak_width=peak_width)
    if detected is None:
        gradient = _estimate_grid_gradient(gray)
        if gradient is None:
            return None
        grid_w, grid_h = gradient
    else:
        grid_w, grid_h = detected
        pixel_size_x = width / max(grid_w, 1e-6)
        pixel_size_y = height / max(grid_h, 1e-6)
        max_pixel_size = 20.0
        inconsistent = (
            min(pixel_size_x, pixel_size_y) < min_size
            or max(pixel_size_x, pixel_size_y) > max_pixel_size
            or pixel_size_x / pixel_size_y > max_ratio
            or pixel_size_y / pixel_size_x > max_ratio
        )
        if inconsistent:
            gradient = _estimate_grid_gradient(gray)
            if gradient is None:
                return None
            grid_w, grid_h = gradient
    pixel_size_x = width / max(grid_w, 1e-6)
    pixel_size_y = height / max(grid_h, 1e-6)
    if pixel_size_x <= 0 or pixel_size_y <= 0:
        return None
    if pixel_size_x / pixel_size_y > max_ratio or pixel_size_y / pixel_size_x > max_ratio:
        pixel_size = min(pixel_size_x, pixel_size_y)
    else:
        pixel_size = (pixel_size_x + pixel_size_y) / 2.0
    return int(round(width / pixel_size)), int(round(height / pixel_size))


def _find_best_grid(origin: float, range_val_min: float, range_val_max: float, grad_mag: np.ndarray, thr: float = 0.0) -> int:
    best = round(origin)
    mx = float(np.max(grad_mag))
    if mx < 1e-6:
        return int(best)
    rel_thr = mx * float(thr)
    peaks: list[tuple[float, int]] = []
    for delta in range(-round(range_val_min), round(range_val_max) + 1):
        candidate = round(origin + delta)
        if candidate <= 0 or candidate >= len(grad_mag) - 1:
            continue
        if grad_mag[candidate] > grad_mag[candidate - 1] and grad_mag[candidate] > grad_mag[candidate + 1] and grad_mag[candidate] >= rel_thr:
            peaks.append((float(grad_mag[candidate]), int(candidate)))
    if not peaks:
        return int(best)
    peaks.sort(key=lambda item: item[0], reverse=True)
    return peaks[0][1]


def _refine_grids(
    image_rgb: np.ndarray,
    *,
    grid_w: int,
    grid_h: int,
    refine_intensity: float,
) -> tuple[list[int], list[int]]:
    height, width = image_rgb.shape[:2]
    cell_w = width / max(1, int(grid_w))
    cell_h = height / max(1, int(grid_h))
    gray = _rgb_to_gray(image_rgb)
    grad_x, grad_y = _sobel_xy(gray)
    grad_x_sum = np.sum(np.abs(grad_x), axis=0).reshape(-1)
    grad_y_sum = np.sum(np.abs(grad_y), axis=1).reshape(-1)
    safe_refine = max(0.0, min(0.5, float(refine_intensity)))

    x_coords: list[int] = []
    x = _find_best_grid(width / 2, cell_w, cell_w, grad_x_sum)
    while x < width + cell_w / 2:
        x = _find_best_grid(x, cell_w * safe_refine, cell_w * safe_refine, grad_x_sum)
        x_coords.append(int(x))
        x += cell_w
    x = _find_best_grid(width / 2, cell_w, cell_w, grad_x_sum) - cell_w
    while x > -cell_w / 2:
        x = _find_best_grid(x, cell_w * safe_refine, cell_w * safe_refine, grad_x_sum)
        x_coords.append(int(x))
        x -= cell_w

    y_coords: list[int] = []
    y = _find_best_grid(height / 2, cell_h, cell_h, grad_y_sum)
    while y < height + cell_h / 2:
        y = _find_best_grid(y, cell_h * safe_refine, cell_h * safe_refine, grad_y_sum)
        y_coords.append(int(y))
        y += cell_h
    y = _find_best_grid(height / 2, cell_h, cell_h, grad_y_sum) - cell_h
    while y > -cell_h / 2:
        y = _find_best_grid(y, cell_h * safe_refine, cell_h * safe_refine, grad_y_sum)
        y_coords.append(int(y))
        y -= cell_h

    return sorted(x_coords), sorted(y_coords)


def _even_grid_coords(axis_size: int, cells: int) -> list[int]:
    return [int(round(i * axis_size / max(1, int(cells)))) for i in range(max(1, int(cells)) + 1)]


def _sample_center(image: np.ndarray, x_coords: list[int], y_coords: list[int]) -> np.ndarray:
    x = np.asarray(x_coords, dtype=np.float32)
    y = np.asarray(y_coords, dtype=np.float32)
    centers_x = np.clip(np.rint((x[1:] + x[:-1]) * 0.5), 0, image.shape[1] - 1).astype(np.intp)
    centers_y = np.clip(np.rint((y[1:] + y[:-1]) * 0.5), 0, image.shape[0] - 1).astype(np.intp)
    return image[centers_y[:, None], centers_x[None, :]].copy()


def _sample_median(image: np.ndarray, x_coords: list[int], y_coords: list[int]) -> np.ndarray:
    img = image.astype(np.float32) if image.dtype != np.float32 else image
    height, width = img.shape[:2]
    channels = 1 if img.ndim == 2 else img.shape[2]
    x = np.asarray(x_coords, dtype=np.int32)
    y = np.asarray(y_coords, dtype=np.int32)
    nx, ny = len(x) - 1, len(y) - 1
    out = np.empty((ny, nx, channels), dtype=np.float32)
    for row in range(ny):
        y0 = int(np.clip(y[row], 0, height))
        y1 = int(np.clip(y[row + 1], 0, height))
        if y1 <= y0:
            y1 = min(y0 + 1, height)
        for col in range(nx):
            x0 = int(np.clip(x[col], 0, width))
            x1 = int(np.clip(x[col + 1], 0, width))
            if x1 <= x0:
                x1 = min(x0 + 1, width)
            cell = img[y0:y1, x0:x1].reshape(-1, channels)
            out[row, col] = 0 if cell.shape[0] == 0 else np.median(cell, axis=0)
    if image.dtype == np.uint8:
        return np.clip(np.rint(out), 0, 255).astype(np.uint8)
    return out
