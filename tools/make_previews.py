#!/usr/bin/env python3
"""
Genera las capturas de docs/img/ componiendo el tema tal como lo dibuja GRUB.

No arranca nada: toma las mismas imagenes, las mismas medidas de theme.txt y
los mismos textos de ventoy.json que usara la USB, y los monta en un PNG. Si
una captura se ve mal aqui, se vera mal al arrancar.

Uso:
    python tools/make_previews.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_theme import LAYOUT, ROOT, font, rgba  # noqa: E402

DOCS = ROOT / "docs" / "img"


# --------------------------------------------------------------------------
#  Reconstruccion del 9-slice tal como lo estira GRUB
# --------------------------------------------------------------------------

def nine_slice(folder: Path, prefix: str, size: tuple[int, int]) -> Image.Image:
    w, h = size
    p = {n: Image.open(folder / f"{prefix}_{n}.png").convert("RGBA")
         for n in ["nw", "n", "ne", "w", "c", "e", "sw", "s", "se"]}
    cw, ch = p["nw"].size
    mid_w, mid_h = max(1, w - 2 * cw), max(1, h - 2 * ch)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(p["nw"], (0, 0))
    out.alpha_composite(p["ne"], (w - cw, 0))
    out.alpha_composite(p["sw"], (0, h - ch))
    out.alpha_composite(p["se"], (w - cw, h - ch))
    out.alpha_composite(p["n"].resize((mid_w, ch)), (cw, 0))
    out.alpha_composite(p["s"].resize((mid_w, ch)), (cw, h - ch))
    out.alpha_composite(p["w"].resize((cw, mid_h)), (0, ch))
    out.alpha_composite(p["e"].resize((cw, mid_h)), (w - cw, ch))
    out.alpha_composite(p["c"].resize((mid_w, mid_h)), (cw, ch))
    return out


def select_bar(folder: Path, size: tuple[int, int]) -> Image.Image:
    w, h = size
    west = Image.open(folder / "select_w.png").convert("RGBA")
    east = Image.open(folder / "select_e.png").convert("RGBA")
    core = Image.open(folder / "select_c.png").convert("RGBA")
    sw = west.width
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(west.resize((sw, h)), (0, 0))
    out.alpha_composite(east.resize((sw, h)), (w - sw, 0))
    out.alpha_composite(core.resize((max(1, w - 2 * sw), h)), (sw, 0))
    return out


# --------------------------------------------------------------------------
#  Montaje de una pantalla
# --------------------------------------------------------------------------

def render_screen(res: str, cfg: dict, items: list[tuple[str, str]], selected: int,
                  tips: tuple[str, str] | None, hotkeys: str) -> Image.Image:
    C, L = cfg["colors"], LAYOUT[res]
    w, h = (int(v) for v in res.split("x"))
    folder = ROOT / "usb" / "ventoy" / "theme" / cfg["theme_dir"] / res

    screen = Image.open(folder / "background.png").convert("RGBA")
    d = ImageDraw.Draw(screen)

    logo = Image.open(folder / "logo.png").convert("RGBA")
    screen.alpha_composite(logo, ((w - logo.width) // 2, L["logo_top"]))

    f_small = font("medium", int(L["font_small"] * 1.45))
    f_item = font("medium", int(L["font_item"] * 1.45))
    f_mono = font("medium", int(L["font_small"] * 1.30))

    d.text((w / 2, L["prompt_top"]), cfg["prompt"], font=f_small,
           fill=rgba(C["muted"], 255), anchor="ma")

    menu_x = (w - L["menu_w"]) // 2
    screen.alpha_composite(nine_slice(folder, "menu", (L["menu_w"], L["menu_h"])),
                           (menu_x, L["menu_top"]))

    y = L["menu_top"] + L["item_pad"] + L["item_gap"]
    bar_w = L["menu_w"] - 2 * L["item_pad"]
    for i, (label, icon_name) in enumerate(items):
        if i == selected:
            screen.alpha_composite(select_bar(folder, (bar_w, L["item_h"])),
                                   (menu_x + L["item_pad"], y))
        icon_path = folder / "icons" / f"{icon_name}.png"
        icon_x = menu_x + L["item_pad"] + L["icon_gap"]
        if icon_path.exists():
            icon = Image.open(icon_path).convert("RGBA")
            screen.alpha_composite(icon, (icon_x, y + (L["item_h"] - icon.height) // 2))
        color = C["item_selected"] if i == selected else C["item"]
        d.text((icon_x + L["icon"] + L["icon_gap"], y + L["item_h"] / 2), label,
               font=f_item, fill=rgba(color, 255), anchor="lm")
        y += L["item_h"] + L["item_gap"]

    if tips:
        tx = (w - L["menu_w"]) // 2
        for k, line in enumerate(tips):
            d.text((tx, L["tip_top"] + k * int(L["font_small"] * 1.7)), line,
                   font=f_mono, fill=rgba(C["tip"], 255))

    d.text((int(w * 0.03), L["hotkey_top"]), hotkeys, font=f_small, fill=rgba(C["hint"], 255))
    ver = "1.1.17 UEFI   www.ventoy.net"
    d.text((w - int(w * 0.02), L["hotkey_top"]), ver, font=f_mono,
           fill=rgba(C["ventoy_version"], 255), anchor="ra")
    return screen.convert("RGB")


# --------------------------------------------------------------------------

HOTKEYS = "L:Idioma  F1:Ayuda  F2:Navegar  F3:Vista de arbol  F4:Arranque local  F5:Herramientas  F6:Menu ext."


def alias_of(data: dict, key: str, kind: str) -> str:
    for entry in data.get("menu_alias", []):
        if entry.get(kind) == key:
            return entry.get("alias", key)
    return key


def tips_of(data: dict, key: str, kind: str) -> tuple[str, str] | None:
    for entry in data.get("menu_tip", {}).get("tips", []):
        if entry.get(kind) == key:
            return entry.get("tip1", ""), entry.get("tip2", "")
    return None


def main() -> None:
    cfg = json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))
    data = json.loads((ROOT / "usb" / "ventoy" / "ventoy.json").read_text(encoding="utf-8"))
    DOCS.mkdir(parents=True, exist_ok=True)

    dirs = [e["dir"] for e in data.get("menu_alias", []) if "dir" in e]
    top = [(alias_of(data, p, "dir"), cls) for p, cls in zip(
        dirs, ["install", "repair", "clone", "diag", "linux"])]

    # primeras ISOs declaradas dentro de la primera categoria
    win = [e["image"] for e in data.get("menu_alias", [])
           if "image" in e and e["image"].startswith(dirs[0] + "/")][:2]
    submenu = [(alias_of(data, i, "image"), "install") for i in win]
    submenu.append(("Volver", "vtoyret"))

    shots = [
        ("01_menu_principal.png", "1920x1080", top, 0, tips_of(data, dirs[0], "dir")),
        ("02_submenu_windows.png", "1920x1080", submenu, 0,
         tips_of(data, win[0], "image") if win else None),
        ("03_diagnostico.png", "1920x1080", top, 3, tips_of(data, dirs[3], "dir")),
        ("04_pantalla_1024x768.png", "1024x768", top, 4, tips_of(data, dirs[4], "dir")),
    ]

    for name, res, items, sel, tips in shots:
        img = render_screen(res, cfg, items, sel, tips, HOTKEYS)
        img.save(DOCS / name)
        print(f"  docs/img/{name}  ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
