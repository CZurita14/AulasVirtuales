# Modo híbrido con IA local (Qwen) + Docker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar el modelo local de la universidad (Qwen3-8B vía vLLM) y una BD vectorial (Qdrant) al sistema "Sílabo → Aula virtual", empaquetado en Docker, como **segundo lector, respaldo y redactor** — sin que la IA pueda publicar en Canvas un dato que no esté verificado.

**Architecture:** La lectura por reglas (`core/silabo.py`) sigue siendo la fuente de los datos estructurados (fechas, horas, columnas, URL). Qwen lee el mismo sílabo en segundo plano (bloques recuperados de Qdrant, salida JSON con esquema) y su resultado se usa para: (a) **concordancia** — mostrar al docente dónde la IA discrepa de las reglas; (b) **respaldo** — completar solo bloques que las reglas no pudieron leer, marcados "leído por IA, revisar"; (c) **redactar** el propósito del momento (PROPUESTO). La lista de control existente sigue siendo filtro obligatorio antes de publicar.

**Tech Stack:** Python 3.12 (Docker) / 3.14 (local), FastAPI, pdfplumber, BeautifulSoup, openai SDK (vLLM), qdrant-client + FastEmbed, Docker Compose, pytest, Playwright (verificación manual de UI).

**Spec:** [`progress.md`](../../../progress.md) — secciones "Decisiones vigentes" (punto 6) y "Pruebas con el modelo local" (resultados de exactitud y estrés que motivan cada tarea).

## Global Constraints

- Servidor IA: `QWEN_URL=http://172.16.8.69:8000/v1`, `QWEN_MODEL=Qwen/Qwen3-8B-AWQ`, ventana **8192 tokens (entrada + salida)**, `response_format=json_schema` sí, **tool calls no**, `enable_thinking=False`, `temperature=0`.
- El servidor es **compartido** y atiende **16 peticiones simultáneas**; el extractor usa como máximo `IA_PARALELO=6` por docente.
- Embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (FastEmbed, local). Qdrant `qdrant/qdrant:v1.20.0`, colección `silabos`.
- La IA **nunca** sobrescribe en silencio un dato leído por reglas; todo lo que viene de la IA se marca y pasa por la lista de control.
- Si Qwen o Qdrant no responden, el sistema funciona igual que hoy (solo reglas) y lo dice en pantalla.
- Reglas de contenido intactas: LITERAL / PROPUESTO / VACÍO, orden de columnas por significado, PIS vacío → se omite el bloque.
- Pruebas automáticas **nunca** usan un Canvas real ni un token real (`sistema/tests/mock_canvas.py`); las que llaman a Qwen llevan la marca `@pytest.mark.qwen` y se saltan si el servidor no responde.
- Puerto del sistema `8770`. Interfaz en español.
- **Sin commits en el repositorio de la carpeta personal** (`C:/Users/Chris` es la raíz git actual). Cada tarea cierra agregando su entrada a la Bitácora de `progress.md`. La Tarea 0 propone crear el repositorio propio del proyecto (requiere aprobación del usuario).

## Review Focus

- **Qwen se cae o tarda a mitad del análisis** → el docente sigue con reglas sin esperar; el panel IA muestra "no disponible"; publicar nunca depende de la IA. *(prueba en Tarea 5)*
- **Qwen inventa en un campo vacío** (p. ej. copia el rótulo "Proyecto interdisciplinario socioformativo" como título del PIS) → el valor se descarta y nunca reemplaza al de las reglas. *(pruebas en Tareas 3 y 4)*
- **Un bloque no cabe en la ventana** (momento con muchas sesiones largas, bibliografía de 20+ obras) → la tarea se parte; nunca un error 400 por exceder 8192. *(pruebas en Tareas 2 y 3)*
- **Varios docentes a la vez (más de 16 peticiones)** → las tareas esperan en cola; un timeout por tarea con un solo reintento; el análisis no queda colgado. *(prueba en Tarea 2)*
- **La IA discrepa de las reglas** → se muestra la discrepancia; lo publicado sale de las reglas salvo en bloques que las reglas dejaron vacíos. *(prueba en Tarea 5)*

---

### Task 0: Repositorio propio del proyecto *(requiere aprobación del usuario)*

**Files:**
- Create: `.gitignore` (excluye `__pycache__/`, `.venv/`, `reportes_ia/`, `.playwright-mcp/`, `.pytest_cache/`, `*.zip`)

