# Workspace de mods de Hedgehod Launcher

## Crear un mod

Pulsa **Crear mod** y completa nombre del proyecto, versión, autor, tipo y juego objetivo. El launcher crea un proyecto bajo `Data Games/<juego>/Mod Projects/` con `mod.ini`, `project.json`, `Data/` y `Scripts/`. No copia ni distribuye archivos del juego.

La carpeta de cada perfil está en `Data Games/<juego>/`; contiene `mods/` para los mods instalados y `Mod Projects/` para los editables. La personalización y los perfiles del launcher se guardan en `configs/hedgehod-launcher.json`. Los datos de una instalación anterior en `Game Data/` se mueven al nuevo perfil si el destino aún no existe.

Desde un proyecto puedes abrir el editor de código, el Workspace de sprites, la carpeta del proyecto, instalarlo en `mods/` o exportar un paquete para compartir. **Mods / compartir** reúne proyectos locales y permite importar `.hmod` y `.smmd` de otras personas, exportarlos e instalarlos. Sonic Mania usa `.smmd`; los demás juegos usan `.hmod`. Los paquetes incluyen hashes SHA-256 para revisar la integridad del contenido; no son firmas criptográficas de identidad.

La función de compartir genera e importa archivos locales. Publicar en un catálogo en línea necesita un servidor/cuenta de comunidad que este programa todavía no incluye. Los usuarios pueden compartir los paquetes mediante el servicio que elijan.

## Código de mods y código fuente

El editor abre y guarda scripts del proyecto, y también archivos de código que el usuario elija (`.txt`, `.cpp`, `.h`, `.c`, `.ini`, `.xml`, `.json`, `.lua`). Guarda los scripts nuevos en la carpeta `Scripts/`. El editor no compila ni ejecuta código. Para editar o compilar una decompilación, abre el código fuente obtenido legalmente y usa la cadena de compilación correspondiente a esa versión de RSDK; cambiar archivos de datos no equivale a cambiar el código del ejecutable comercial.

La estructura y los nombres de script que acepta el motor cambian entre juegos y builds. La plantilla crea carpetas y metadatos; no garantiza que cualquier script sea compatible. Revisa `log.txt` y prueba los cambios en una copia del juego.

## Biblioteca y sprites

1. Exporta el `Data.rsdk` de tu copia del juego con RetroED (Tools → RSDK Unpacker → Export DataPack).
2. Abre **Workspace** y pulsa **Elegir carpeta Data…**.
3. Explora **Stages**, **Players** y **Misc**. Selecciona un asset para revisar el tamaño, formato y límites.
4. Pulsa **Editar sprite** en la vista previa para abrir el editor de píxeles integrado. Incluye pincel, borrador, relleno, cuentagotas, paleta, zoom con desplazamiento, deshacer y selección de fotogramas GIF.
5. **Guardar en mod…** copia la edición a `Data/<ruta-original>` de un proyecto del mismo juego; **Guardar copia…** exporta PNG o GIF a `Data Games/<juego>/Sprite Edits/`. Ninguna opción sobrescribe el asset original.
6. **Abrir en Aseprite / LibreSprite** permite usar el editor externo configurado en Ajustes para tareas avanzadas.

## Animaciones de personaje

En **Players**, selecciona una acción (Idle, Walk, Running, Spin, Jump, Roll, Spin Dash o Peel Out) y asígnale un sprite. Los GIF animados se reproducen en bucle al seleccionarlos. Para una hoja estática, usa **Configurar tira de frames…** o abre el editor nativo, elige **Selección ▭**, marca la región y ajusta el marco con las esquinas. El HUD muestra el recorte; selecciona la acción, indica cuántos frames contiene y pulsa **Asignar selección a movimiento**. Cada acción conserva su propia ruta y configuración en el perfil del juego.

El preview usa vecino más cercano para conservar los píxeles. Los GIF animados se guardan con sus frames y duración. Mantén la ruta relativa, paleta y dimensiones esperadas por el juego cuando prepares recursos para un mod.

## Editor externo: Aseprite o LibreSprite

El editor de píxeles básico está integrado en el launcher. Para funciones avanzadas, configura el ejecutable de Aseprite o LibreSprite en **Ajustes → Editor externo**; se abrirá como aplicación independiente y el launcher no incluye sus binarios. LibreSprite puede obtenerse desde su [página oficial de la versión 1.3](https://github.com/LibreSprite/LibreSprite/releases/tag/v1.3); sus créditos y licencia pertenecen a [LibreSprite](https://github.com/LibreSprite/LibreSprite/blob/v1.3/LICENSE.txt).

La carpeta `Data/` del proyecto conserva la estructura de la exportación seleccionada. Que el motor lea un recurso suelto depende del formato, la ruta y el loader de mods de la build de RSDK usada; si requiere reempaquetado, hazlo con herramientas compatibles y prueba una copia del juego.
