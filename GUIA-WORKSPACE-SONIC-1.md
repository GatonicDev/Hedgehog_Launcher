# Workspace Hedgehod · Sonic 1

## Alcance

La primera versión del Workspace se centra en aprender a modificar Sonic 1 con un perfil RSDKv4. Su editor de sprite permite cargar una imagen/GIF y probar tamaño, posición y cielo en una escena de muestra. El editor de código aplica un DSL pequeño a esa vista previa. No ejecuta RetroScript, no modifica `Data.rsdk` y no compila ni exporta todavía un mod nativo.

## Reconocer archivos y recursos

El `Data.rsdk` del perfil Sonic 1 aportado en este proyecto tiene cabecera `RSDKvB`, coherente con la familia usada por Sonic 1 móvil/RSDKv4. Una firma no identifica por sí sola la build/revisión exacta. Para indexar una copia local, RetroED → Tools → RSDK Unpacker → selecciona `RSDKv4FileList.txt` para Sonic 1/2 móvil. Verifica que el listado no se llene de nombres ambiguos `File #.bin`; una lista incorrecta puede producir rutas poco informativas.

No hay aquí un inventario verificado de los nombres concretos de todos los sprites/stages del datapack. Usa los paths que entregue el índice local. No supongas nombres como `GreenHill/...` sin confirmarlos.

## Sprites

Las hojas gráficas de Retro Engine normalmente usan GIF con paleta indexada. Para modificar una hoja, trabaja sobre una copia, conserva la paleta, dimensiones, transparencia y orden de frames. Si el juego usa archivos de animación que apuntan a esa hoja, mantén consistencia entre los frames y esas referencias. Coloca dentro del mod solo el archivo que cambiaste y la misma ruta relativa bajo `Data/`.

Estructura típica de loader RSDKv4:

```text
Game Data/Sonic 1/mods/MiSpriteMod/
├── mod.ini
└── Data/
    └── Sprites/
        └── (ruta exacta según el índice del datapack)
```

## Stages, fondos y objetos

RetroED es la herramienta documentada para ver/editar escenas. El Scene Editor permite seleccionar capas, pintar/borrar tiles o chunks, mover entidades y ajustar propiedades visibles del stage. Para trabajar con la lógica y catálogo de objetos, configura Game Link con lógica compatible del juego; si Game Link no carga, no des por válidos los nombres/IDs mostrados en una guía genérica.

Para un fondo, identifica qué capa y configuración de scroll/parallax usa la escena, modifica una copia y verifica movimiento de cámara a más de una velocidad. La previsualización de Hedgehod solo ilustra cambios de color/posición/título; no es un importador/exportador de escenas binarias RSDK.

## Scripts y activación

El decompilado RSDKv4 con loader busca subcarpetas en `mods/`, con `mod.ini` en la raíz. Un mod puede proporcionar contenido bajo `Data/`; los archivos conservan la estructura relativa al juego. Para scripts, el loader documenta el directorio y flag de scripts de texto según el engine. Si también se usa RSDKv5U en modo legacy v4, `TargetVersion=4` indica esa versión objetivo; no se necesita esa etiqueta para que la decompilación RSDKv4 nativa liste un mod. Activa el mod desde el menú y consulta `log.txt` si el juego lo desactiva.

Plantilla mínima:

```ini
Name=Mi mod
Description=Cambio visual de Sonic 1
Author=Tu equipo
Version=1.0
TargetVersion=4
```

Comparte únicamente tu código y recursos originales o sus deltas permitidos. No publiques el datapack comercial, sus assets extraídos, ni ejecutables/dlls del juego.

## Proyectos `.hmod` / `.smmd`

El Workspace guarda un JSON con extensión de proyecto elegida. Campos actuales: `format`, `formatVersion`, `signature`, `game.id`, `project`, `preview.code` y `preview.sprite`. La firma lógica incluye juego y familia de motor (por ejemplo `HMOD:SONIC_1:RSDKv4:v1`, `HMOD:SONIC_CD:RSDKv3:v1`, `HMOD:SONIC_3:UNVERIFIED:v1` o `SMMD:SONIC_MANIA:RSDKv5:v1`). `.smmd` se reserva para Sonic Mania; Sonic 1 usa `.hmod`.

El archivo es reabrible en el prototipo/Workspace y conserva el arte seleccionado embebido. El importador comprueba formato, extensión, firma y juego objetivo. SHA-256 es una suma de integridad si el navegador la soporta; no es una firma digital de autoría. Este formato propio todavía no es ejecutable en RSDK: hace falta implementar un exportador que escriba un mod nativo válido y pruebe sus rutas y scripts contra una build de RSDKv4 concreta. Para Sonic 2 la familia se etiqueta RSDKv4, Sonic CD RSDKv3, Sonic Mania RSDKv5; la compatibilidad concreta de Sonic 3 aún queda sin verificar.

## Otras versiones

Aunque el manifiesto deja etiquetar Sonic 2, Sonic 3 & Knuckles, Sonic CD y Sonic Mania, las guías y edición real de juego están marcadas como Sonic 1 inicial. Cada versión requiere file list, revisión y lógica compatibles. Se activarán editores por juego cuando se verifique el contenido y el motor correspondientes.

## Referencias primarias

- https://rsdkmodding.com/Guides/RetroED/ExtractDatapack/
- https://rsdkmodding.com/Guides/Spritesheets/
- https://rsdkmodding.com/Tools/RetroED/SceneEditor/
- https://rsdkmodding.com/Guides/RetroED/GameLogicLink/
- https://rsdkmodding.com/RSDKv4/Decompilation/ModLoader/
- https://rsdkmodding.com/Guides/RSDKv4/Decompilation/Setup/
