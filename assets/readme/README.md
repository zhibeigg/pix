# README 视觉素材

`hero.png` 是首页发布用的静态拼版，排版源为 [`source/hero-layout.svg`](source/hero-layout.svg)。图片来自项目已有输出，没有新增 AI 生图，也没有改变素材颜色或动作顺序。

## 内容与视觉方向

- 读者：游戏开发者、独立工作室与自行部署服务的开发者。
- 项目价值：将 AI 图像生成、像素后处理和资产管理接到同一工作流程。
- 证据：仓库中实际生成的物品、技能书、纹理、Logo 与九帧 Sprite Sheet。
- 首次操作：启动 API、Worker 和前端，创建管理员，配置供应商后生成素材。
- 主题：像素素材图鉴；原尺寸像素与透明画布是视觉线索。
- 色彩：石墨 `#17191d`、前景 `#f4f5f8`、品牌紫 `#9e8bff`、薄荷绿 `#83d9b4`、辅助灰 `#a7aab4`。
- 排版：系统无衬线字体，104 / 36 / 26 / 20 字号层级；1200 单位画布，1 单位分隔线，宽松留白。

## 来源与处理

所有路径相对于仓库根目录，授权见 [ASSETS.md](../../ASSETS.md)。

| 素材 | 来源 |
| --- | --- |
| 项目标识 | `apps/web/public/pix-logo-64.png` |
| 剑、书、药水、法杖 | `apps/web/public/homepage-examples/items/09_highfantasy_item_01.png` 至 `04.png` |
| 仙侠物品 | `apps/web/public/homepage-examples/items/02_xianxia_item_02.png` |
| 技能书 | `apps/web/public/homepage-examples/showcase/skillbook_ciyuanzhan_image2_job10_pixelized.png` |
| 苔藓石板 | `apps/web/public/homepage-examples/textures/01_cobblestone_moss.png`，以原图重复铺设 3 × 3 |
| 创世录 Logo | `apps/web/public/homepage-examples/showcase/logo_chuangshilu_image2_job18_pixelized.png` |
| 骑士动作 | `apps/web/public/homepage-examples/sprites/04_knight_1x9.png`，完整保留九帧 |

## 重新渲染

使用 Node.js、`playwright`（含 Chromium）和 `sharp`，从仓库根目录运行：

```bash
node assets/readme/source/render.cjs
```

工具依赖可安装在独立目录，通过 `NODE_PATH` 指向其 `node_modules`，无需修改应用的依赖或锁文件。渲染时仅在内存中内联 PNG，输出 2 倍分辨率的 `hero.png`。SVG 保留相对引用，作为可编辑源使用；README 引用最终 PNG，避免 GitHub 对 SVG 外部图片的限制。

修改后检查 900 px 与 360 px 宽度；图中小字号分类在 README 正文中有对应说明。安装命令、配置和文档导航始终使用 Markdown。
