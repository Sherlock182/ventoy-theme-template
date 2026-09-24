#!/usr/bin/env python3
"""
Generador del tema de Ventoy.

Lee brand.json y regenera, para cada resolucion declarada:
  background.png  logo.png  menu_*.png  select_*.png  slider_*.png
  terminal_box_*.png  icons/*.png  theme.txt

Tambien actualiza las rutas del tema dentro de usb/ventoy/ventoy.json
y exporta los logos sueltos a brand/.

Uso:
    python tools/build_theme.py                # genera todo
    python tools/build_theme.py --only 1920x1080
    python tools/build_theme.py --config mi_marca.json
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import shutil
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    sys.exit("Falta Pillow.  Instalelo con:  pip install -r tools/requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "tools" / "assets"
SS = 4  # factor de supermuestreo para dibujar con bordes suaves


# --------------------------------------------------------------------------
#  Color
# --------------------------------------------------------------------------

def hex_to_rgb(value) -> tuple[int, int, int]:
    """Acepta "#RGB", "#RRGGBB" o una tupla ya resuelta."""
    if not isinstance(value, str):
        return tuple(value[:3])  # type: ignore[return-value]
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgba(value, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(value)
    return (r, g, b, alpha)


def mix(a: str | tuple, b: str | tuple, t: float) -> tuple[int, int, int]:
    """Interpola dos colores. t=0 devuelve a, t=1 devuelve b."""
    ca, cb = hex_to_rgb(a), hex_to_rgb(b)
    return tuple(round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))  # type: ignore[return-value]


def shade(value: str | tuple, factor: float) -> tuple[int, int, int]:
    """factor < 1 oscurece, factor > 1 aclara."""
    c = hex_to_rgb(value)
    return tuple(max(0, min(255, round(x * factor))) for x in c)  # type: ignore[return-value]


def hue_of(value: str) -> tuple[float, float]:
    r, g, b = (x / 255 for x in hex_to_rgb(value))
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    return h, s


# --------------------------------------------------------------------------
#  Fuentes
# --------------------------------------------------------------------------

_FONT_CANDIDATES = {
    "bold": ["Poppins-Bold.ttf", "Poppins-SemiBold.ttf", "Montserrat-Bold.ttf",
             "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "medium": ["Poppins-Medium.ttf", "Poppins-Regular.ttf", "Montserrat-Medium.ttf",
               "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Busca primero en tools/assets/fonts, luego en las fuentes del sistema."""
    key = (weight, size)
    if key in _font_cache:
        return _font_cache[key]
    for name in _FONT_CANDIDATES[weight]:
        for candidate in (ASSETS / "fonts" / name, Path(name)):
            try:
                f = ImageFont.truetype(str(candidate), size)
                _font_cache[key] = f
                return f
            except (OSError, ValueError):
                continue
    raise SystemExit(
        "No se encontro ninguna fuente TrueType utilizable.\n"
        "Coloque Poppins-Bold.ttf y Poppins-Medium.ttf en tools/assets/fonts/"
    )


def text_width(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=f)
    return box[2] - box[0]


def tracked_text(draw: ImageDraw.ImageDraw, xy, text, f, fill, tracking=0, anchor_left=True):
    """Dibuja texto con espaciado entre letras (tracking) y devuelve el ancho usado."""
    x, y = xy
    if not anchor_left:  # medir primero para centrar
        total = sum(text_width(draw, ch, f) + tracking for ch in text) - tracking
        x -= total / 2
    start = x
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += text_width(draw, ch, f) + tracking
    return x - start - tracking


# --------------------------------------------------------------------------
#  Primitivas de dibujo
# --------------------------------------------------------------------------

def linear_gradient(size, c1, c2, vertical=True) -> Image.Image:
    """Degradado lineal de c1 a c2 en una imagen RGB del tamano pedido."""
    w, h = size
    steps = h if vertical else w
    bar = Image.new("RGB", (1, steps) if vertical else (steps, 1))
    px = bar.load()
    for i in range(steps):
        c = mix(c1, c2, i / max(1, steps - 1))
        if vertical:
            px[0, i] = c
        else:
            px[i, 0] = c
    return bar.resize((w, h), Image.BILINEAR)


