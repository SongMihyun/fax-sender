"""Create the FaxSender Windows application icon from the in-app fax mark."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "auto_processor" / "assets" / "faxsender.ico"


def draw_icon(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = round(size * 0.08)
    radius = round(size * 0.18)
    draw.rounded_rectangle((pad, pad, size - pad, size - pad), radius=radius, fill="#151b2b")

    white = "#eef4ff"
    muted = "#9fb3cb"
    purple = "#a86eff"
    scale = size / 64
    line = max(2, round(3 * scale))
    thin = max(1, round(2 * scale))
    point = lambda x, y: (round(x * scale), round(y * scale))

    # Paper, fax body, and a purple right-facing transmission arrow.
    draw.rounded_rectangle((*point(20, 11), *point(42, 28)), radius=max(2, round(3 * scale)), outline=white, width=line)
    draw.line((*point(25, 18), *point(37, 18)), fill=muted, width=thin)
    draw.rounded_rectangle((*point(13, 25), *point(51, 47)), radius=max(2, round(3 *scale)), outline=white, width=line)
    draw.line((*point(20, 34), *point(44, 34)), fill=muted, width=line)
    draw.line((*point(20, 47), *point(20, 51)), fill=white, width=line)
    draw.line((*point(44, 47), *point(44, 51)), fill=white, width=line)
    draw.line((*point(41, 17), *point(55, 17)), fill=purple, width=line)
    draw.line((*point(51, 12), *point(56, 17)), fill=purple, width=line)
    draw.line((*point(51, 22), *point(56, 17)), fill=purple, width=line)
    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    icon = draw_icon(256)
    icon.save(OUTPUT, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(OUTPUT)


if __name__ == "__main__":
    main()
