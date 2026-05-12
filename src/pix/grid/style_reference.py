"""AI Grid 手绘风格参考图标选择与摘要。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image

SUPPORTED_REFERENCE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class StyleReference:
    """一张可传给 VL 的手绘参考图标。"""

    path: Path
    label: str
    size: tuple[int, int]
    visible_pixels: int
    color_count: int
    bbox: tuple[int, int, int, int] | None

    @property
    def bbox_coverage(self) -> float:
        if self.bbox is None:
            return 0.0
        left, top, right, bottom = self.bbox
        area = max(1, self.size[0] * self.size[1])
        return ((right - left) * (bottom - top)) / area


def find_style_references(
    reference_dir: str | Path | None,
    *,
    query: str = "",
    limit: int = 3,
) -> list[StyleReference]:
    """从目录中选取少量手绘图标作为风格参考。

    排名优先级：文件名命中 prompt/素材名 > 中文字符重合度 > 稳定文件名排序。
    只返回可读取的图片，避免因为坏文件中断生成流程。
    """
    if not reference_dir or limit <= 0:
        return []
    root = Path(reference_dir).expanduser()
    if not root.exists() or not root.is_dir():
        return []

    candidates = [p for p in _iter_reference_files(root) if p.is_file()]
    ranked = sorted(candidates, key=lambda path: _rank_path(path, query), reverse=True)
    refs: list[StyleReference] = []
    for path in ranked:
        ref = _read_reference(path, root)
        if ref is None:
            continue
        refs.append(ref)
        if len(refs) >= limit:
            break
    return refs


def style_reference_context(references: Iterable[StyleReference]) -> str:
    refs = list(references)
    if not refs:
        return "- 手绘参考图标：未配置。"
    lines = ["- 手绘参考图标：后续参考图只用于学习低像素美术语言，不得照抄题材。"]
    for index, ref in enumerate(refs, start=1):
        bbox = list(ref.bbox) if ref.bbox else None
        lines.append(
            f"  {index}. {ref.label}：{ref.size[0]}x{ref.size[1]}，"
            f"可见像素 {ref.visible_pixels}，颜色 {ref.color_count}，"
            f"bbox={bbox}，bbox 占比 {ref.bbox_coverage:.0%}。"
        )
    return "\n".join(lines)


def _iter_reference_files(root: Path):
    for path in root.rglob("*"):
        if path.suffix.lower() in SUPPORTED_REFERENCE_EXTS:
            yield path


def _rank_path(path: Path, query: str) -> tuple[int, int, str]:
    normalized_query = query.lower().replace(" ", "")
    stem = path.stem.lower().replace(" ", "")
    score = 0
    if stem and stem in normalized_query:
        score += 10_000 + len(stem) * 20
    overlap = len(set(stem) & set(normalized_query))
    score += overlap * 10
    # 文件名越短越像具体素材名，优先于大而泛的目录名。
    specificity = max(0, 80 - len(stem))
    return score, specificity, str(path).lower()


def _read_reference(path: Path, root: Path) -> StyleReference | None:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            pixels = list(image.getdata())
    except Exception:
        return None

    visible = [pixel for pixel in pixels if pixel[3] > 0]
    try:
        label = str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        label = path.name
    return StyleReference(
        path=path,
        label=label,
        size=image.size,
        visible_pixels=len(visible),
        color_count=len(set(visible)),
        bbox=image.getbbox(),
    )