- [ ] **Step 1:** Con aprobación del usuario, `git init` en `C:\Users\Chris\Desktop\CIA\AulasVirtuales-Silabos` (queda como repo anidado; la carpeta personal no se toca) y primer commit "estado al 2026-11-09".
- [ ] **Step 2:** Verificar: `git -C . rev-parse --show-toplevel` → `C:/Users/Chris/Desktop/CIA/AulasVirtuales-Silabos`.
- [ ] **Step 3:** Entrada en `progress.md`.

---

### Task 1: Docker Compose (sistema + Qdrant) y estado de servicios

**Files:**
- Create: `sistema/Dockerfile`, `docker-compose.yml` (raíz), `.env.example`
- Modify: `sistema/requirements.txt` (agregar `openai>=1.40`, `qdrant-client>=1.12`, `fastembed>=0.4`)
- Modify: `sistema/app.py` (endpoint `/api/salud`)
- Create: `sistema/ia/salud.py`
- Test: `sistema/tests/test_salud.py`

**Interfaces:**
- Produces: `ia.salud.estado() -> dict` con claves `reglas: "ok"`, `qwen: "ok"|"no_disponible"`, `qdrant: "ok"|"no_disponible"|"memoria"`, `modelo: str`. `GET /api/salud` devuelve ese dict (siempre 200).
- Produces: variables de entorno `QWEN_URL`, `QWEN_MODEL`, `QWEN_TIMEOUT` (default 120), `QDRANT_URL`, `IA_ACTIVA` (`1`/`0`, default `1`), `IA_PARALELO` (default 6), `FASTEMBED_CACHE`.

- [ ] **Step 1: Write the failing test** `test_salud_sin_qwen_responde_200`: con `QWEN_URL=http://127.0.0.1:9/v1` y `QDRANT_URL=""`, `GET /api/salud` → 200, `qwen == "no_disponible"`, `qdrant == "memoria"`, `reglas == "ok"`, en < 6 s.
- [ ] **Step 2:** Run `python -m pytest sistema/tests/test_salud.py -v` → FAIL (404).
- [ ] **Step 3:** Implementar `estado()` (GET `/v1/models` con timeout 3 s; `QdrantClient.get_collections()` con timeout 3 s) y el endpoint.
- [ ] **Step 4:** Run el test → PASS.
- [ ] **Step 5:** `Dockerfile`: `python:3.12-slim`, instala requirements, precarga el modelo de embeddings en la imagen (`FASTEMBED_CACHE=/modelos`), `CMD uvicorn app:app --host 0.0.0.0 --port 8770`. `docker-compose.yml`: servicios `app` (puerto 8770, `env_file: .env`, depende de `qdrant`) y `qdrant` (`qdrant/qdrant:v1.20.0`, volumen `qdrant_data:/qdrant/storage`, sin publicar 6333 hacia fuera).
- [ ] **Step 6: Verify:** `docker compose up -d --build` y en el navegador `http://localhost:8770/api/salud` → `{"reglas":"ok","qwen":"ok","qdrant":"ok",...}`; `python -m pytest sistema/tests tests -q` sigue en verde.
- [ ] **Step 7:** Entrada en `progress.md` (incluye el procedimiento de reparación de Docker si vuelve el error de sockets).

---

### Task 2: Cliente Qwen robusto (ventana, reintentos, disponibilidad)

**Files:**
- Modify: `sistema/ia/qwen.py`
- Test: `sistema/tests/test_qwen_cliente.py`

**Interfaces:**
- Consumes: variables de la Tarea 1.
- Produces: `qwen.contar_tokens(texto: str) -> int` (usa `POST {base}/tokenize` de vLLM; si falla, `ceil(len/2.5)`); `qwen.disponible() -> bool` (cacheado 30 s); `qwen.json_con_esquema(sistema, usuario, esquema, nombre, max_tokens=None, pensar=False, temperatura=0.0) -> (dict, dict)` (firma actual, sin cambios); excepción nueva `qwen.QwenNoDisponible(Exception)`.

- [ ] **Step 1: Write failing tests** con un cliente falso (monkeypatch de `qwen.cliente`):
  - `test_reduce_max_tokens_si_excede_ventana`: la primera llamada lanza `BadRequestError` con "maximum context length is 8192" → se reintenta una vez con `max_tokens` menor y devuelve el JSON.
  - `test_presupuesto_con_texto_en_ingles_y_urls`: para la bibliografía de B26 (texto del fragmento `bibliografia`) `entrada + max_tokens <= 8192` usando `contar_tokens`.
  - `test_timeout_lanza_qwen_no_disponible`: el cliente falso lanza `APITimeoutError` dos veces → `QwenNoDisponible`.
  - `test_disponible_falso_si_no_responde`: `QWEN_URL` a puerto cerrado → `disponible() is False` en < 4 s.
