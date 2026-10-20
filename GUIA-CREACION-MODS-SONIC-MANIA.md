# Guía para crear mods de Sonic Mania con Hedgehod Launcher

## Antes de empezar

Necesitas una instalación legítima de Sonic Mania y un motor RSDKv5 decompilado compatible. Para el perfil de Mania, el directorio debe contener el `Data.rsdk` correspondiente y `Game.dll` compatible con ese motor; algunas builds pueden requerir archivos adicionales. El launcher organiza y abre el perfil: no convierte motores ni comprueba que archivos de versiones distintas sean compatibles.

Mantén esos archivos en `Game Data/Sonic Mania/`. No incluyas `Data.rsdk`, `Game.dll` ni recursos comerciales extraídos en un paquete de mod o en una publicación.

## Estructura básica de un mod

Crea una carpeta por mod dentro de:

```text
Game Data/Sonic Mania/mods/NombreDelMod/
├── mod.ini
└── Data/
    └── ... (solo archivos propios o modificados, conservando rutas del juego)
```

El cargador necesita un `mod.ini` en la raíz de cada carpeta del mod. Usa esta plantilla como punto de partida, y ajusta `TargetVersion` a la versión esperada por el motor que uses:

```ini
Name=Mi mod
Description=Una breve descripción
Author=Tu nombre o equipo
Version=1.0
TargetVersion=5
```

Para cambiar un recurso, coloca la versión modificada dentro de `Data/` siguiendo la misma ruta relativa que usa el juego. Incluye únicamente trabajo original del mod o cambios permitidos; no copies el datapack base completo.

## Activarlo y probarlo

1. Copia la carpeta del mod a `Game Data/Sonic Mania/mods/`.
2. En Hedgehod Launcher, selecciona Sonic Mania y guarda el perfil.
3. Inicia el motor compatible. Abre el Dev Menu del motor (en builds compatibles suele abrirse con `Esc`), entra en Mods y activa el mod. La lista y su prioridad dependen de la build del motor.
4. Prueba primero un mod a la vez. Revisa `log.txt` junto al ejecutable si no aparece o no carga.
5. Para mostrar una portada propia, selecciona el mod en “Portada de” y usa “Editar portada…”. Esa imagen solo personaliza el launcher.

## Herramientas y compatibilidad

- La guía de RetroED indica usar `RSDKv5FileList.txt` al inspeccionar datapacks de Sonic Mania. Úsalo con una copia local obtenida legalmente y conserva sus recursos base privados.
- Los mods hechos para la edición comercial de Steam que dependen de DLL o de su loader no son automáticamente compatibles con la decompilación. Usa mods preparados para el mismo motor; la guía del loader documenta la compatibilidad de GameAPI.
- Comparte código, mapas, gráficos y sonidos creados por tu equipo, junto con instrucciones y créditos. No subas el `Data.rsdk`, `Game.dll`, ejecutables del juego ni extracciones de recursos de SEGA.
- En la publicación indica versión exacta del motor, `TargetVersion`, dependencias, orden recomendado, controles y cómo desactivar/eliminar el mod. Guarda una copia de tus archivos originales antes de experimentar.

## Enlaces oficiales

- [Configuración de Sonic Mania RSDKv5](https://rsdkmodding.com/Guides/RSDKv5/Decompilation/ModSetup/)
- [Cargador de mods RSDKv5](https://rsdkmodding.com/RSDKv5/Decompilation/ModLoader/)
- [Configuración de decompilación de Sonic Mania](https://rsdkmodding.com/Guides/RSDKv5/Decompilation/Setup/)
- [Extraer/inspeccionar datapacks con RetroED](https://rsdkmodding.com/Guides/RetroED/ExtractDatapack/)
- [Datapack de Sonic Mania](https://rsdkmodding.com/Guides/Games/SonicMania/Datapack/)
