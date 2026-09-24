# Solución de problemas

Ordenado por el momento en que suele aparecer el problema: al preparar la USB,
al arrancar, o al personalizar el tema.

---

## Al preparar la USB

### Ventoy2Disk no detecta la memoria

- Prueba otro puerto USB, preferiblemente uno trasero y USB 2.0.
- Ejecútalo **como administrador**.
- Algunos antivirus bloquean el acceso directo al disco: desactívalo un momento.
- Si la memoria aparece en *Administración de discos* pero no en Ventoy, puede
  estar en un estado raro. Límpiala antes:

  ```bat
  diskpart
  list disk
  select disk N        :: ¡el número de tu USB, comprueba el tamaño!
  clean
  exit
  ```

### No puedo copiar una ISO de más de 4 GB

La partición quedó en FAT32, que no admite archivos de ese tamaño. Reinstala
Ventoy y en *Option → Partition Style* deja el sistema de archivos en **exFAT**
(es el que usa por defecto). Reinstalar borra el contenido de la memoria.

### Copiar a la USB va lentísimo

Normal en memorias USB 2.0 o de gama baja: una ISO de Windows son 5–6 GB. Si
tarda horas, prueba otro puerto y evita concentradores (hubs) sin alimentación.

---

## Al arrancar

### El equipo no arranca desde la USB

1. Entra al **menú de arranque** (`F9`, `F12`, `Esc`… según la marca) en vez de
   confiar en el orden de arranque de la BIOS.
2. Si la USB no aparece en la lista, en la BIOS/UEFI:
   - Desactiva **Secure Boot** (o reinstala Ventoy con *Secure Boot Support*).
   - Desactiva **Fast Boot**.
   - Activa el soporte **USB Legacy / CSM** si el equipo es antiguo.
3. En equipos muy nuevos puede hacer falta instalar Ventoy en modo **GPT**; en
   equipos anteriores a 2012, en modo **MBR**.

### Arranca Ventoy pero con su tema azul por defecto

Ventoy no está encontrando o no está aceptando `ventoy.json`. En orden:

1. **Comprueba la ruta.** Tiene que ser exactamente `X:\ventoy\ventoy.json`,
   con `ventoy` en minúsculas y en la **raíz** de la partición. Un error
   clásico es acabar con `X:\usb\ventoy\ventoy.json`.
2. **Valida el JSON.** Si tiene un error de sintaxis, Ventoy ignora el archivo
   entero sin avisar:

   ```bash
   python -m json.tool X:\ventoy\ventoy.json
   ```

   Lo que más falla: una coma de más antes de un `]` o un `}`, o comillas
   tipográficas (`"`) en lugar de comillas rectas (`"`) por haber editado en
   Word.
3. **Comprueba que las rutas del tema existen.** Las de
   `"theme": { "file": [...] }` deben corresponder a archivos reales dentro de
   la USB. Si cambiaste `theme_dir` y copiaste la carpeta antigua, no cuadran.

### Se ve el tema, pero sin logo ni fondo

Faltan imágenes en la carpeta del tema, o `theme.txt` está en otro sitio.
Vuelve a copiar la carpeta `theme/<tu tema>/` completa, con sus tres
subcarpetas de resolución y `fonts/`.

### Los acentos salen como cuadros o desaparecen

Falta alguna fuente `.pf2`. Copia de nuevo `theme/<tu tema>/fonts/` entera y
verifica que `ventoy.json` las lista todas en `"fonts": [...]`.

### La pantalla se ve deformada, cortada o descentrada

El monitor está usando una resolución para la que no hay tema. Pulsa `F3` para
cambiar de modo de vídeo, o añade tu resolución siguiendo la
[sección 6 de PERSONALIZACION.md](PERSONALIZACION.md#6-añadir-una-resolución).

En pantallas panorámicas raras (21:9, por ejemplo) el fondo se estira. La
opción `"resolution_fit": 1` de `ventoy.json` reduce el efecto.

### Las ISOs aparecen con su nombre de archivo en vez del nombre bonito

La ruta del `menu_alias` no coincide con el archivo real. Debe coincidir
**carácter por carácter**:

- empieza con `/`;
- usa barras normales `/`, nunca `\`;
- respeta mayúsculas, espacios, acentos y la extensión.

Truco: en Windows, `Mayús` + clic derecho sobre el archivo → *Copiar como
ruta*, y de ahí adapta las barras.

### Una ISO aparece en el menú pero no arranca

No es cosa del tema: es la ISO o el equipo.

- Verifica el archivo con su suma SHA-256 (Ventoy la calcula: selecciona la
  entrada y pulsa `F2`... o usa `certutil -hashfile archivo.iso SHA256`).
- Prueba otro modo de arranque de Ventoy sobre esa entrada: `Ctrl+R` (modo
  grub2), `Ctrl+W` (modo wimboot) o `Ctrl+D` (memdisk).
- Algunas ISOs muy antiguas solo arrancan en modo Legacy/BIOS, no en UEFI.

### Windows 11 se queja de TPM 2.0 o pide cuenta Microsoft

Ya viene resuelto: `VTOY_WIN11_BYPASS_CHECK` y `VTOY_WIN11_BYPASS_NRO` están en
`"1"` en `ventoy.json`. Si aun así aparece, confirma que estás arrancando desde
el menú del kit (con el tema aplicado) y no desde otra USB.

---

## Al personalizar el tema

### `ModuleNotFoundError: No module named 'PIL'`

```bash
pip install -r tools/requirements.txt
```

Si tienes varias versiones de Python instaladas, usa la misma con la que
ejecutas el script: `python -m pip install Pillow`.

### `No se encontro ninguna fuente TrueType utilizable`

El generador no halló ninguna fuente para dibujar el logo. Descarga
[Poppins](https://fonts.google.com/specimen/Poppins) y copia `Poppins-Bold.ttf`
y `Poppins-Medium.ttf` a `tools/assets/fonts/`. En Linux también sirve
instalar `fonts-dejavu`.

### El nombre del logo se ve muy pequeño

El logo se escala para caber entero en el espacio disponible, así que un texto
largo se encoge. Reparte el nombre entre `line_top` y `line_main`, o acorta el
`tagline`, que es la línea que más ancho consume.

### Cambié `accent` pero los iconos siguen azules

Los iconos se regeneran al ejecutar el generador. Comprueba que terminó sin
errores y que estás mirando la carpeta correcta (`theme_dir` puede haber
cambiado y haber creado una carpeta nueva). Y recuerda volver a copiar la
carpeta a la USB.

### Cambié `theme_dir` y ahora hay dos carpetas de tema

Es lo esperado: el generador crea la nueva y deja la anterior. Borra a mano la
que ya no uses dentro de `usb/ventoy/theme/`.

### Edité `ventoy_grub.cfg` y mis cambios desaparecieron

Ese archivo se genera. Edita `tools/assets/ventoy_grub.cfg.tmpl` y vuelve a
ejecutar el generador. Recuerda doblar las llaves (`{{` y `}}`) en las entradas
de GRUB.

---

## Si nada de esto ayuda

- Documentación oficial de Ventoy: <https://www.ventoy.net/en/doc_start.html>
- Referencia de `ventoy.json`: <https://www.ventoy.net/en/plugin_start.html>
- Problemas del propio Ventoy: <https://github.com/ventoy/Ventoy/issues>

Al abrir una incidencia en este repositorio, indica: versión de Ventoy, sistema
desde el que preparaste la USB, contenido de tu `ventoy.json` y una foto de la
pantalla si el fallo ocurre al arrancar.