def radial_glow(size, center, radius, color, strength=1.0) -> Image.Image:
    """Halo radial suave, devuelto como capa RGBA lista para superponer."""
    w, h = size
    cx, cy = center
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                                 fill=int(255 * strength))
    mask = mask.filter(ImageFilter.GaussianBlur(radius * 0.55))
    layer = Image.new("RGBA", (w, h), (*hex_to_rgb(color), 255))
    layer.putalpha(mask)
    return layer


def hexagon(cx, cy, r, rotation=0.0):
    """Seis vertices; rotation=0 deja un vertice arriba (hexagono apuntado)."""
    return [
        (cx + r * math.sin(rotation + i * math.pi / 3),
         cy - r * math.cos(rotation + i * math.pi / 3))
        for i in range(6)
    ]


def gear_polygon(cx, cy, r_out, r_in, teeth=12, tooth_ratio=0.46):
    """Contorno de un engranaje: dientes trapezoidales alrededor de un circulo."""
    pts = []
    step = 2 * math.pi / teeth
    half_top = step * tooth_ratio / 2
    half_base = step * 0.5 / 2 + step * 0.06
    for i in range(teeth):
        a = i * step
        for angle, radius in (
            (a - half_base, r_in), (a - half_top, r_out),
            (a + half_top, r_out), (a + half_base, r_in),
        ):
            pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return pts


def rounded_rect_mask(size, radius) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return m


def wrench(draw: ImageDraw.ImageDraw, p_open, p_closed, width, color, hollow):
    """Llave inglesa: cabeza de boca abierta en p_open, cabeza de anillo en p_closed.

    `hollow` es el color con el que se perforan la boca y el anillo; pasando
    (0, 0, 0, 0) sobre una capa propia se deja ver lo que haya debajo.
    """
    head = width * 1.6
    draw.line([p_closed, p_open], fill=color, width=int(width), joint="curve")
    for p in (p_open, p_closed):
        draw.ellipse([p[0] - head, p[1] - head, p[0] + head, p[1] + head], fill=color)

    ring = head * 0.42
    draw.ellipse([p_closed[0] - ring, p_closed[1] - ring,
                  p_closed[0] + ring, p_closed[1] + ring], fill=hollow)

    # boca en V: vertice dentro de la cabeza, abriendose hacia afuera del mango
    ang = math.atan2(p_open[1] - p_closed[1], p_open[0] - p_closed[0])
    tip = (p_open[0] - head * 0.15 * math.cos(ang), p_open[1] - head * 0.15 * math.sin(ang))
    spread, reach = math.radians(20), head * 2.6
    draw.polygon([
        tip,
        (tip[0] + reach * math.cos(ang - spread), tip[1] + reach * math.sin(ang - spread)),
        (tip[0] + reach * math.cos(ang + spread), tip[1] + reach * math.sin(ang + spread)),
    ], fill=hollow)


# --------------------------------------------------------------------------
#  Emblema (hexagono + engranaje + llave + inicial)
# --------------------------------------------------------------------------

