# 示例

Convert the input image or described subject into a TRUE pixel-art game asset designed for game inventory/UI use, not a painted digital illustration. Subject: 冰霜之心. Asset type: game {asset_kind_label}. Subject kind: {subject_kind_label}. Canvas size must be exactly 16x16 pixels, where each pixel is one square grid cell. Use large, chunky readable pixels, limited colors, and a simple silhouette with very few noisy details. Simplicity is critical. Use no more than {max_colors} visible subject colors; background color does not count. For human characters, make sure the face is flat and no shadow. The subject must be centered with clear empty pixel rows around all edges for safe sprite padding and easy placement in game UI. Use a pure solid single-color background for chroma-key removal; choose a background color that is not close to any visible subject color, with color-distance greater than the removal tolerance ({key_tolerance} RGB Euclidean distance). No anti-aliasing or smoothing — every pixel must be a perfect square aligned to the grid. The output image should be pixel-perfect, each grid cell only contains one color. No text, no watermark, no UI frame, no labels.

## 解释

示例里的 `16x16` 位置必须根据用户实际选择的输出大小自动替换（例如 16x16、32x32、64x64），确保 prompt 中的 “Canvas size must be exactly ... pixels” 与最终像素网格一致。`{asset_kind_label}` / `{subject_kind_label}` 由用户选择的物品图标/UI 组件、单个道具/单个 UI 自动填入。`{max_colors}` / `{colors}` 必须根据用户在生图时实际选择的颜色数量上限填入，例如选择 12 色就写入 “no more than 12 visible subject colors”；`{key_tolerance}` 根据当前实际抠色最大色容差填入（例如网站素材生图默认 48），仅用于要求模型选择一个与主体所有可见颜色距离足够远的纯色背景，不固定为 #FF00FF 或任何指定 HEX；用户只需要输入 `Subject:` 后面的主体描述即可，输入框应提示“主体/描述”。

## 主页范例图谱

主页范例中的每个物品格也按同一规则维护 `主体 prompt`：右键某个 64×64 原图或 32×32 outline 图标时，只复制 `主体：` 后面的 prompt 描述片段，例如“物品名 + 题材单个道具 + 可识别造型/材质特征”，不只复制主体名称，也不带尺寸、风格或整组通用描述。