- [ ] **Step 2:** Run `python -m pytest sistema/tests/test_qwen_cliente.py -v` → FAIL.
- [ ] **Step 3:** Implementar; `timeout=QWEN_TIMEOUT`, un solo reintento.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Entrada en `progress.md`.

---

### Task 3: Extracción más exacta (corrige los errores medidos)

**Files:**
- Modify: `sistema/ia/documento.py`, `sistema/ia/extractor.py`
- Test: `sistema/tests/test_extractor_unit.py` (sin red), `sistema/tests/test_qwen_integracion.py` (`@pytest.mark.qwen`)
- Modify: `sistema/pytest.ini` o `conftest.py` (registrar la marca `qwen`; saltar si `qwen.disponible()` es falso)

**Interfaces:**
- Consumes: `qwen.json_con_esquema`, `qwen.contar_tokens` (Tarea 2); `core.silabo._columnas`, `core.silabo._valores` (lector actual).
- Produces: `documento.registros_sesiones(pdf_path) -> dict[int, list[str]]` — por momento, una cadena por sesión con las celdas **etiquetadas por encabezado** (`"SESIÓN: …\nACTIVIDADES CON EL DOCENTE: …\nHORAS DOCENTE: …\nPRÁCTICO-EXPERIMENTALES: …\nHORAS PRÁCTICO: …\nAUTÓNOMO: …\nHORAS AUTÓNOMO: …\nCONTENIDOS: …"`), con las filas de continuación entre páginas ya unidas.
- Produces: `extractor.limpiar_rotulos(valor: str, rotulos: list[str]) -> str` (devuelve `""` si el valor es igual, sin mayúsculas/espacios, a un rótulo de la tabla).
- Produces: constante `extractor.ROTULOS_PIS = ["Proyecto interdisciplinario socioformativo", "Aporte del proyecto formativo al proyecto interdisciplinario socioformativo"]` y `extractor.ROTULOS_SESIONES` (encabezados de la tabla de sesiones: "Sesión - fecha", "Actividades con el docente", "Horas", "Actividades práctico- experimentales", "Actividades de trabajo autónomo", "Contenidos").
- Produces: `extractor.extraer(alm, silabo_id, ficha=None, paralelo=6, pdf_path=None) -> (dict, dict)` (agrega `pdf_path` para leer `registros_sesiones`; una tarea por **sesión** con `ESQ_SESION`; la bibliografía se parte en tareas de ≤ 8 obras si no cabe).

- [ ] **Step 1: Write failing unit tests:**
  - `test_registros_sesiones_med_m1`: para el sílabo de Medicina, `registros_sesiones(...)[1][2]` contiene `"HORAS DOCENTE: 2.0"` y termina el docente con `"digitales en medicina."`.
  - `test_registros_columnas_extra_m2`: Medicina M2 S1 contiene `"HORAS DOCENTE: 2.0"` y `"HORAS PRÁCTICO: 2.0"`.
  - `test_limpiar_rotulos`: `limpiar_rotulos("Proyecto interdisciplinario socioformativo", ROTULOS_PIS) == ""` y `limpiar_rotulos("Desarrollo de soluciones…", ROTULOS_PIS)` lo deja igual.
- [ ] **Step 2:** Run `python -m pytest sistema/tests/test_extractor_unit.py -v` → FAIL.
- [ ] **Step 3:** Implementar `registros_sesiones` reutilizando `_columnas`/`_valores`; `limpiar_rotulos`; tareas por sesión y bibliografía partida; aplicar `limpiar_rotulos` a PIS y a toda celda de texto.
- [ ] **Step 4:** Run unit tests → PASS.
- [ ] **Step 5: Write the integration test** `test_exactitud_minima[pdf]` (`@pytest.mark.qwen`, parametrizado con los PDF de `silabos_prueba/` + B26): con `ia.comparar.comparar(ref, ia)`: categoría `Horas` = 100 %, `PIS` = 100 %, `Bibliografía` = 100 %, total ≥ 97 %, y `metricas['errores'] == []`.
- [ ] **Step 6:** Run `python -m pytest sistema/tests/test_qwen_integracion.py -m qwen -v` (≈ 3 min) → PASS. Si alguna categoría no llega, registrar la cifra en `progress.md` y **no** bajar el umbral sin aprobación del usuario.
- [ ] **Step 7:** Regenerar `reportes_ia/` con `python -m ia.evaluar … --repeticiones 2` y anotar la tabla nueva en `progress.md`.

