# Historial de cargas — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar cada uso del sistema (Sílabos y Guías) en un historial persistente, con página `/historial`, botón en la cabecera, correcciones manuales y siembra de lo ya cargado.

**Architecture:** Módulo `core/historial.py` sobre SQLite (stdlib). `app.py` registra eventos al terminar cada endpoint (sin romper el flujo si el historial falla) y expone `/api/historial*`. Página estática `static/historial.html`; botón en las tres cabeceras.

**Tech Stack:** Python 3.12, FastAPI, sqlite3, HTML/JS sin dependencias, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-11-14-historial-design.md` (mockup `diseno/mockup_historial.html`).

## Global Constraints
- Nunca guardar el token ni el contenido del PDF; solo nombre de archivo.
- Un error del historial nunca cambia la respuesta de analizar/publicar (se traga y se registra en consola).
- Fechas en hora de Ecuador `-05:00`, ISO `YYYY-MM-DDTHH:MM`; las sembradas sin hora usan `YYYY-MM-DD`.
- `HISTORIAL=0` → endpoints 404 y botón oculto; `HISTORIAL_CLAVE` → API exige cabecera `X-Historial-Clave` o `?clave=`.
- Ruta `HISTORIAL_DB` (por defecto `<raíz>/datos/historial.sqlite`); Docker: volumen `historial_data:/datos`.
- Todo cambio se registra en `progress.md`.

## Review Focus
- Historial apagado o base no escribible: analizar y publicar siguen funcionando (T2: `test_falla_historial_no_rompe_publicar`).
- Siembra ejecutada dos veces (reinicio del contenedor): no duplica filas (T1: `test_siembra_idempotente`).
- Texto del usuario con HTML en la nota de corrección o en el nombre del PDF: se muestra escapado (T4: `esc()` en toda celda; T3 devuelve texto crudo).
- Clave configurada y petición sin clave: 401, y la página muestra pedir la clave (T3: `test_clave_requerida`).
- CSV abierto en Excel con tildes: UTF-8 con BOM y separador `;` (T3: `test_csv`).

---

### Task 1: Almacén SQLite, siembra y correcciones

**Files:** Create `sistema/core/historial.py` · Test `sistema/tests/test_historial.py`

**Interfaces — Produces:**
- `ruta() -> str`, `habilitado() -> bool`, `clave() -> str` (vacía = sin clave)
- `registrar(tipo: str, accion: str, resultado: str, archivos=(), curso: dict|None=None, detalle='', enlaces=(), reconstruido=False, fuente='', fecha: str|None=None) -> int|None` — `tipo` ∈ {'silabos','guias'}; `resultado` ∈ {'ok','error','avisos'}; `enlaces` = [{texto, url}]; devuelve None si falla o está apagado.
- `listar(tipo=None, curso=None, texto=None, orden='desc') -> list[dict]` — dict con `id, fecha, tipo, archivos(list), curso_id, curso_nombre, accion, resultado, detalle, enlaces(list), reconstruido(bool), fuente, correccion (dict|None: resultado, nota, fecha)`.
- `corregir(id: int, resultado: str, nota: str) -> dict` · `quitar_correccion(id: int) -> dict` (KeyError si no existe)
- `sembrar() -> int` (filas insertadas; 0 si ya sembrado) · `resumen(filas) -> dict(eventos, cursos, publicaciones, errores)` (usa el resultado corregido si lo hay).

- [ ] Step 1: tests `test_registrar_y_listar` (filtros tipo/curso/texto, orden), `test_no_guarda_token` (registrar con detalle normal; columnas de la tabla no incluyen 'token'), `test_correccion_conserva_original`, `test_quitar_correccion`, `test_siembra_idempotente` (8 filas, segunda llamada 0), `test_resumen_usa_correccion`, `test_apagado` (`HISTORIAL=0` → registrar devuelve None).
- [ ] Step 2: correr y ver fallar. Step 3: implementar (una conexión por operación, `threading.Lock`, `CREATE TABLE IF NOT EXISTS eventos/meta`). Siembra = las 8 filas reconstruidas del mockup. Step 4: pasar.

### Task 2: Registrar eventos en los flujos

**Files:** Modify `sistema/app.py` · Test `sistema/tests/test_historial.py`

**Interfaces — Consumes:** `historial.registrar`. Guardar en la sesión `s['_archivos']` (lista de nombres) al analizar.
- Sílabos: analizar ok → `accion='Analizado'` con `detalle` = n momentos y avisos graves; analizar 422 → `resultado='error'` con el mensaje; publicar → `accion='Publicado Momentos …'`, ok si todos ok, `avisos` si mezcla, error si 409/ninguno; enlaces a cada página; restaurar → `accion='Restaurado Momento N'`.
- Guías: analizar; publicar → `accion='PAE creadas: PAE3, …'` con enlaces a tarea y rúbrica; deshacer → `accion='Deshecho: PAEn'`.
- Llamar `historial.sembrar()` al iniciar la app (evento startup), envuelto en try.
- [ ] Tests: `test_flujo_silabos_queda_en_historial`, `test_flujo_guias_queda_en_historial`, `test_error_de_analisis_queda_registrado`, `test_falla_historial_no_rompe_publicar` (monkeypatch registrar → raise).

### Task 3: API del historial, CSV y protección

**Files:** Modify `sistema/app.py` · Test `sistema/tests/test_historial.py`
- `GET /api/historial/estado` → `{habilitado, requiere_clave}` (siempre 200).
- `GET /api/historial?tipo&curso&q&orden` → `{eventos, resumen, cursos:[{id,nombre}]}`.
- `POST /api/historial/{id}/corregir` body `{resultado, nota}` (resultado ∈ ok/error/avisos; nota ≤ 500) · `DELETE /api/historial/{id}/correccion`.
- `GET /api/historial.csv` → UTF-8 BOM, `;`, columnas: fecha, tipo, archivos, curso, acción, resultado, resultado corregido, nota, reconstruido, fuente.
- `GET /historial` → `static/historial.html`.
- [ ] Tests: `test_api_listar_y_corregir`, `test_csv`, `test_clave_requerida` (401 sin clave, 200 con cabecera), `test_apagado_404`.

### Task 4: Página Historial y botón en cabeceras

**Files:** Create `sistema/static/historial.html` · Modify `static/menu.html`, `static/index.html`, `static/guias.html`
- Botón `<a class="hist" href="historial">🕘 Historial</a>` arriba a la derecha (estilo del mockup); oculto si `estado.habilitado` es false.
- Página según mockup: KPIs, filtros, tabla, detalle desplegable, "✎ Corregir" con editor en línea, "Quitar corrección", "⬇ Exportar CSV", pedir clave si `requiere_clave` (guardada en sessionStorage).
- [ ] Test `test_paginas_tienen_boton_historial` (las 3 páginas contienen `href="historial"`; `/historial` 200). Verificación en navegador.

### Task 5: Docker, verificación y registro

**Files:** Modify `docker-compose.yml`, `.gitignore`, `sistema/README.md`, `progress.md`
- Volumen `historial_data:/datos` y `HISTORIAL_DB: /datos/historial.sqlite` en `app`; `datos/` en `.gitignore`.
- [ ] Suite completa; `docker compose up -d --build`; comprobar en navegador: siembra visible, flujo con Canvas simulado registrado, corrección, CSV; reiniciar contenedor y ver que persiste. Entrada en `progress.md`.
