# Hedgehod Launcher

Launcher comunitario para organizar instalaciones locales de juegos Sonic basados en Retro Engine y preparar proyectos de mods. El programa no distribuye juegos, `Data.rsdk`, ejecutables ni recursos extraídos.

## Estado

Versión de escritorio para Windows en desarrollo. Incluye biblioteca de perfiles, editor de sprites, selección de fotogramas clave y exportación de recursos/declaraciones para proyectos de mod. La integración con el formato de animación `.ani` de RSDKv4 todavía requiere trabajo adicional.

## Ejecutar desde el código

1. Instala Python 3.10 o posterior.
2. Instala dependencias: `python -m pip install -r requirements.txt`.
3. Ejecuta `python hedgehod_launcher.py` o `iniciar_hedgehod_launcher.bat`.
4. Configura tus propios archivos locales desde el launcher. No copies archivos comerciales al repositorio.

Para crear el ejecutable de Windows, abre PowerShell en esta carpeta y ejecuta `python -m PyInstaller --noconfirm HedgehodLauncher-Keyframes.spec`.

## Recursos visuales

El patrón propio `sonic-grid-tile.png` está incluido. Las carátulas, música, símbolos/arte de Sonic y cualquier otro recurso con derechos de terceros se omiten del repositorio. Si quieres esos elementos localmente, colócalos junto al programa y usa arte que tengas derecho a utilizar. La app permite escoger imágenes propias.

## Desarrollo de mods

Consulta `GUIA-WORKSPACE-SONIC-1.md`, `GUIA-CREACION-MODS-SONIC-MANIA.md` e `INTEGRACION-LIBRESPRITE.md`. Los mods deben incluir solo contenido creado por su autor y declarar el juego objetivo; no incluyas `Data.rsdk`, DLL comerciales ni recursos extraídos.

## Licencia

El código de Hedgehod Launcher se distribuye bajo la licencia MIT. Consulta el archivo `LICENSE`. Las marcas, personajes, juegos, música y otros recursos de terceros mencionados no forman parte de esta licencia.