---

### Task 4: Concordancia reglas ↔ IA (segundo lector)

**Files:**
- Create: `sistema/ia/concordancia.py`
- Test: `sistema/tests/test_concordancia.py`

**Interfaces:**
- Consumes: `ia.comparar.campos(sil)` (existente).
- Produces: `concordancia.discrepancias(ref: dict, ia: dict) -> list[dict]` con claves `campo`, `categoria`, `reglas`, `ia`, `gravedad` (`"alta"` para Horas, Cabecera.fechas, RA, Sesiones.cantidad, Rúbrica.indicadores; `"media"` para textos), ordenada por gravedad. Ignora diferencias triviales: espacios, punto final, viñeta "•", mayúsculas en códigos RA, y valores IA vacíos por `limpiar_rotulos`.
- Produces: `concordancia.resumen(lista) -> dict(total, altas, medias, por_categoria)`.

- [ ] **Step 1: Write failing tests** con diccionarios pequeños armados en la prueba:
  - `test_sin_diferencias_triviales`: RA con y sin punto final → `[]`.
  - `test_horas_es_alta`: `hd` "6.0" vs "4.0" → una discrepancia `gravedad == "alta"`, `campo == "M2.S1.horas"`.
  - `test_ia_vacia_no_es_discrepancia_de_texto`: texto IA `""` (descartado) frente a texto de reglas → no se reporta como texto distinto sino como `"ia_sin_dato"` con gravedad `"media"`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5:** Entrada en `progress.md`.

---

### Task 5: Segunda lectura en segundo plano + respaldo por bloque

**Files:**
- Create: `sistema/ia/trabajo.py`
- Modify: `sistema/core/servicio.py` (lanzar el trabajo; `resumen()` expone `ia`), `sistema/app.py` (`GET /api/ia/{sid}`, parámetro `usar_ia` en `/api/analizar`)
- Test: `sistema/tests/test_trabajo_ia.py`

**Interfaces:**
- Consumes: `extractor.extraer` (Tarea 3), `concordancia.discrepancias/resumen` (Tarea 4), `vectores.Almacen`, `qwen.disponible` (Tarea 2).
- Produces: `trabajo.iniciar(sesion: dict, pdf_bytes: bytes) -> None` (hilo en segundo plano; no bloquea `analizar`). Estado en `sesion['ia']`: `{"estado": "pendiente"|"en_curso"|"listo"|"error"|"no_disponible", "avance": float 0–1, "segundos": float, "discrepancias": list, "resumen": dict, "bloques_ia": list[str], "error": str|None}`.
- Produces: `trabajo.fusionar(ref: dict, ia: dict) -> (dict, list[str])` — copia de `ref` donde solo se completan con IA los bloques **vacíos** en reglas (momento sin sesiones, momento sin rúbrica, RA sin texto); devuelve los nombres de bloques completados (p. ej. `"M3.rubrica"`), que se agregan como advertencia grave "Leído por IA, revisar".
- Produces: `GET /api/ia/{sid}` → `sesion['ia']` sin datos internos.

- [ ] **Step 1: Write failing tests** (monkeypatch de `extractor.extraer` y `qwen.disponible`, Canvas simulado):
  - `test_analizar_no_espera_a_la_ia`: con un extractor falso que duerme 5 s, `/api/analizar` responde en < 2 s y `/api/ia/{sid}` dice `"en_curso"`; luego `"listo"` con discrepancias.
  - `test_qwen_caido_sistema_funciona`: `disponible() -> False` → `/api/ia/{sid}` `"no_disponible"`; `/api/generar` y `/api/publicar` funcionan igual que hoy.
  - `test_fusion_solo_bloques_vacios`: `ref` con M3 sin rúbrica y M1 completo; `ia` con ambos → resultado con rúbrica M3 de la IA, M1 intacto de reglas; `bloques_ia == ["M3.rubrica"]`; la lista de control del M3 pasa contra los datos fusionados.
  - `test_discrepancia_no_cambia_lo_publicado`: IA con horas distintas en M2 → el HTML publicado en el Canvas simulado tiene las horas de reglas.
