# Personalización

Todo el aspecto del menú sale de un único archivo, **`brand.json`**, y de un
único comando. Lo que trae la plantilla —"Kit de Herramientas"— es solo una
marca de ejemplo: está ahí para que veas cómo queda, y para que la reemplaces.

```bash
pip install -r tools/requirements.txt
python tools/build_theme.py
```

Esta guía explica qué controla cada cosa, de lo más sencillo a lo más
avanzado.

---

## 1. Cambiar el nombre y el logo

```jsonc
{
  "project_name": "Kit de Herramientas",   // aparece en el menú F6 y en los comentarios
  "theme_dir": "kitherramientas",          // carpeta dentro de theme/ (sin espacios ni acentos)

  "logo": {
    "line_top":  "KIT DE",                 // línea pequeña, en color de acento
    "line_main": "HERRAMIENTAS",           // línea grande, en blanco
    "tagline":   "SISTEMAS · DIAGNÓSTICO · RECUPERACIÓN",
    "initial":   "H"                       // letra dentro del engranaje
  }
}
```

Notas:

- **El logo se autoajusta.** Se compone a tamaño libre y luego se escala para
  caber en el espacio disponible, así que un nombre largo se encoge en vez de
  cortarse. Aun así, dos o tres palabras se leen mucho mejor que seis.
- `initial` admite una sola letra. Déjala en `""` si prefieres el engranaje
  limpio.
- Cualquiera de las tres líneas de texto puede ir vacía.
- Si cambias **`theme_dir`**, el generador actualiza solo las rutas de
  `ventoy.json`. Pero la carpeta antigua sigue en `usb/ventoy/theme/`: bórrala
  a mano para no copiar peso muerto a la USB.

---

## 2. Cambiar los colores

```jsonc
"colors": {
  "accent":         "#3BA9F7",   // color principal: emblema, iconos, bordes, filo de selección
  "accent_deep":    "#1D4ED8",   // tono oscuro del degradado y de la barra de selección
  "bg_deep":        "#060B16",   // fondo, en los bordes de la pantalla
  "bg_soft":        "#0E1B33",   // fondo, en el centro superior
  "item":           "#B8C7DE",   // texto de las entradas del menú
  "item_selected":  "#FFFFFF",   // texto de la entrada seleccionada
  "muted":          "#7F93B5",   // línea de instrucciones bajo el logo
  "tip":            "#8FB7E8",   // descripciones de dos líneas
  "hint":           "#9FB0CC",   // barra inferior de teclas rápidas
  "flag":           "#FFB547",   // indicadores de modo (Ctrl+D, Ctrl+R…)
  "ventoy_version": "#5C7299"    // versión de Ventoy, esquina inferior derecha
}
```

En la práctica basta con tocar **`accent`** y **`accent_deep`**: el emblema,
los 52 iconos, el borde del panel y la barra de selección se recalculan a
partir de ellos.

**Cómo se recolorean los iconos.** Los maestros de `tools/assets/icons/` se
convierten a HSL y se les impone el tono de `accent`, conservando luminosidad y
saturación relativa. Los píxeles casi grises (saturación < 0,12) se dejan
intactos, de modo que los detalles blancos siguen siendo blancos. El resultado
es coherente con cualquier color sin tener que redibujar nada.

Combinaciones que funcionan bien sobre el fondo oscuro:

| Intención | `accent` | `accent_deep` |
|---|---|---|
| Azul (por defecto) | `#3BA9F7` | `#1D4ED8` |
| Verde técnico | `#00D18F` | `#047857` |
| Ámbar / taller | `#F5A524` | `#B45309` |
| Rojo forense | `#FF5C5C` | `#B91C1C` |
| Violeta | `#A78BFA` | `#6D28D9` |

Si usas un fondo claro, tendrás que ajustar también `item`, `muted` y `tip`, o
el texto quedará ilegible.

---

## 3. Ajustar el fondo

```jsonc
"background": {
  "hex_pattern": true,   // trama de panal
  "watermark":   true,   // emblema gigante, muy tenue, abajo a la derecha
  "top_rule":    true    // filete de acento en el borde superior
}
```

Con los tres en `false` queda un degradado limpio con viñeta.

¿Quieres una foto o una imagen propia de fondo? Genera el tema y después
sustituye `background.png` en cada carpeta de resolución por tu imagen, con las
mismas dimensiones exactas. Ten en cuenta que **`build_theme.py` la
sobrescribirá** la próxima vez que lo ejecutes.

---

## 4. Cambiar las categorías del menú

Las categorías no están en `brand.json`, sino en
`usb/ventoy/ventoy.json`, porque son carpetas reales de la USB.

Para añadir una sexta categoría, por ejemplo `06_UTILIDADES`:

1. Crea la carpeta `06_UTILIDADES` en la raíz de la USB.
2. En `ventoy.json`, añade una entrada en cada una de las tres secciones:

```jsonc
// menu_alias  -> el nombre que se ve
{ "dir": "/06_UTILIDADES", "alias": "Utilidades y controladores" },

// menu_class  -> el icono
{ "dir": "/06_UTILIDADES", "class": "settings" },
{ "parent": "/06_UTILIDADES", "class": "settings" },

// menu_tip    -> las dos líneas de descripción
{
  "dir": "/06_UTILIDADES",
  "tip1": "Controladores, utilidades y portables.",
  "tip2": "Herramientas sueltas que no arrancan como sistema."
}
```