def build_emblem(size: int, C: dict, initial: str) -> Image.Image:
    """Emblema cuadrado con fondo transparente, dibujado a 4x y reducido."""
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    r = S * 0.485

    # --- hexagono: borde de acento con degradado, relleno oscuro ---
    ring = Image.new("L", (S, S), 0)
    ImageDraw.Draw(ring).polygon(hexagon(cx, cy, r), fill=255)
    ring_grad = linear_gradient((S, S), C["accent"], C["accent_deep"]).convert("RGBA")
    ring_grad.putalpha(ring)
    img.alpha_composite(ring_grad)

    d.polygon(hexagon(cx, cy, r * 0.915), fill=rgba(C["bg_deep"], 255))
    d.polygon(hexagon(cx, cy, r * 0.83), outline=rgba(mix(C["bg_deep"], C["accent"], 0.22), 255),
              width=max(1, int(S * 0.006)))

    # --- engranaje con degradado ---
    gear_mask = Image.new("L", (S, S), 0)
    gd = ImageDraw.Draw(gear_mask)
    gd.polygon(gear_polygon(cx, cy, r * 0.63, r * 0.50), fill=255)
    gd.ellipse([cx - r * 0.52, cy - r * 0.52, cx + r * 0.52, cy + r * 0.52], fill=255)
    gear_mask = gear_mask.filter(ImageFilter.GaussianBlur(S * 0.0015))
    gear = linear_gradient((S, S), C["accent"], C["accent_deep"]).convert("RGBA")
    gear.putalpha(gear_mask)
    img.alpha_composite(gear)

    # --- llave inglesa en diagonal, recortada al hexagono ---
    tool = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    td = ImageDraw.Draw(tool)
    off = r * 0.66 / math.sqrt(2)
    wrench(td, (cx + off, cy - off), (cx - off, cy + off),
           width=S * 0.065, color=(226, 232, 240, 255), hollow=(0, 0, 0, 0))
    clip = Image.new("L", (S, S), 0)
    ImageDraw.Draw(clip).polygon(hexagon(cx, cy, r * 0.90), fill=255)
    tool.putalpha(Image.composite(tool.getchannel("A"), Image.new("L", (S, S), 0), clip))
    img.alpha_composite(tool)

    # --- nucleo oscuro, por encima del mango de la llave ---
    core = r * 0.345
    d.ellipse([cx - core, cy - core, cx + core, cy + core], fill=rgba(C["bg_deep"], 255))
    d.ellipse([cx - core * 0.9, cy - core * 0.9, cx + core * 0.9, cy + core * 0.9],
              outline=rgba(mix(C["bg_deep"], C["accent"], 0.35), 255), width=max(1, int(S * 0.005)))

    # --- inicial ---
    letter = (initial or "").strip()[:1].upper()
    if letter:
        f = font("bold", int(S * 0.30))
        box = d.textbbox((0, 0), letter, font=f)
        d.text((cx - (box[2] + box[0]) / 2, cy - (box[3] + box[1]) / 2), letter,
               font=f, fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.LANCZOS)


