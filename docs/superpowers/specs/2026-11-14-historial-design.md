# Historial de cargas — diseño corto (aprobado 2026-11-14)

**Intención.** El usuario quiere *su propio control* de todo lo que ha cargado con el sistema: qué sílabo o guías subió,
a qué curso, qué se publicó y con qué resultado. Mockup aprobado: `diseno/mockup_historial.html`.

**Objetivos**
- Botón pequeño **"🕘 Historial"** en la esquina superior derecha de las tres pantallas (menú, Sílabos, Guías).
- Página `/historial`: resumen (eventos, cursos, publicaciones, errores), filtros (tipo, curso, texto, orden),
  tabla (fecha, tipo, archivos, curso, acción, resultado), detalle desplegable, enlaces a Canvas, **Exportar CSV**.
- Registro automático de: analizar, publicar, restaurar (Sílabos); analizar, publicar/crear PAE, deshacer (Guías);
  con resultado ok / error / avisos y un detalle breve.
- **Corrección manual** por registro: resultado real + nota; el original queda tachado; la corrección se puede quitar.
- **Siembra** de lo ya cargado, marcado "reconstruido" con su fuente (progress.md, registro de Docker, Descargas).

**No objetivos.** Historial por docente/usuarios, auditoría para coordinación, reconstruir desde Canvas.

**Anti-objetivos.** Guardar el token o el PDF. Inventar nombres de archivo que no se registraron. Perder el historial
al reconstruir Docker. Que un fallo al escribir el historial impida analizar o publicar.

**Enfoques considerados**
- **A. SQLite en un volumen de Docker** — elegido por el usuario: dura, filtra fácil, sin dependencias nuevas.
- B. Archivo de texto por líneas — simple pero torpe para filtrar y con riesgo de mezclas concurrentes.
- C. localStorage del navegador — se pierde al limpiar el navegador; no registra lo que pasa en el servidor.

**Restricciones.** Protección: en el equipo local funciona sin clave; `HISTORIAL=0` lo apaga; si `HISTORIAL_CLAVE`
está definida, la API exige esa clave (para cuando se publique en un servidor). Enlaces relativos (deploy bajo
`/aulasvirtuales/`).

**Decisiones del constructor (mías).** Ruta `HISTORIAL_DB` (Docker: `/datos/historial.sqlite`, local:
`datos/historial.sqlite`, ignorado por git); siembra idempotente con marca en tabla `meta`; fechas en hora de Ecuador.
