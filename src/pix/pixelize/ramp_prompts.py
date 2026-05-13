"""Ramp 调色板 VL prompt 模板。

让 VL 按"色相组 × 明度阶梯"返回结构化调色板，而不是自由采样。
输出必须可以直接映射到 Python 量化链路。
"""

from __future__ import annotations


RAMP_SYSTEM_PROMPT = """你是资深像素画美术指导。你的任务是给定一张参考图，
为其设计一套"手绘像素画调色板"，要求按色相组 × 明度阶梯返回结构化 JSON。

核心要求：
1. 不是从图里机械取色，而是基于图中主体、材质、光源重新设计一套手绘 ramp。
2. 每个 ramp 代表一种"主色相 + 材质"，在色相轴上保持一致，明度沿阶梯递增。
3. 每个 ramp 从暗到亮至少给 3 个 step，常见 4 个：outline → shadow → mid → highlight。
4. outline 明度必须明显低于 shadow（L* 差 ≥ 12），highlight 明度必须明显高于 mid（L* 差 ≥ 12）。
5. 同一 ramp 内部色相（H）漂移不超过 25°，避免"阴影偏红而高光偏绿"的塑料感。
6. 所有颜色都用 #RRGGBB 大写，不包含透明。
7. 所有 ramps 的 step 总数加起来不能超过 max_colors。
8. 如果图里出现多种材质（例如金属 + 宝石 + 木头），可以给 2~3 个 ramp；单材质图标 1 个 ramp 就够。

只返回一个 JSON 对象，不要 Markdown，不要解释。
"""


RAMP_SCHEMA_HINT = """{
  "ramps": [
    {
      "name": "主色相简短标签，例如 metal / emerald / wood",
      "hue": "主色相名（英文单词，小写）",
      "steps": [
        {"hex": "#RRGGBB", "role": "outline"},
        {"hex": "#RRGGBB", "role": "shadow"},
        {"hex": "#RRGGBB", "role": "mid"},
        {"hex": "#RRGGBB", "role": "highlight"}
      ]
    }
  ]
}"""


def build_ramp_user_prompt(
    *,
    max_colors: int,
    output_size: tuple[int, int],
    description: str = "",
    draft_palette_hex: list[str] | None = None,
) -> str:
    """构造发给 VL 的 user 消息正文。"""
    width, height = output_size
    hints: list[str] = []
    if description.strip():
        hints.append(f"- 语义提示：{description.strip()[:500]}")
    if draft_palette_hex:
        sample = ", ".join(draft_palette_hex[:8])
        hints.append(f"- 参考底色（仅作色相参考，不要照搬）：{sample}")
    hint_text = "\n".join(hints) if hints else "- 无额外语义提示。"

    return f"""请为这张参考图设计一套 {width}x{height} 像素画用的 ramp 调色板。

{hint_text}

约束：
- 所有 ramp 的 step 总数 ≤ {max_colors}。
- 每个 ramp 至少 3 个 step，最多 6 个 step。
- 相邻 step 的 L*（CIELAB 明度）差不得低于 10。
- outline step 的 L* 不超过 30；highlight step 的 L* 不低于 70（除非画面整体偏暗需要压低）。
- 如果图里明显有多种材质，可以拆成多个 ramp。

只返回符合下列结构的 JSON，不要 Markdown：
```
{RAMP_SCHEMA_HINT}
```
"""


def build_ramp_repair_prompt(
    *,
    max_colors: int,
    output_size: tuple[int, int],
    previous_output: str,
    error_detail: str,
) -> str:
    """schema 校验失败或 L* 差不够时的修正提示。"""
    width, height = output_size
    return f"""上一次返回的 ramp 不合格：
{error_detail}

请重新设计一套 {width}x{height} 的 ramp 调色板，严格满足：
- 所有 ramp 的 step 总数 ≤ {max_colors}；
- 每个 ramp 至少 3 个 step；
- outline → shadow → mid → highlight 明度必须严格递增，相邻 L* 差 ≥ 10；
- 同一 ramp 色相漂移 ≤ 25°；
- hex 使用 #RRGGBB 大写。

上一次输出：
{previous_output[:3500]}

只返回 JSON。"""