def build_logo(width: int, height: int, C: dict, cfg: dict) -> Image.Image:
    """Logo horizontal: emblema a la izquierda y bloque de texto a la derecha.

    Se compone a tamano libre y despues se escala para encajar en
    (width, height), de modo que ningun nombre quede recortado por largo
    que sea.
    """
    L = cfg["logo"]
    line_top = L.get("line_top", "").upper()
    line_main = L.get("line_main", "").upper()
    tagline = L.get("tagline", "").upper()

    U = 300                      # altura de referencia del emblema
    pad = U // 4
    canvas = Image.new("RGBA", (U * 14, U * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)

    f_top = font("bold", int(U * 0.135))
    f_main = font("bold", int(U * 0.355))
    f_tag = font("medium", int(U * 0.088))
    tr_top, tr_main, tr_tag = int(U * 0.060), int(U * 0.013), int(U * 0.030)

    emblem = build_emblem(U, C, L.get("initial", ""))
    canvas.alpha_composite(emblem, (pad, pad))

    tx = pad + U + int(U * 0.13)
    y = pad + int(U * 0.10)
    if line_top:
        tracked_text(d, (tx, y), line_top, f_top, rgba(C["accent"], 255), tr_top)
    y += int(U * 0.20)
    if line_main:
        tracked_text(d, (tx, y), line_main, f_main, (255, 255, 255, 255), tr_main)
    y += int(U * 0.43)
    if tagline:
        rule_w = int(U * 0.17)
        ry = y + int(U * 0.058)
        d.line([(tx, ry), (tx + rule_w, ry)], fill=rgba(C["accent"], 255), width=max(2, int(U * 0.020)))
        tracked_text(d, (tx + rule_w + int(U * 0.07), y), tagline, f_tag,
                     rgba(mix(C["muted"], C["item"], 0.45), 255), tr_tag)

    box = canvas.getbbox()
    if box is None:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))
    art = canvas.crop(box)

    scale = min(width / art.width, height / art.height)
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))),
                     Image.LANCZOS)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.alpha_composite(art, ((width - art.width) // 2, (height - art.height) // 2))
    return out


# --------------------------------------------------------------------------
#  Layout por resolucion
# --------------------------------------------------------------------------
#  Reproduce las medidas que espera GRUB en cada modo de video. Las piezas
#  9-slice se estiran, asi que su tamano solo influye en la nitidez.

LAYOUT = {
    "1920x1080": dict(
        logo=(480, 150), logo_top=58, prompt_top=236, font_small=17, font_item=22,
        menu_w=1000, menu_top=282, menu_h=540, item_h=48, item_pad=16, item_gap=8,
        icon=32, icon_gap=16, scrollbar=6, corner=20, panel=(560, 360),
        select=(1000, 48), select_side=10, slider=(6, 28, 6),
        flags_top=986, hotkey_top=1037, tip_top=838, ventoy_off=240,
    ),
    "1366x768": dict(
        logo=(333, 104), logo_top=34, prompt_top=160, font_small=14, font_item=16,
        menu_w=780, menu_top=196, menu_h=384, item_h=36, item_pad=12, item_gap=6,
        icon=24, icon_gap=12, scrollbar=5, corner=16, panel=(568, 368),
        select=(1000, 36), select_side=8, slider=(5, 30, 5),
        flags_top=690, hotkey_top=733, tip_top=592, ventoy_off=240,
    ),
    "1024x768": dict(
        logo=(333, 104), logo_top=34, prompt_top=160, font_small=14, font_item=16,
        menu_w=740, menu_top=196, menu_h=384, item_h=36, item_pad=12, item_gap=6,
        icon=24, icon_gap=12, scrollbar=5, corner=16, panel=(568, 368),
        select=(1000, 36), select_side=8, slider=(5, 30, 5),
        flags_top=690, hotkey_top=733, tip_top=592, ventoy_off=225,
    ),
}


# --------------------------------------------------------------------------
#  Fondo de pantalla
# --------------------------------------------------------------------------

def build_background(w: int, h: int, C: dict, opts: dict, emblem: Image.Image) -> Image.Image:
    bg = linear_gradient((w, h), mix(C["bg_deep"], C["bg_soft"], 0.75), C["bg_deep"]).convert("RGBA")

    # halo frio detras del logo
    bg.alpha_composite(radial_glow((w, h), (w * 0.5, h * 0.04), h * 0.55,
                                   mix(C["accent"], C["bg_soft"], 0.62), 0.38))

    # panal de hexagonos, desvaneciendose hacia abajo
    if opts.get("hex_pattern", True):
        cell = h / 11
        grid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grid)
        line = rgba(mix(C["bg_deep"], C["accent"], 0.30), 255)
        step_x = cell * math.sqrt(3)
        row = 0
        y = -cell
        while y < h + cell:
            x = -cell if row % 2 == 0 else -cell + step_x / 2
            while x < w + cell:
                gd.polygon(hexagon(x, y, cell * 0.99), outline=line, width=2)
                x += step_x
            y += cell * 1.5
            row += 1
        fade = linear_gradient((w, h), (255, 255, 255), (0, 0, 0)).convert("L")
        fade = fade.point(lambda v: int(v * 0.34))
        grid.putalpha(Image.composite(fade, Image.new("L", (w, h), 0), grid.getchannel("A")))
        bg.alpha_composite(grid)

    # marca de agua del emblema en la esquina inferior derecha
    if opts.get("watermark", True):
        size = int(h * 0.62)
        mark = emblem.resize((size, size), Image.LANCZOS).convert("RGBA")
        mark.putalpha(mark.getchannel("A").point(lambda v: int(v * 0.055)))
        bg.alpha_composite(mark, (int(w - size * 0.80), int(h - size * 0.72)))

    # vineta: oscurece los bordes para que el menu destaque
    vig = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vig).ellipse((-w * 0.25, -h * 0.55, w * 1.25, h * 1.35), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(min(w, h) * 0.16)).point(lambda v: 255 - int(v * 0.80))
    dark = Image.new("RGBA", (w, h), rgba(C["bg_deep"], 255))
    dark.putalpha(vig)
    bg.alpha_composite(dark)

    # filete de acento en el borde superior
    if opts.get("top_rule", True):
        rule = linear_gradient((w, 1), C["bg_deep"], C["accent"], vertical=False).convert("RGBA")
        rule = rule.resize((w, max(2, h // 360)))
        mask = linear_gradient((w, 1), (0, 0, 0), (255, 255, 255), vertical=False).convert("L")
        mask = Image.merge("L", [mask]).resize(rule.size)
        rule.putalpha(mask.point(lambda v: int(190 * (1 - abs(v - 128) / 128))))
        bg.alpha_composite(rule, (0, 0))

    return bg.convert("RGB")


# --------------------------------------------------------------------------
#  Piezas 9-slice (menu, caja de terminal, barra de seleccion, scrollbar)
# --------------------------------------------------------------------------

_SLICE_NAMES = ["nw", "n", "ne", "w", "c", "e", "sw", "s", "se"]


def slice_nine(panel: Image.Image, corner: int) -> dict[str, Image.Image]:
    """Corta un panel en las nueve piezas que GRUB espera."""
    w, h = panel.size
    xs = [(0, corner), (corner, w - corner), (w - corner, w)]
    ys = [(0, corner), (corner, h - corner), (h - corner, h)]
    out = {}
    for i, (y0, y1) in enumerate(ys):
        for j, (x0, x1) in enumerate(xs):
            out[_SLICE_NAMES[i * 3 + j]] = panel.crop((x0, y0, x1, y1))
    return out


def build_panel(size, corner, C, fill_alpha, border_alpha, glow=True) -> Image.Image:
    """Panel de esquinas redondeadas con borde de acento y brillo superior."""
    w, h = size
    S = 2
    big = (w * S, h * S)
    panel = Image.new("RGBA", big, (0, 0, 0, 0))
    mask = rounded_rect_mask(big, corner * S)

    body = linear_gradient(big, mix(C["bg_soft"], C["accent"], 0.10), C["bg_deep"]).convert("RGBA")
    body.putalpha(mask.point(lambda v: int(v * fill_alpha / 255)))
    panel.alpha_composite(body)

    edge = Image.new("RGBA", big, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle((1, 1, big[0] - 2, big[1] - 2), radius=corner * S,
                                           outline=rgba(C["accent"], border_alpha),
                                           width=max(2, S))
    panel.alpha_composite(edge)

    if glow:  # realce tenue en el borde superior
        top = Image.new("RGBA", big, (0, 0, 0, 0))
        ImageDraw.Draw(top).rounded_rectangle((1, 1, big[0] - 2, big[1] - 2), radius=corner * S,
                                              outline=rgba(mix(C["accent"], "#FFFFFF", 0.5), 40),
                                              width=max(2, S))
        fade = linear_gradient(big, (255, 255, 255), (0, 0, 0)).convert("L")
        top.putalpha(Image.composite(fade, Image.new("L", big, 0), top.getchannel("A")))
        panel.alpha_composite(top)

    return panel.resize((w, h), Image.LANCZOS)


def build_select_bar(size, side, C) -> Image.Image:
    """Barra del elemento seleccionado: degradado de acento y filo vivo a la izquierda."""
    w, h = size
    S = 2
    big = (w * S, h * S)
    radius = int(h * S * 0.22)
    bar = Image.new("RGBA", big, (0, 0, 0, 0))

    body = linear_gradient(big, C["accent_deep"], mix(C["accent_deep"], C["bg_deep"], 0.72),
                           vertical=False).convert("RGBA")
    body.putalpha(rounded_rect_mask(big, radius).point(lambda v: int(v * 0.92)))
    bar.alpha_composite(body)

    sheen = Image.new("RGBA", big, (0, 0, 0, 0))
    ImageDraw.Draw(sheen).rounded_rectangle((0, 0, big[0] - 1, big[1] - 1), radius=radius,
                                            outline=rgba(mix(C["accent"], "#FFFFFF", 0.35), 110),
                                            width=S)
    bar.alpha_composite(sheen)

    edge = Image.new("RGBA", big, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle((0, 0, side * S * 2, big[1] - 1), radius=radius,
                                           fill=rgba(mix(C["accent"], "#FFFFFF", 0.25), 255))
    edge = Image.composite(edge, Image.new("RGBA", big, (0, 0, 0, 0)),
                           rounded_rect_mask(big, radius))
    bar.alpha_composite(edge)

    return bar.resize((w, h), Image.LANCZOS)


def build_slider(width, mid_h, cap_h, C) -> dict[str, Image.Image]:
    S = 4
    total = (width * S, (cap_h * 2 + mid_h) * S)
    img = Image.new("RGBA", total, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, total[0] - 1, total[1] - 1),
                                          radius=width * S / 2,
                                          fill=rgba(mix(C["accent"], C["bg_deep"], 0.35), 220))
    img = img.resize((width, cap_h * 2 + mid_h), Image.LANCZOS)
    return {
        "n": img.crop((0, 0, width, cap_h)),
        "c": img.crop((0, cap_h, width, cap_h + mid_h)),
        "s": img.crop((0, cap_h + mid_h, width, cap_h * 2 + mid_h)),
    }


# --------------------------------------------------------------------------
#  Iconos: se retinen al color de acento conservando luces y sombras
# --------------------------------------------------------------------------

def recolor_icon(src: Image.Image, accent: str, size: int) -> Image.Image:
    hue, sat = hue_of(accent)
    out = src.convert("RGBA")
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
            if ss < 0.12:      # grises y blancos se dejan intactos
                continue
            nr, ng, nb = colorsys.hls_to_rgb(hue, ll, min(1.0, ss * (sat / max(ss, 0.05)) ** 0.5))
            px[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), a)
    if out.size != (size, size):
        out = out.resize((size, size), Image.LANCZOS)
    return out


# --------------------------------------------------------------------------
#  theme.txt
# --------------------------------------------------------------------------

FLAGS = ["@VTOY_MEM_DISK@", "@VTOY_ISO_RAW@", "@VTOY_GRUB2_MODE@", "@VTOY_WIMBOOT_MODE@"]


def build_theme_txt(res: str, L: dict, C: dict, cfg: dict) -> str:
    _w, h = (int(v) for v in res.split("x"))
    small = f'Poppins Regular {L["font_small"]}'
    item = f'Poppins Medium {L["font_item"]}'
    half_menu = L["menu_w"] // 2
    title = cfg["project_name"].upper()

    flags = "\n".join(
        "+ hbox {{\n"
        "  left = 3%{off}\n"
        "  top = {top}\n"
        "  width = 10%\n"
        "  height = {hh}\n"
        '  + label {{ text = "{flag}" color = "{color}" align = "left" font = "{font}" }}\n'
        "}}".format(off=f"+{i * 220}" if i else "", top=L["flags_top"], hh=L["item_h"] // 2,
                    flag=flag, color=C["flag"], font=small)
        for i, flag in enumerate(FLAGS)
    )

    return TEMPLATE.format(
        title=title, res=res, C=C, L=L, small=small, item=item,
        half_menu=half_menu, flags=flags, prompt=cfg["prompt"],
        logo_half=L["logo"][0] // 2, uefi_top=round(h * 0.02),
    )


TEMPLATE = '''ventoy_left_top_color: "@100%-{L[ventoy_off]}@{L[hotkey_top]}@{C[ventoy_version]}@"
# ==========================================================
#  {title} - Tema para Ventoy ({res})
#  Generado por tools/build_theme.py - no editar a mano.
# ==========================================================
title-text: ""
desktop-image: "background.png"
desktop-color: "{C[bg_deep]}"
message-color: "#DDE7F7"
message-bg-color: "{C[bg_deep]}"

terminal-font: "Unknown Regular 16"
terminal-box: "terminal_box_*.png"
terminal-left: "8%"
terminal-top: "24%"
terminal-width: "84%"
terminal-height: "64%"
terminal-border: "0"

menu-tip-left: "50%-{half_menu}"
menu-tip-top: "{L[tip_top]}"
menu-tip-color: "{C[tip]}"

# ---------- Logo ----------
+ image {{
  left = 50%-{logo_half}
  top = {L[logo_top]}
  file = "logo.png"
}}

# ---------- Instruccion ----------
+ label {{
  left = 0
  top = {L[prompt_top]}
  width = 100%
  height = 24
  align = "center"
  font = "{small}"
  color = "{C[muted]}"
  text = "{prompt}"
}}

# ---------- Menu principal ----------
+ boot_menu {{
  left = 50%-{half_menu}
  top = {L[menu_top]}
  width = {L[menu_w]}
  height = {L[menu_h]}
  menu_pixmap_style = "menu_*.png"
  item_font = "{item}"
  item_color = "{C[item]}"
  selected_item_font = "{item}"
  selected_item_color = "{C[item_selected]}"
  item_height = {L[item_h]}
  item_padding = {L[item_pad]}
  item_spacing = {L[item_gap]}
  icon_width = {L[icon]}
  icon_height = {L[icon]}
  item_icon_space = {L[icon_gap]}
  selected_item_pixmap_style = "select_*.png"
  scrollbar = true
  scrollbar_width = {L[scrollbar]}
  scrollbar_thumb = "slider_*.png"
}}

# ---------- Indicadores de modo (Ctrl+D, Ctrl+R, Ctrl+W, ...) ----------
{flags}
+ hbox {{
  left = 100%-260
  top = {uefi_top}
  width = 10%
  height = 25
  + label {{ text = "@VTOY_ISO_UEFI_DRV@" color = "{C[flag]}" align = "left" font = "{small}" }}
}}

# ---------- Barra inferior: teclas rapidas ----------
+ hbox {{
  left = 3%
  top = {L[hotkey_top]}
  width = 10%
  height = 25
  + label {{ text = "@VTOY_HOTKEY_TIP@" color = "{C[hint]}" align = "left" font = "{small}" }}
}}
'''


# --------------------------------------------------------------------------
#  Construccion
# --------------------------------------------------------------------------

def build_resolution(res: str, cfg: dict, out_root: Path) -> None:
    C, L = cfg["colors"], LAYOUT[res]
    w, h = (int(v) for v in res.split("x"))
    out = out_root / res
    (out / "icons").mkdir(parents=True, exist_ok=True)

    build_logo(*L["logo"], C, cfg).save(out / "logo.png")

    emblem = build_emblem(int(h * 0.9), C, cfg["logo"]["initial"])
    build_background(w, h, C, cfg.get("background", {}), emblem).save(out / "background.png")

    menu = build_panel(L["panel"], L["corner"], C, fill_alpha=150, border_alpha=70)
    for name, piece in slice_nine(menu, L["corner"]).items():
        piece.save(out / f"menu_{name}.png")

    term = build_panel(L["panel"], L["corner"], C, fill_alpha=238, border_alpha=95)
    for name, piece in slice_nine(term, L["corner"]).items():
        piece.save(out / f"terminal_box_{name}.png")

    bar = build_select_bar(L["select"], L["select_side"], C)
    side = L["select_side"]
    bar.crop((0, 0, side, bar.height)).save(out / "select_w.png")
    bar.crop((side, 0, bar.width - side, bar.height)).save(out / "select_c.png")
    bar.crop((bar.width - side, 0, bar.width, bar.height)).save(out / "select_e.png")

    sw, mid, cap = L["slider"]
    for name, piece in build_slider(sw, mid, cap, C).items():
        piece.save(out / f"slider_{name}.png")

    for src in sorted((ASSETS / "icons").glob("*.png")):
        recolor_icon(Image.open(src), C["accent"], L["icon"]).save(out / "icons" / src.name)

    (out / "theme.txt").write_text(build_theme_txt(res, L, C, cfg), encoding="utf-8")
    n_img = len(list(out.glob("*.png")))
    n_ico = len(list((out / "icons").glob("*.png")))
    print(f"  {res}  ->  {n_img} imagenes + {n_ico} iconos + theme.txt")


def sync_ventoy_json(cfg: dict, theme_root: Path) -> None:
    """Deja ventoy.json apuntando al tema recien generado."""
    path = ROOT / "usb" / "ventoy" / "ventoy.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    base = f"/ventoy/theme/{cfg['theme_dir']}"
    first = LAYOUT[cfg["resolutions"][0]]
    theme = data.setdefault("theme", {})
    theme["file"] = [f"{base}/{res}/theme.txt" for res in cfg["resolutions"]]
    theme["gfxmode"] = ",".join(cfg["resolutions"])
    theme["fonts"] = [f"{base}/fonts/{f.name}" for f in sorted((theme_root / "fonts").glob("*.pf2"))]
    theme["ventoy_color"] = cfg["colors"]["ventoy_version"]
    theme["ventoy_left"] = f"100%-{first['ventoy_off']}"
    if "menu_tip" in data:
        data["menu_tip"]["color"] = cfg["colors"]["tip"]
        data["menu_tip"]["left"] = f"50%-{first['menu_w'] // 2}"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    print(f"  ventoy.json actualizado -> {base}")


def build_grub_cfg(cfg: dict) -> None:
    """Genera el menu extendido (F6) a partir de la plantilla, con el nombre del proyecto."""
    tmpl = ASSETS / "ventoy_grub.cfg.tmpl"
    if not tmpl.exists():
        return
    data_path = ROOT / "usb" / "ventoy" / "ventoy.json"
    categories = ""
    if data_path.exists():
        data = json.loads(data_path.read_text(encoding="utf-8"))
        names = [e["alias"] for e in data.get("menu_alias", []) if "dir" in e]
        categories = "\n".join(f'    echo "    {i}. {n}"' for i, n in enumerate(names, 1))
    out = tmpl.read_text(encoding="utf-8").format(
        PROJECT_NAME=cfg["project_name"],
        PROJECT_UPPER=cfg["project_name"].upper(),
        CATEGORIES=categories,
    )
    (ROOT / "usb" / "ventoy" / "ventoy_grub.cfg").write_text(out, encoding="utf-8")
    print("  ventoy_grub.cfg generado (menu F6)")


def export_brand(cfg: dict) -> None:
    """Logos sueltos para el README, redes o papeleria."""
    C = cfg["colors"]
    out = ROOT / "brand"
    out.mkdir(exist_ok=True)
    build_emblem(1024, C, cfg["logo"]["initial"]).save(out / "emblema.png")
    build_logo(960, 300, C, cfg).save(out / "logo_horizontal.png")
    dark = Image.new("RGBA", (960, 300), rgba(C["bg_deep"], 255))
    dark.alpha_composite(build_logo(960, 300, C, cfg))
    dark.convert("RGB").save(out / "logo_horizontal_fondo_oscuro.png")
    print("  brand/  ->  emblema.png, logo_horizontal.png, logo_horizontal_fondo_oscuro.png")


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera el tema de Ventoy a partir de brand.json")
    ap.add_argument("--config", default=str(ROOT / "brand.json"))
    ap.add_argument("--only", action="append", help="generar solo esta resolucion (repetible)")
    ap.add_argument("--no-brand", action="store_true", help="no exportar los logos a brand/")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    resolutions = args.only or cfg["resolutions"]
    unknown = [r for r in resolutions if r not in LAYOUT]
    if unknown:
        sys.exit(f"Resolucion sin layout definido: {', '.join(unknown)}\n"
                 f"Disponibles: {', '.join(LAYOUT)}")

    theme_root = ROOT / "usb" / "ventoy" / "theme" / cfg["theme_dir"]
    theme_root.mkdir(parents=True, exist_ok=True)
    if not (theme_root / "fonts").exists():
        shutil.copytree(ASSETS / "fonts", theme_root / "fonts")

    print(f'Generando "{cfg["project_name"]}" en {theme_root.relative_to(ROOT)}')
    for res in resolutions:
        build_resolution(res, cfg, theme_root)
    sync_ventoy_json(cfg, theme_root)
    build_grub_cfg(cfg)
    if not args.no_brand:
        export_brand(cfg)
    print("Listo.")


if __name__ == "__main__":
    main()
