"""Gera o ícone do Relógio Vivo (assets/icon.ico e assets/icon.png).

Uso:
    python make_icon.py

O desenho é feito em 4x e reduzido, para sair suave em todos os tamanhos.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

BASE = 1024
SCALE = 4
SIZE = BASE * SCALE

BG_TOP = (32, 52, 92)
BG_BOTTOM = (9, 15, 28)
ACCENT = (124, 199, 255)
ACCENT_SOFT = (86, 148, 214)
HAND = (240, 248, 255)


def gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (1, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(
            round(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)
        )
    return img.resize((size, size))


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    return mask


def build() -> Image.Image:
    s = SIZE
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    canvas.paste(gradient(s), (0, 0), rounded_mask(s, round(s * 0.22)))

    draw = ImageDraw.Draw(canvas)

    # brilho suave no topo
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse(
        (-s * 0.25, -s * 0.55, s * 1.25, s * 0.45),
        fill=(120, 180, 255, 34),
    )
    glow.putalpha(Image.composite(glow.getchannel("A"), Image.new("L", (s, s), 0), rounded_mask(s, round(s * 0.22))))
    canvas = Image.alpha_composite(canvas, glow)
    draw = ImageDraw.Draw(canvas)

    cx, cy = s * 0.5, s * 0.47
    radius = s * 0.30
    ring = round(s * 0.028)

    # anel do relógio
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        outline=ACCENT,
        width=ring,
    )
    # marcas de 12, 3, 6 e 9
    tick = s * 0.028
    for angle_cos, angle_sin in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        x1 = cx + angle_cos * (radius - s * 0.075)
        y1 = cy + angle_sin * (radius - s * 0.075)
        x2 = cx + angle_cos * (radius - s * 0.022)
        y2 = cy + angle_sin * (radius - s * 0.022)
        draw.line((x1, y1, x2, y2), fill=ACCENT_SOFT, width=round(tick))

    def hand(angle_deg: float, length: float, width: float) -> None:
        from math import cos, radians, sin

        a = radians(angle_deg - 90)
        x = cx + cos(a) * length
        y = cy + sin(a) * length
        draw.line((cx, cy, x, y), fill=HAND, width=round(width))
        r = width / 2
        draw.ellipse((x - r, y - r, x + r, y + r), fill=HAND)

    hand(-60, radius * 0.55, s * 0.040)   # hora
    hand(60, radius * 0.78, s * 0.032)    # minuto

    r = s * 0.030
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ACCENT)

    # faixa da data embaixo
    bar_w = s * 0.40
    bar_h = s * 0.062
    bar_y = cy + radius + s * 0.105
    draw.rounded_rectangle(
        (cx - bar_w / 2, bar_y, cx + bar_w / 2, bar_y + bar_h),
        radius=bar_h / 2,
        fill=ACCENT,
    )

    return canvas.resize((BASE, BASE), Image.LANCZOS)


def main() -> None:
    out_dir = Path(__file__).resolve().parent / "assets"
    out_dir.mkdir(exist_ok=True)

    icon = build()
    png = out_dir / "icon.png"
    icon.save(png, "PNG")
    print(f"Gerado: {png}")

    ico = out_dir / "icon.ico"
    icon.save(
        ico,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Gerado: {ico}")


if __name__ == "__main__":
    main()
