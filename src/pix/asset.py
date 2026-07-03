"""游戏素材直出与资源校验辅助。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

import numpy as np
from PIL import Image

from pix.prompt_style import compile_style_profile


IssueLevel = Literal["error", "warning"]
AssetGenerationPolicy = Literal["extract"]
AssetPaletteMode = Literal["auto", "ramp", "kmeans"]
TileTextureKind = Literal[
    "auto",
    "generic_texture",
    "terrain_ground",
    "path_floor",
    "wall_surface",
    "wood_planks",
    "water_liquid",
    "foliage_canopy",
    "roof_tile",
    "metal_panel",
    "fabric_carpet",
]


class AssetSizePolicyError(ValueError):
    """素材尺寸不符合直出策略。"""


def resolve_asset_generation_policy(size: tuple[int, int]) -> AssetGenerationPolicy:
    """返回游戏素材直出策略。

    规则：仅支持 ≥16×16 的素材，统一走 Pixel Grid extract 流程。AI Grid / 普通 resize
    分支已在 0.60.0 版本删除，更小尺寸由调用方负责再做下采样。
    """
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise AssetSizePolicyError("素材尺寸必须为正整数")
    if width < 16 or height < 16:
        raise AssetSizePolicyError("最低支持 16x16 素材")
    return "extract"


@dataclass(frozen=True)
class AssetSizeStrategy:
    """按目标尺寸推荐的 pipeline 策略；调用方仍可显式覆盖。"""

    palette_mode: str
    grid_mode: str  # 仅 "extract"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "palette_mode": self.palette_mode,
            "grid_mode": self.grid_mode,
            "notes": self.notes,
        }


def resolve_size_strategy(size: tuple[int, int]) -> AssetSizeStrategy:
    """所有支持尺寸统一推荐 extract + auto/K-means。

    AI Grid / 普通 resize 分支已废弃；默认保留经典单图纯色背景效果：
    从源图反推像素格 → 按原始 K-means/auto 调色 → 精确渲染。
    """
    return AssetSizeStrategy(
        palette_mode="auto",
        grid_mode="extract",
        notes="extract Pixel Grid + auto/K-means（经典单图纯色背景风格，AI Grid / resize 路径已删除）",
    )


@dataclass(frozen=True)
class AssetValidationIssue:
    level: IssueLevel
    code: str
    message: str


@dataclass
class AssetValidationReport:
    path: Path
    size: tuple[int, int] | None = None
    mode: str | None = None
    visible_color_count: int = 0
    alpha_bbox: tuple[int, int, int, int] | None = None
    issues: list[AssetValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    @property
    def warnings(self) -> list[AssetValidationIssue]:
        return [issue for issue in self.issues if issue.level == "warning"]

    @property
    def errors(self) -> list[AssetValidationIssue]:
        return [issue for issue in self.issues if issue.level == "error"]


def safe_asset_filename(name: str, fallback: str = "asset") -> str:
    """把资源名转换成适合跨平台文件名的字符串，保留中文。"""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name.strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip(" ._")
    return cleaned or fallback


ASSET_KIND_LABELS: dict[str, str] = {
    "item_icon": "item icon",
    "ui_component": "UI component",
    "tile_texture": "tileable pixel texture",
    "game_logo": "game logo",
    "dual_grid": "dual-grid tileset",
    "character": "character reference",
}
SUBJECT_KIND_LABELS: dict[str, str] = {
    "single_prop": "single prop",
    "single_ui": "single UI element",
    "tileable_pattern": "seamlessly tileable pattern",
    "logo_mark": "logo title mark",
    "single_character": "single character",
}
COMPATIBLE_SUBJECT_KINDS: dict[str, set[str]] = {
    "item_icon": {"single_prop"},
    "ui_component": {"single_ui"},
    "tile_texture": {"tileable_pattern"},
    "game_logo": {"logo_mark"},
    "character": {"single_character"},
}


@dataclass(frozen=True)
class AssetPromptProfile:
    default_subject_kind: str
    usage_label: str
    placement_context: str
    forbidden_elements: str


ASSET_PROMPT_PROFILES: dict[str, AssetPromptProfile] = {
    "item_icon": AssetPromptProfile(
        default_subject_kind="single_prop",
        usage_label="inventory use",
        placement_context="easy placement in inventory slots",
        forbidden_elements="No text, no watermark, no frame, no labels.",
    ),
    "ui_component": AssetPromptProfile(
        default_subject_kind="single_ui",
        usage_label="game interface use",
        placement_context="easy placement in HUD or menu layouts",
        forbidden_elements="No text, no watermark, no unrelated outer frame, no labels.",
    ),
    "game_logo": AssetPromptProfile(
        default_subject_kind="logo_mark",
        usage_label="game title screen, main menu, splash screen, or HUD branding use",
        placement_context="easy placement on transparent title screens, menu headers, splash screens, or HUD brand areas",
        forbidden_elements=(
            "Only use the exact short title, acronym, or brand text provided in the subject if text is needed; "
            "do not invent extra words. No watermark, no mockup scene, no paragraph text, no tiny unreadable text, "
            "no labels outside the logo, no unrelated frame."
        ),
    ),
    "tile_texture": AssetPromptProfile(
        default_subject_kind="tileable_pattern",
        usage_label="seamless tile-map / wallpaper use",
        # 关键：要求图案铺满画布、四边可拼接，禁止主体居中留白
        placement_context="filling the entire canvas with a seamlessly tileable pattern; the left edge must connect to the right edge and the top edge must connect to the bottom edge without seams",
        forbidden_elements="No text, no watermark, no centered subject, no transparent background, no border, no frame, no vignette, no padding around the edges.",
    ),
    "character": AssetPromptProfile(
        default_subject_kind="single_character",
        usage_label="reusable character reference and sprite-animation source use",
        placement_context="easy reuse as a character reference for later sprite sheets, with the full character readable in one centered image",
        forbidden_elements=(
            "No text, no watermark, no frame, no labels, no inventory icon pedestal, no UI chrome, "
            "no cropped head-only portrait, no multiple characters, no unrelated props as the main subject."
        ),
    ),
}


@dataclass(frozen=True)
class TileTexturePromptProfile:
    label: str
    prompt_rules: str
    keywords: tuple[str, ...]


TILE_TEXTURE_KIND_LABELS: dict[str, str] = {
    "auto": "auto-detected texture type",
    "generic_texture": "generic tileable surface texture",
    "terrain_ground": "top-down terrain ground",
    "path_floor": "walkable path or floor",
    "wall_surface": "wall or rock surface",
    "wood_planks": "wood plank or bark surface",
    "water_liquid": "water or liquid surface",
    "foliage_canopy": "foliage, leaf, or grass canopy",
    "roof_tile": "roof tile or shingle surface",
    "metal_panel": "metal panel or sci-fi floor",
    "fabric_carpet": "fabric, carpet, or woven pattern",
}


TILE_TEXTURE_PROMPT_PROFILES: dict[str, TileTexturePromptProfile] = {
    "generic_texture": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["generic_texture"],
        prompt_rules=(
            "Texture subtype rules: make an even repeatable game-map material with balanced detail density; "
            "avoid a single landmark, emblem, object, creature, horizon, cast shadow, or focal center that would reveal repetition."
        ),
        keywords=(),
    ),
    "terrain_ground": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["terrain_ground"],
        prompt_rules=(
            "Texture subtype rules: top-down RPG terrain ground tile. Use organic granular variation such as small grass blades, dirt speckles, pebbles, snow grains, sand noise, or moss flecks; "
            "keep details evenly scattered and walkable, with no centered tree, rock pile, path edge, horizon, wall face, or large object."
        ),
        keywords=(
            "grass",
            "grassland",
            "meadow",
            "ground",
            "terrain",
            "dirt",
            "soil",
            "mud",
            "sand",
            "snow",
            "moss",
            "pebble",
            "gravel",
            "草",
            "草地",
            "地表",
            "地面",
            "泥土",
            "泥地",
            "沙地",
            "沙漠",
            "雪地",
            "苔藓",
            "碎石",
            "砾石",
        ),
    ),
    "path_floor": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["path_floor"],
        prompt_rules=(
            "Texture subtype rules: top-down walkable path or floor tile. Use readable repeated stones, bricks, slabs, cobbles, ceramic tiles, or indoor floor pieces; "
            "align grout lines and cracks across opposite edges, keep perspective flat top-down, and avoid walls, doors, rugs with borders, or a centered decorative emblem."
        ),
        keywords=(
            "path",
            "road",
            "floor",
            "pavement",
            "cobblestone",
            "stone road",
            "slab",
            "brick floor",
            "tile floor",
            "tiles",
            "plaza",
            "路",
            "道路",
            "小路",
            "石板",
            "石板路",
            "砖路",
            "地砖",
            "地板",
            "铺路",
            "路面",
            "广场",
        ),
    ),
    "wall_surface": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["wall_surface"],
        prompt_rules=(
            "Texture subtype rules: vertical wall, cliff, cave, brick wall, or rock-face surface. Use front-facing courses, cracks, blocks, mortar, moss streaks, or rock strata with one consistent upper-left light direction; "
            "do not show floor perspective, sky, windows, doors, torches, shelves, or a complete building facade."
        ),
        keywords=(
            "wall",
            "brick wall",
            "stone wall",
            "cliff",
            "rock face",
            "cave wall",
            "castle wall",
            "岩壁",
            "墙",
            "墙壁",
            "砖墙",
            "石墙",
            "城墙",
            "山壁",
            "洞壁",
            "峭壁",
            "悬崖",
        ),
    ),
    "wood_planks": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["wood_planks"],
        prompt_rules=(
            "Texture subtype rules: wooden plank, timber, bark, or log surface. Use long pixelated grain bands, knots, cracks, and plank seams that continue across the left/right and top/bottom edges; "
            "keep boards as texture strips rather than a single table, crate, sign, frame, or centered log."
        ),
        keywords=(
            "wood",
            "wooden",
            "plank",
            "timber",
            "bark",
            "log",
            "deck",
            "木",
            "木板",
            "木地板",
            "木墙",
            "树皮",
            "原木",
            "甲板",
            "木纹",
        ),
    ),
    "water_liquid": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["water_liquid"],
        prompt_rules=(
            "Texture subtype rules: animated-ready liquid surface base tile. Use small repeating waves, ripples, foam pixels, glow streaks, bubbles, or viscous swirls that continue across all edges; "
            "avoid shorelines, islands, boats, waterfalls, characters, and large one-off highlight shapes."
        ),
        keywords=(
            "water",
            "river",
            "lake",
            "sea",
            "ocean",
            "liquid",
            "lava",
            "magma",
            "poison",
            "slime",
            "acid",
            "swamp water",
            "水",
            "水面",
            "河流",
            "湖水",
            "海水",
            "液体",
            "岩浆",
            "熔岩",
            "毒液",
            "酸液",
            "史莱姆",
            "沼泽水",
        ),
    ),
    "foliage_canopy": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["foliage_canopy"],
        prompt_rules=(
            "Texture subtype rules: leafy canopy, bush, hedge, grass clump, or dense foliage overlay. Build mottled clusters of leaves and tiny branch gaps with varied greens; "
            "keep it as a continuous coverage texture, with no centered tree trunk, flower bouquet, single plant icon, or transparent holes."
        ),
        keywords=(
            "foliage",
            "leaf",
            "leaves",
            "bush",
            "hedge",
            "canopy",
            "shrub",
            "ivy",
            "vines",
            "树叶",
            "叶子",
            "叶片",
            "灌木",
            "树冠",
            "植被",
            "藤蔓",
            "爬山虎",
            "草丛",
            "绿篱",
        ),
    ),
    "roof_tile": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["roof_tile"],
        prompt_rules=(
            "Texture subtype rules: roof tile, shingle, thatch, or ceramic roof surface. Use repeated rows with clear overlap rhythm and aligned row offsets across edges; "
            "avoid chimneys, skylights, roof outlines, house silhouettes, gutters, or ground/floor perspective."
        ),
        keywords=(
            "roof",
            "rooftile",
            "roof tile",
            "shingle",
            "thatch",
            "瓦",
            "屋顶",
            "瓦片",
            "瓦面",
            "琉璃瓦",
            "茅草屋顶",
            "屋瓦",
        ),
    ),
    "metal_panel": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["metal_panel"],
        prompt_rules=(
            "Texture subtype rules: metal panel, industrial floor, sci-fi wall, or machinery plating. Use repeated panel seams, rivets, bolts, scratches, vents, warning-stripe fragments, or subtle wear that lines up at tile edges; "
            "avoid readable text, logos, screens, buttons as focal objects, weapons, or a single machine part."
        ),
        keywords=(
            "metal",
            "steel",
            "iron",
            "panel",
            "sci-fi",
            "scifi",
            "industrial",
            "machine",
            "rivets",
            "bolts",
            "vent",
            "金属",
            "钢铁",
            "铁板",
            "金属板",
            "面板",
            "机械",
            "科幻",
            "工业",
            "铆钉",
            "螺丝",
            "通风口",
        ),
    ),
    "fabric_carpet": TileTexturePromptProfile(
        label=TILE_TEXTURE_KIND_LABELS["fabric_carpet"],
        prompt_rules=(
            "Texture subtype rules: fabric, carpet, rug, tapestry, or woven decorative pattern. Use pixelated weave, thread noise, small motifs, stripes, or geometric repeats that cross every edge; "
            "avoid outer borders, fringe, a single central medallion, readable symbols, or an object-like cloth silhouette."
        ),
        keywords=(
            "fabric",
            "cloth",
            "carpet",
            "rug",
            "tapestry",
            "woven",
            "textile",
            "linen",
            "布",
            "布料",
            "织物",
            "地毯",
            "毯子",
            "挂毯",
            "编织",
            "纺织",
            "麻布",
            "纹样",
        ),
    ),
}


def _canonical_asset_prompt(
    name: str,
    width: int,
    height: int,
    key_tolerance: int,
    max_colors: int,
    asset_kind_label: str,
    subject_kind_label: str,
    profile: AssetPromptProfile,
) -> str:
    return (
        f"Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} "
        f"designed for {profile.usage_label}, not a painted digital illustration. "
        f"Subject: {name}. Subject kind: {subject_kind_label}. "
        f"Canvas size must be exactly {width}x{height} pixels, "
        "where each pixel is one square cell of a conceptual pixel grid — do NOT draw any visible grid lines, "
        "gridlines, graph-paper or checkerboard pattern. Use large, chunky readable pixels, "
        "limited colors, and a simple silhouette. "
        f"Use no more than {max_colors} visible subject colors; background color does not count. "
        "For human characters, make sure the face is flat and no shadow. "
        "The subject must be centered with clear empty pixel rows around all edges for safe sprite "
        f"padding and {profile.placement_context}. "
        "Fill the ENTIRE canvas edge to edge with one single flat uniform background color for chroma-key "
        "removal: the background must be perfectly solid with NO gradient, NO vignette, NO lighting or shading, "
        "NO drawn grid lines or graph paper, and NO border or frame; it must reach all four image edges. "
        "First decide the subject's full color palette, THEN choose the background color: pick a single flat "
        "color that MAXIMIZES the MINIMUM RGB Euclidean distance to EVERY visible subject color (a maximin "
        "choice), strongly preferring a saturated opposite or complementary hue that the subject does not use "
        "at all. This minimum distance must be far greater than the removal tolerance "
        f"({key_tolerance} RGB Euclidean distance), targeting at least 150 RGB Euclidean distance, so the "
        "background never blends with the subject and keys out cleanly. "
        "No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the conceptual pixel grid. "
        "The output image should be pixel-perfect, each cell only contains one color. "
        f"{profile.forbidden_elements}"
    )


def _canonical_tile_prompt(
    name: str,
    width: int,
    height: int,
    max_colors: int,
    asset_kind_label: str,
    subject_kind_label: str,
    profile: AssetPromptProfile,
    texture_profile: TileTexturePromptProfile,
) -> str:
    """平铺纹理专用 prompt：铺满画布、四边无缝拼接、不留透明背景。"""
    return (
        f"Create a TRUE pixel-art {asset_kind_label} (a {subject_kind_label}). "
        f"Subject / theme: {name}. "
        f"Texture subtype: {texture_profile.label}. "
        f"Canvas size must be exactly {width}x{height} pixels, where each pixel is one square grid cell. "
        f"The pattern must completely fill the entire canvas — every pixel of the {width}x{height} canvas is part of the texture, "
        "with NO transparent areas, NO solid background border, NO vignette, NO empty padding rows around the edges. "
        f"The texture must be seamlessly tileable: the left edge must continue smoothly into the right edge, "
        "and the top edge must continue smoothly into the bottom edge, so that placing the same image side-by-side reveals no visible seam. "
        f"{texture_profile.prompt_rules} "
        f"Use no more than {max_colors} visible colors total. "
        "Use large, chunky readable pixels, limited palette, no painterly blending, no anti-aliasing, no soft brush, no smoothing. "
        "Every pixel must be a perfect square aligned to the grid; each grid cell contains exactly one color. "
        f"{profile.forbidden_elements}"
    )


def _canonical_character_three_view_prompt(
    name: str,
    width: int,
    height: int,
    key_tolerance: int,
    max_colors: int,
    asset_kind_label: str,
    subject_kind_label: str,
    profile: AssetPromptProfile,
) -> str:
    """角色三视图专用 prompt：一张横向排列的正/侧/背三视图拼合图（turnaround sheet）。

    `width` 传入时已是单视图宽度的 3 倍（画布横向 3 倍宽），单视图宽度 = width // 3。
    强调同一角色、姿势/比例/调色板一致、三视图等宽排列、视图间留纯背景间隔，
    并保留纯色背景 chroma-key 与像素网格约束，使成品仍可整体抠色、居中复用。
    """
    view_width = max(1, width // 3)
    return (
        f"Convert the input image or described subject into a TRUE pixel-art game {asset_kind_label} "
        f"designed for {profile.usage_label}, not a painted digital illustration. "
        f"Subject: {name}. Subject kind: {subject_kind_label}. "
        "Draw a CHARACTER TURNAROUND SHEET that shows the EXACT SAME single character from three views "
        "arranged strictly left to right in this order: FRONT view (facing the viewer), SIDE view (facing "
        "left in profile), and BACK view (facing away). "
        f"Canvas size must be exactly {width}x{height} pixels, split into three equal-width columns of "
        f"{view_width}x{height} pixels each; place exactly one view centered inside each column with clear "
        "empty background pixels around it. "
        "All three views must be the SAME character at the SAME scale, height, proportions, costume, and color "
        "palette — only the facing direction changes. Keep the feet/baseline aligned across all three views. "
        "Each pixel is one square cell of a conceptual pixel grid — do NOT draw any visible grid lines, "
        "gridlines, graph-paper or checkerboard pattern. Use large, chunky readable pixels, limited colors, "
        "and a simple silhouette per view. "
        f"Use no more than {max_colors} visible subject colors total across all three views; background color "
        "does not count. For human characters, make sure the face is flat and no shadow. "
        "Fill the ENTIRE canvas edge to edge with one single flat uniform background color for chroma-key "
        "removal, including the gaps between the three views: the background must be perfectly solid with NO "
        "gradient, NO vignette, NO lighting or shading, NO drawn grid lines or graph paper, and NO border or "
        "frame; it must reach all four image edges. "
        "First decide the character's full color palette, THEN choose the background color: pick a single flat "
        "color that MAXIMIZES the MINIMUM RGB Euclidean distance to EVERY visible subject color (a maximin "
        "choice), strongly preferring a saturated opposite or complementary hue that the character does not use "
        "at all. This minimum distance must be far greater than the removal tolerance "
        f"({key_tolerance} RGB Euclidean distance), targeting at least 150 RGB Euclidean distance, so the "
        "background never blends with the character and keys out cleanly. "
        "No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the conceptual pixel grid. "
        "The output image should be pixel-perfect, each cell only contains one color. "
        "No text, no watermark, no frame, no labels, no view captions, no arrows, no extra poses, "
        "no inventory icon pedestal, no UI chrome, no cropped head-only portrait, no additional characters "
        "beyond the three required views of the same character."
    )


def _asset_kind_key(value: str) -> str:
    key = (value or "item_icon").strip()
    return key if key in ASSET_KIND_LABELS else "item_icon"


def _subject_kind_key(asset_kind: str, subject_kind: str) -> str:
    profile = ASSET_PROMPT_PROFILES[asset_kind]
    key = (subject_kind or profile.default_subject_kind).strip()
    if key not in COMPATIBLE_SUBJECT_KINDS[asset_kind]:
        return profile.default_subject_kind
    return key


def resolve_tile_texture_kind(
    requested: str = "auto",
    *,
    name: str = "",
    extra_prompt: str = "",
) -> str:
    """解析平铺纹理细分类型；auto 会按主题关键词轻量推断。"""
    key = (requested or "auto").strip()
    if key in TILE_TEXTURE_PROMPT_PROFILES:
        return key
    if key and key != "auto":
        return "generic_texture"

    haystack = f"{name}\n{extra_prompt}".casefold()
    inference_order = (
        "wall_surface",
        "water_liquid",
        "roof_tile",
        "wood_planks",
        "metal_panel",
        "fabric_carpet",
        "path_floor",
        "foliage_canopy",
        "terrain_ground",
    )
    for candidate in inference_order:
        profile = TILE_TEXTURE_PROMPT_PROFILES[candidate]
        if any(keyword.casefold() in haystack for keyword in profile.keywords):
            return candidate
    return "generic_texture"


def tile_texture_kind_label(kind: str) -> str:
    return TILE_TEXTURE_KIND_LABELS.get(kind, TILE_TEXTURE_KIND_LABELS["generic_texture"])


def _legacy_template_to_type_aware(template: str) -> str:
    return (
        template.replace(
            "TRUE pixel-art game asset designed for game inventory/UI use",
            "TRUE pixel-art game {asset_kind_label} designed for {asset_usage_label}",
        )
        .replace("easy placement in game UI", "{placement_context}")
        .replace("No text, no watermark, no UI frame, no labels.", "{forbidden_elements}")
    )


def build_asset_prompt(
    template: str,
    name: str,
    *,
    size: tuple[int, int],
    extra_prompt: str = "",
    asset_kind: str = "item_icon",
    subject_kind: str = "single_prop",
    texture_kind: str = "auto",
    character_views: str = "single",
    key_color: str = "#00FF00",
    key_tolerance: int = 48,
    max_colors: int = 16,
    style_profile: Mapping[str, object] | None = None,
) -> str:
    """按游戏素材模板生成最终生图 prompt。

    当 asset_kind=character 且 character_views="three_view" 时，走角色三视图专用 prompt，
    此时 `size` 的宽度应已是单视图宽度的 3 倍（由调用方在计算 output_size 时横向 ×3）。
    """
    width, height = size
    size_label = f"{width}×{height}"
    asset_kind_key = _asset_kind_key(asset_kind)
    subject_kind_key = _subject_kind_key(asset_kind_key, subject_kind)
    profile = ASSET_PROMPT_PROFILES[asset_kind_key]
    asset_kind_label = ASSET_KIND_LABELS[asset_kind_key]
    subject_kind_label = SUBJECT_KIND_LABELS[subject_kind_key]
    canvas_shape = "正方形画幅" if width == height else f"适配 {size_label} 画幅"
    values = {
        "name": name,
        "width": width,
        "height": height,
        "size_label": size_label,
        "asset_kind": asset_kind_key,
        "asset_kind_label": asset_kind_label,
        "asset_usage_label": profile.usage_label,
        "subject_kind": subject_kind_key,
        "subject_kind_label": subject_kind_label,
        "placement_context": profile.placement_context,
        "forbidden_elements": profile.forbidden_elements,
        "canvas_shape": canvas_shape,
        "green": key_color,
        "key_color": key_color,
        "key_tolerance": int(key_tolerance),
        "colors": int(max_colors),
        "max_colors": int(max_colors),
    }
    template_text = _legacy_template_to_type_aware((template or "").strip())
    is_tile = asset_kind_key == "tile_texture"
    is_character_three_view = asset_kind_key == "character" and character_views == "three_view"
    if is_tile:
        # 平铺纹理不复用普通 prompt 模板，用专用模板（强调"铺满+无缝"，不需要 chroma-key 占位符）
        resolved_texture_kind = resolve_tile_texture_kind(
            texture_kind,
            name=name,
            extra_prompt=extra_prompt,
        )
        texture_profile = TILE_TEXTURE_PROMPT_PROFILES[resolved_texture_kind]
        prompt = _canonical_tile_prompt(
            name,
            width,
            height,
            int(max_colors),
            asset_kind_label,
            subject_kind_label,
            profile,
            texture_profile,
        )
    elif is_character_three_view:
        # 角色三视图不复用通用/用户模板（会退化成单图措辞），走专用三视图 prompt。
        prompt = _canonical_character_three_view_prompt(
            name,
            width,
            height,
            int(key_tolerance),
            int(max_colors),
            asset_kind_label,
            subject_kind_label,
            profile,
        )
    elif template_text:
        try:
            prompt = template_text.format(**values)
        except Exception:
            prompt = _canonical_asset_prompt(
                name,
                width,
                height,
                int(key_tolerance),
                int(max_colors),
                asset_kind_label,
                subject_kind_label,
                profile,
            )
    else:
        prompt = _canonical_asset_prompt(
            name,
            width,
            height,
            int(key_tolerance),
            int(max_colors),
            asset_kind_label,
            subject_kind_label,
            profile,
        )
    style_prompt = compile_style_profile(style_profile).prompt
    if style_prompt:
        prompt = f"{prompt.strip()} {style_prompt}"
    if extra_prompt.strip():
        prompt = f"{prompt.strip()} {extra_prompt.strip()}"
    return prompt.strip()


def validate_asset_image(
    path: str | Path,
    *,
    expected_size: tuple[int, int] | None = None,
    max_colors: int | None = 16,
    require_alpha: bool = True,
    require_transparency: bool = True,
    alpha_threshold: int = 8,
    min_subject_coverage: float = 0.06,
    max_subject_coverage: float = 0.92,
) -> AssetValidationReport:
    """检查 PNG 是否适合作为小尺寸游戏素材。"""
    p = Path(path)
    report = AssetValidationReport(path=p)

    if p.suffix.lower() != ".png":
        report.issues.append(AssetValidationIssue("error", "not_png", "文件扩展名不是 .png"))

    try:
        with Image.open(p) as opened:
            original_bands = opened.getbands()
            original_has_transparency = "transparency" in opened.info
            image = opened.convert("RGBA")
            report.size = opened.size
            report.mode = opened.mode
    except Exception as exc:
        report.issues.append(AssetValidationIssue("error", "cannot_open", f"无法读取图片：{exc}"))
        return report

    if expected_size is not None and report.size != expected_size:
        report.issues.append(
            AssetValidationIssue(
                "error",
                "size_mismatch",
                f"尺寸应为 {expected_size[0]}x{expected_size[1]}，实际为 {report.size[0]}x{report.size[1]}",
            )
        )

    original_has_alpha = "A" in original_bands or original_has_transparency
    if require_alpha and not original_has_alpha:
        report.issues.append(
            AssetValidationIssue("error", "missing_alpha", "图片不含 alpha/透明通道")
        )

    rgba = np.asarray(image, dtype=np.uint8)
    alpha = rgba[..., 3]
    visible_mask = alpha > max(0, int(alpha_threshold))
    if visible_mask.any():
        visible_rgb = rgba[..., :3][visible_mask]
        report.visible_color_count = int(np.unique(visible_rgb.reshape(-1, 3), axis=0).shape[0])
    else:
        report.visible_color_count = 0

    if max_colors is not None and report.visible_color_count > max_colors:
        report.issues.append(
            AssetValidationIssue(
                "error",
                "too_many_colors",
                f"可见颜色数 {report.visible_color_count} 超过限制 {max_colors}",
            )
        )

    if require_transparency and int(alpha.min()) > 0:
        report.issues.append(
            AssetValidationIssue("error", "no_transparency", "图片没有透明背景像素")
        )

    semi_transparent = int(((alpha > 0) & (alpha < 255)).sum())
    if semi_transparent > 0:
        report.issues.append(
            AssetValidationIssue(
                "warning",
                "semi_transparent_pixels",
                f"存在 {semi_transparent} 个半透明像素，像素游戏中可能形成脏边",
            )
        )

    mask_img = Image.fromarray(np.where(visible_mask, 255, 0).astype(np.uint8), mode="L")
    report.alpha_bbox = mask_img.getbbox()
    if report.alpha_bbox is None:
        report.issues.append(
            AssetValidationIssue("error", "empty_subject", "没有检测到可见主体像素")
        )
        return report

    width, height = report.size or image.size
    left, top, right, bottom = report.alpha_bbox
    bbox_area = max(1, right - left) * max(1, bottom - top)
    coverage = bbox_area / max(1, width * height)
    if coverage < min_subject_coverage:
        report.issues.append(
            AssetValidationIssue(
                "warning", "subject_too_small", f"主体 bbox 占比 {coverage:.1%}，可能过小"
            )
        )
    if coverage > max_subject_coverage:
        report.issues.append(
            AssetValidationIssue(
                "warning", "subject_too_large", f"主体 bbox 占比 {coverage:.1%}，可能过满"
            )
        )
    if left <= 0 or top <= 0 or right >= width or bottom >= height:
        report.issues.append(
            AssetValidationIssue("warning", "subject_touches_edge", "主体触碰画布边缘")
        )

    return report