3. Ejecuta `python tools/build_theme.py` para que el menú F6 liste la categoría
   nueva.

El valor de `class` debe corresponder a un icono existente en
`tools/assets/icons/`. Los disponibles incluyen: `install`, `repair`, `clone`,
`diag`, `linux`, `settings`, `info`, `boot_windows`, `boot_disk`, `boot_uefi`,
`reboot`, `poweroff`. La lista completa es el contenido de esa carpeta.

---

## 5. Añadir o cambiar iconos

Los iconos maestros viven en `tools/assets/icons/`, en PNG de 32×32 con fondo
transparente. Para sustituir uno, reemplaza el archivo conservando el nombre y
vuelve a generar: se recoloreará y se reducirá a 24×24 para las resoluciones
pequeñas automáticamente.

Para añadir uno nuevo, guarda `mi_icono.png` de 32×32 en esa carpeta y
referéncialo en `ventoy.json` como `"class": "mi_icono"`.

---

## 6. Añadir una resolución

Las medidas de cada modo de vídeo están en el diccionario `LAYOUT`, al
principio de la sección de layout de `tools/build_theme.py`. Para añadir, por
ejemplo, 2560×1440, copia el bloque de `1920x1080` y escala los valores:

```python
"2560x1440": dict(
    logo=(640, 200), logo_top=77, prompt_top=315, font_small=22, font_item=29,
    menu_w=1333, menu_top=376, menu_h=720, item_h=64, item_pad=21, item_gap=11,
    icon=42, icon_gap=21, scrollbar=8, corner=26, panel=(747, 480),
    select=(1333, 64), select_side=13, slider=(8, 37, 8),
    flags_top=1315, hotkey_top=1383, tip_top=1117, ventoy_off=320,
),
```

Después añádela a `resolutions` en `brand.json`, **la más grande primero**:

```jsonc
"resolutions": ["2560x1440", "1920x1080", "1366x768", "1024x768"]
```

El generador actualiza `gfxmode` y la lista de `theme.file` en `ventoy.json`
por ti. Ventoy elige el primer modo que la tarjeta gráfica acepte.

> Cuidado con los iconos: los maestros son de 32×32, así que en 2560×1440 se
> ampliarán y perderán nitidez. Para un resultado impecable, sustitúyelos por
> versiones de 48×48.

---

## 7. Cambiar el menú extendido (tecla F6)

`usb/ventoy/ventoy_grub.cfg` **se genera**; no lo edites directamente o
perderás los cambios. La fuente es
`tools/assets/ventoy_grub.cfg.tmpl`, donde puedes añadir tus propias entradas
de GRUB:

```grub
menuentry "Mi herramienta" --class=settings {{
    echo "Arrancando..."
}}
```

Ojo: la plantilla se procesa con `str.format()` de Python, así que **las llaves
de GRUB van dobladas** (`{{` y `}}`). Los marcadores disponibles son
`{PROJECT_NAME}`, `{PROJECT_UPPER}` y `{CATEGORIES}`.

---

## 8. Cambiar las tipografías

El menú de GRUB no usa TTF, sino el formato `.pf2`. Las incluidas son Poppins
en seis variantes. Para usar otra familia necesitas la herramienta
`grub-mkfont` (viene con GRUB en Linux):

```bash
grub-mkfont -s 22 -o MiFuente-Medium-22.pf2 MiFuente-Medium.ttf
```

Genera un `.pf2` por cada tamaño que necesites, colócalos en
`tools/assets/fonts/`, borra `usb/ventoy/theme/<tu tema>/fonts/` y vuelve a
generar. Después ajusta los nombres en `build_theme.py` (las cadenas
`Poppins Regular 17`, `Poppins Medium 22`, etc.), que deben coincidir con el
nombre interno de la fuente y su tamaño.

Las imágenes del logo usan una fuente TrueType aparte. El generador busca, por
este orden: `tools/assets/fonts/Poppins-Bold.ttf`, luego Montserrat, luego las
fuentes del sistema (Segoe UI, Arial, DejaVu). Para que el logo use exactamente
la misma tipografía que el menú, descarga
[Poppins](https://fonts.google.com/specimen/Poppins) y copia `Poppins-Bold.ttf`
y `Poppins-Medium.ttf` a `tools/assets/fonts/`.

---

## 9. Ver el resultado sin arrancar un equipo

```bash
python tools/make_previews.py
```

Compone las capturas de `docs/img/` usando las mismas imágenes, las mismas
medidas de `theme.txt` y los mismos textos de `ventoy.json` que usará la USB.
No es un render aproximado: si algo se ve mal en la captura, se verá mal al
arrancar.

Es la forma rápida de comprobar que un nombre largo entra, que un color nuevo
contrasta y que las descripciones no se salen de la pantalla.

---

## Comandos útiles

```bash
python tools/build_theme.py                    # todo
python tools/build_theme.py --only 1920x1080   # solo una resolución (más rápido)
python tools/build_theme.py --no-brand         # sin reexportar los logos de brand/
python tools/build_theme.py --config otra.json # usar otro archivo de marca
python tools/make_previews.py                  # regenerar capturas
```

Mantener varios perfiles de marca es tan simple como tener varios archivos:

```bash
python tools/build_theme.py --config marcas/taller-perez.json
python tools/build_theme.py --config marcas/soporte-interno.json
```
