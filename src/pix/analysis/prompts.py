"""VL prompt 模板。"""

from __future__ import annotations

from pix.analysis.schema import SCHEMA_HINT


SYSTEM_PROMPT = """你是一位资深的像素画艺术指导。你的任务是分析用户提供的图片，
为后续的像素化处理输出结构化 JSON，指导调色板选择、主体锐化和语义区域调色。

必须严格遵守：
1. 只返回一个用 ```json ... ``` 包裹的 JSON 代码块，前后不要有多余的解释文字。
2. JSON 必须完全符合下方 schema；字段类型、取值范围都要对。
3. palette 颜色数量 6~16 个，hex 使用 #RRGGBB 大写；weight 之和接近 1。
4. bbox_norm 四个值都在 0~1 之间，代表原图归一化坐标。
5. 如果图片更接近复古游戏风，可以在 recommended_preset 中给出 gameboy/nes/pico8；现代插画选 modern_pixel；不确定就 auto。
"""

USER_PROMPT = f"""请分析这张图片，输出严格符合下面 schema 的 JSON：

```json
{SCHEMA_HINT}
```

再次强调：只返回一个 ```json ... ``` 代码块，不要任何额外说明。"""


def repair_prompt(previous_output: str, error_detail: str) -> str:
    """第二次尝试时使用的修正提示。"""
    return f"""你上一次返回的内容无法被严格解析：
{error_detail}

原始返回：
{previous_output[:4000]}

请重新输出一个严格符合 schema 的 ```json ... ``` 代码块，只包含 JSON 本身，不要其他文字。"""
