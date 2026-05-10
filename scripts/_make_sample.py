"""生成一张用于冒烟测试的 PNG。"""

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    out = Path("outputs/_smoke/sample.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (512, 512), (30, 90, 180))
    draw = ImageDraw.Draw(img)
    # 一些几何图形，方便观察色彩量化
    draw.rectangle((40, 40, 240, 240), fill=(240, 200, 80))
    draw.ellipse((260, 120, 480, 380), fill=(220, 60, 80))
    draw.polygon([(100, 300), (300, 480), (60, 480)], fill=(60, 170, 80))
    img.save(out)
    print(f"written: {out}")


if __name__ == "__main__":
    main()