- [ ] **Step 2:** Run `python -m pytest sistema/tests/test_trabajo_ia.py -v` → FAIL.
- [ ] **Step 3:** Implementar (`threading.Thread(daemon=True)`; `Almacen()` compartido por proceso; avance = tareas terminadas / tareas totales).
- [ ] **Step 4:** Run → PASS; `python -m pytest sistema/tests tests -q` en verde.
- [ ] **Step 5:** Entrada en `progress.md`.

---

### Task 6: Propósito redactado por Qwen (PROPUESTO) con respaldo por regla

**Files:**
- Modify: `sistema/core/propuestas.py`
- Test: `sistema/tests/test_propuestas_ia.py`

**Interfaces:**
- Consumes: `qwen.json_con_esquema`, `qwen.disponible`.
- Produces: `propuestas.proposito_ia(momento: dict) -> str | None` — esquema `{"proposito": string}`; acepta solo si es 1 oración, primera palabra termina en `ar|er|ir`, ≤ 45 palabras y no copia la evidencia literal; si no, `None`.
- Produces: `propuestas.proponer(sil, usar_ia: bool = False) -> dict` (firma ampliada): con `usar_ia` y `disponible()`, usa `proposito_ia` y cae a la regla actual por momento si devuelve `None`.

- [ ] **Step 1: Write failing tests** con Qwen falso: respuesta válida → se usa; respuesta de dos oraciones → `None` y se usa la regla; Qwen no disponible → regla, sin esperar.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar. **Step 4:** Run → PASS.
- [ ] **Step 5:** Entrada en `progress.md`.

---

### Task 7: Interfaz — casilla IA, panel de segunda lectura y estado

**Files:**
- Modify: `sistema/static/index.html`
- Test: `sistema/tests/test_sistema.py::test_pagina_principal` (amplía) + verificación con Playwright

**Interfaces:**
- Consumes: `GET /api/salud` (Tarea 1), `GET /api/ia/{sid}` (Tarea 5), `usar_ia` en `/api/analizar`.

- [ ] **Step 1: Ampliar el test** `test_pagina_principal`: el HTML contiene `"Revisar también con la IA de la universidad"` y `"Segunda lectura (IA)"`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implementar:
  - Paso 1: casilla "Revisar también con la IA de la universidad (Qwen)", marcada si `/api/salud` dice `qwen: ok`; deshabilitada con nota si no.
  - Paso 2: tarjeta "Segunda lectura (IA)" que consulta `/api/ia/{sid}` cada 3 s: barra de avance; al terminar, tabla de discrepancias (alta en rojo, media en naranja) y, si hubo `bloques_ia`, aviso grave "Leído por IA, revisar".
  - Botones del paso 4 ya propuestos: "Volver al inicio" (avisa si no se descargó el ZIP) y "Cargar otro curso" tras terminar.
- [ ] **Step 4:** Run → PASS. **Step 5: Verify con Playwright** contra el Canvas simulado y Qwen real: subir Medicina, ver el panel completar en ~90 s con 0 discrepancias altas (tras la Tarea 3); con `QWEN_URL` inválida, ver "no disponible" y publicar igual.
- [ ] **Step 6:** Entrada en `progress.md` con capturas.

---

### Task 8: Regresión y estrés dentro del proyecto + documentación

**Files:**
- Create: `sistema/ia/estres.py` (desde el script de la sesión de pruebas: niveles de concurrencia, p50/p95, tok/s, muestreo de `/metrics`), `sistema/ia/visor.py` (genera `reportes_ia/visor.html`)
- Modify: `sistema/README.md`, `progress.md`

**Interfaces:**
- Produces: `python -m ia.estres --niveles 1 2 4 8 16` → imprime una fila JSON por nivel y escribe `reportes_ia/estres_<fecha>.json`; `python -m ia.visor` → `reportes_ia/visor.html`.

- [ ] **Step 1:** Mover los scripts; correr `python -m ia.estres --niveles 1 4 16` → 0 errores, todos los JSON válidos.
- [ ] **Step 2:** Correr la batería completa: `python -m pytest sistema/tests tests -q` (sin red) y `python -m pytest sistema/tests -m qwen -v` (con Qwen).
- [ ] **Step 3:** README: sección "Modo IA" (qué hace y qué no, variables, cómo levantar con Docker, cómo evaluar). `progress.md`: estado final y cifras.

---

## Fuera de este plan (pendientes registrados en `progress.md`)
- OAuth / Developer Key de Canvas (requiere administrador de Canvas).
- Despliegue en el servidor de la UTI con HTTPS.
- Conectar el sistema como Acción de un GPT o conector MCP.
