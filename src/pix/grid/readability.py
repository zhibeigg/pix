"""Pixel Grid 低像素可读性评分。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Literal

from pix.grid.schema import PixelGrid

IssueLevel = Literal["blocking", "warning"]


@dataclass(frozen=True)
class GridReadabilityIssue:
    level: IssueLevel
    code: str
    message: str


@dataclass
class GridReadabilityReport:
    ok: bool
    width: int
    height: int
    visible_pixels: int
    visible_ratio: float
    bbox: tuple[int, int, int, int] | None
    bbox_coverage: float
    color_count: int
    component_count: int
    isolated_pixels: int
    outline_ratio: float
    highlight_ratio: float
    issues: list[GridReadabilityIssue] = field(default_factory=list)

    @property
    def blocking(self) -> list[GridReadabilityIssue]:
        return [issue for issue in self.issues if issue.level == "blocking"]

    @property
    def warnings(self) -> list[GridReadabilityIssue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "width": self.width,
            "height": self.height,
            "visible_pixels": self.visible_pixels,
            "visible_ratio": self.visible_ratio,
            "bbox": list(self.bbox) if self.bbox else None,
            "bbox_coverage": self.bbox_coverage,
            "color_count": self.color_count,
            "component_count": self.component_count,
            "isolated_pixels": self.isolated_pixels,
            "outline_ratio": self.outline_ratio,
            "highlight_ratio": self.highlight_ratio,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def evaluate_grid_readability(grid: PixelGrid, *, max_colors: int = 8) -> GridReadabilityReport:
    """检查低像素图标是否具备基本可读性。"""
    width = grid.canvas.width
    height = grid.canvas.height
    transparent = grid.canvas.transparent_index
    visible = [(x, y, value) for y, row in enumerate(grid.pixels) for x, value in enumerate(row) if value != transparent]
    visible_pixels = len(visible)
    canvas_area = max(1, width * height)
    visible_ratio = visible_pixels / canvas_area
    used_ids = {value for _, _, value in visible}
    color_count = len(used_ids)
    issues: list[GridReadabilityIssue] = []

    if not visible:
        issues.append(GridReadabilityIssue("blocking", "empty_subject", "没有可见主体像素"))
        return GridReadabilityReport(
            ok=False,
            width=width,
            height=height,
            visible_pixels=0,
            visible_ratio=0.0,
            bbox=None,
            bbox_coverage=0.0,
            color_count=color_count,
            component_count=0,
            isolated_pixels=0,
            outline_ratio=0.0,
            highlight_ratio=0.0,
            issues=issues,
        )

    xs = [x for x, _, _ in visible]
    ys = [y for _, y, _ in visible]
    bbox = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
    bbox_w = bbox[2] - bbox[0]
    bbox_h = bbox[3] - bbox[1]
    bbox_coverage = (bbox_w * bbox_h) / canvas_area
    short_side = max(1, min(width, height))
    min_axis_ratio = min(bbox_w, bbox_h) / short_side
    component_count = _component_count(grid.pixels, transparent)
    isolated_pixels = _isolated_count(grid.pixels, transparent)
    role_by_id = {color.id: color.role for color in grid.palette}
    outline_pixels = sum(1 for _, _, value in visible if role_by_id.get(value) == "outline")
    highlight_pixels = sum(1 for _, _, value in visible if role_by_id.get(value) == "highlight")
    outline_ratio = outline_pixels / max(1, visible_pixels)
    highlight_ratio = highlight_pixels / max(1, visible_pixels)

    if min_axis_ratio < 0.45:
        issues.append(GridReadabilityIssue("blocking", "subject_too_small", f"主体短轴只占画布 {min_axis_ratio:.0%}，16px 下会读不清"))
    if color_count > max_colors:
        issues.append(GridReadabilityIssue("blocking", "too_many_colors", f"颜色数 {color_count} 超过限制 {max_colors}"))
    if component_count > 4:
        issues.append(GridReadabilityIssue("blocking", "too_fragmented", f"主体碎成 {component_count} 个连通块"))
    touches_edges = bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= width or bbox[3] >= height
    if outline_pixels == 0 and touches_edges:
        issues.append(GridReadabilityIssue("blocking", "missing_outline", "主体触边且没有 outline 色"))

    if bbox_coverage < 0.28:
        issues.append(GridReadabilityIssue("warning", "bbox_small", f"主体 bbox 占比 {bbox_coverage:.0%} 偏小"))
    if bbox_coverage > 0.92:
        issues.append(GridReadabilityIssue("warning", "bbox_large", f"主体 bbox 占比 {bbox_coverage:.0%} 偏满"))
    if isolated_pixels:
        issues.append(GridReadabilityIssue("warning", "isolated_pixels", f"存在 {isolated_pixels} 个孤立像素"))
    if highlight_ratio > 0.16:
        issues.append(GridReadabilityIssue("warning", "highlight_too_much", f"高光像素占比 {highlight_ratio:.0%} 偏高"))
    if min(width, height) <= 8:
        if touches_edges:
            issues.append(GridReadabilityIssue("blocking", "tiny_touches_edge", "8x8 主体触边，缺少手绘图标留白"))
        if bbox_coverage > 0.82:
            issues.append(GridReadabilityIssue("blocking", "tiny_bbox_too_large", f"8x8 bbox 占比 {bbox_coverage:.0%}，过满像缩图块"))
        if visible_ratio > 0.62:
            issues.append(GridReadabilityIssue("blocking", "tiny_too_dense", f"8x8 可见像素占比 {visible_ratio:.0%}，过密像缩图噪点"))
    if touches_edges:
        issues.append(GridReadabilityIssue("warning", "touches_edge", "主体触碰画布边缘"))

    return GridReadabilityReport(
        ok=not any(issue.level == "blocking" for issue in issues),
        width=width,
        height=height,
        visible_pixels=visible_pixels,
        visible_ratio=visible_ratio,
        bbox=bbox,
        bbox_coverage=bbox_coverage,
        color_count=color_count,
        component_count=component_count,
        isolated_pixels=isolated_pixels,
        outline_ratio=outline_ratio,
        highlight_ratio=highlight_ratio,
        issues=issues,
    )


def format_blocking_issues(report: GridReadabilityReport) -> str:
    if not report.blocking:
        return "无阻塞问题"
    return "\n".join(f"- {issue.code}: {issue.message}" for issue in report.blocking)


def _component_count(pixels: list[list[int]], transparent: int) -> int:
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    visited: set[tuple[int, int]] = set()
    count = 0
    for y in range(height):
        for x in range(width):
            if pixels[y][x] == transparent or (x, y) in visited:
                continue
            count += 1
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                for nx, ny in _neighbors4(cx, cy):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if (nx, ny) in visited or pixels[ny][nx] == transparent:
                        continue
                    visited.add((nx, ny))
                    queue.append((nx, ny))
    return count


def _isolated_count(pixels: list[list[int]], transparent: int) -> int:
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    count = 0
    for y in range(height):
        for x in range(width):
            if pixels[y][x] == transparent:
                continue
            if not any(
                0 <= nx < width and 0 <= ny < height and pixels[ny][nx] != transparent
                for nx, ny in _neighbors8(x, y)
            ):
                count += 1
    return count


def _neighbors4(x: int, y: int):
    yield x - 1, y
    yield x + 1, y
    yield x, y - 1
    yield x, y + 1


def _neighbors8(x: int, y: int):
    for ny in range(y - 1, y + 2):
        for nx in range(x - 1, x + 2):
            if nx == x and ny == y:
                continue
            yield nx, ny
