# progress.md · Sílabo → Aula virtual (Canvas)

> **Leer primero.** Registro de todo lo hecho, decisiones, resultados de pruebas y pendientes.
> Cada tarea nueva agrega una entrada en **Bitácora** (fecha, qué se hizo, cómo se verificó).
> Plan vigente: [`docs/superpowers/plans/2026-11-09-modo-hibrido-qwen.md`](docs/superpowers/plans/2026-11-09-modo-hibrido-qwen.md)

## Estado actual (2026-11-09, tras el plan de modo híbrido)

| Pieza | Estado | Dónde |
|---|---|---|
| Prompt maestro (cualquier IA) + script de carga | ✔ Funciona; ANEXO A con plantilla; variantes de sílabo documentadas | `PROMPT_MAESTRO_Silabo_a_Canvas.md`, `publicar_canvas.ps1` |
| Sistema web (reglas, sin IA) con carga a Canvas por token | ✔ **En uso real**: publicó el curso B26-MED-1 Computación y Sociedad P02 (ID 36732), revisado y aprobado por el usuario | `sistema/` |
| Pruebas automáticas | ✔ 208 locales + 5 contra Qwen real (2 de extracción y 3 de contexto); nunca tocan Canvas real | `tests/`, `sistema/tests/` |
| **Modo IA híbrido** (Qwen + Qdrant) | ✔ Integrado: segunda lectura, respaldo por bloque, propósitos de Qwen; 99.3–99.6 % de exactitud | `sistema/ia/` |
| Docker | ✔ `docker compose up -d --build` (sistema + Qdrant), solo en 127.0.0.1 | `docker-compose.yml` |

## Cómo se usa hoy
- Sistema: `sistema\iniciar.ps1` → http://localhost:8770 (docente: sílabo PDF + URL del curso + token de Canvas).
- Pruebas: `python -m pytest sistema/tests tests -v`
- Evaluación con Qwen: `cd sistema && python -m ia.evaluar ..\silabos_prueba\*.pdf --repeticiones 2 --salida ..\reportes_ia`
- Canvas simulado (sin token real): `python sistema/tests/mock_canvas.py 8771` y `CANVAS_API_OVERRIDE=http://127.0.0.1:8771`.

## Decisiones vigentes
1. **Literal**: todo lo que trae el sílabo se copia sin cambios; lo que no trae se marca **PROPUESTO** (propósito, reparto de bibliografía complementaria, enlaces agregados por el docente).
2. **Plantilla**: la página "Momento N" actual del curso es la plantilla; si no tiene la estructura, se usa `sistema/plantillas/momento_institucional.html`. Ya no se pide el HTML al docente.
3. **Canvas**: el docente entrega URL del curso + token. Lectura solo GET; escritura solo tras casilla de confirmación; respaldo previo, verificación posterior y "Restaurar". Token solo en memoria. En red: **HTTPS obligatorio**.
4. **La lista de control informa, pero no impide publicar** (cambio solicitado expresamente por el usuario el 2026-11-09). El docente revisa los avisos y confirma la publicación. Se conservan los controles de confirmación, vista previa completa/actualizada y página destino.
5. **Prompt maestro**: la IA del chat nunca recibe el token; la carga la hace `publicar_canvas.ps1` en el PC del docente.
6. **Qwen (modelo local)**: según las pruebas del 2026-11-06/09, **no** reemplaza a la lectura por reglas. Se usará en **modo híbrido** (ver plan): reglas para datos estructurados, Qwen como segundo lector, respaldo y redactor de textos PROPUESTOS; la lista de control sigue siendo filtro obligatorio.

## Bitácora

### 2026-11-06 · Del prompt al sistema
- **Prompt maestro** reescrito desde un prompt de "sistema web": entrada sílabo + plantilla HTML → salida HTML por momento; reglas de mapeo LITERAL/PROPUESTO/VACÍO, orden de columnas invertido (Autónomo ↔ Práctico-exp.), formato APA.
- **HTML de Programación Estructurada (B26)** generados para los 4 momentos (`html/`) desde el Momento 1 aprobado (curso 36283).
- **Batería de 99 pruebas** (`tests/`) con lector independiente del PDF; 12/12 errores provocados detectados (pruebas de mutación).
- **Mapa y mockup** (`diseno/`) del sistema de 4 pasos, validados por el usuario.
- **Sistema v1** (FastAPI): lector por reglas, validador, propuestas, renderizador sobre el DOM de la plantilla, lista de control, ZIP. Corrección: la advertencia "orden de columnas de la Presentación" era falsa (texto plano); se lee por tablas.
- **Sistema v2 con token de Canvas**: localiza páginas Momento (página de inicio → módulos → búsqueda), publica con respaldo/verificación/restaurar. Prompt maestro sin pedir HTML (plantilla en ANEXO A) + `publicar_canvas.ps1` (bug encontrado por prueba: `Get-Content -Raw` serializaba un objeto al restaurar → `ReadAllText`).
- **Sílabo de Medicina (Computación y Sociedad)**: variantes corregidas en el lector — sesiones de una sola fecha, columnas vacías extra (mapeo por encabezado), sesiones de examen con 0.0 h, PIS vacío (se omite el bloque, no se inventa), libros sin URL y apellidos compuestos, títulos en mayúsculas, RA desde la tabla de la sección III.
- **Avisos del sílabo en la lista de control** (no bloquean) y campo "Obras sin enlace" en el paso 2 (PROPUESTO). Los 2 libros sin URL de Medicina **no existen tal como se citan** (otra editorial/año/subtítulo); e-Libro de la UTI está inactivo → no se colocaron enlaces.
- **Publicación real** del curso de Medicina (ID 36732) por el usuario: 4/4 "Publicada y verificada"; revisado y aprobado.

### 2026-11-06 → 09 · Pruebas con el modelo local (Qwen3-8B-AWQ, vLLM 172.16.8.69:8000)
- **Servidor**: ventana **8192 tokens totales**; JSON con esquema ✔; ~30 tokens/s por petición; `/metrics` disponible; es **compartido** (había otras peticiones en curso).
- **Docker**: fallaba al iniciar por sockets huérfanos bloqueados (`Docker\run\*.sock`, `docker-secrets-engine\engine.sock`) que Windows no puede abrir. Solución aplicada: cerrar Docker, `wsl --shutdown`, **borrar los sockets desde WSL** (`wsl -d Ubuntu -u root rm …`), reiniciar. Si vuelve a pasar, repetir lo mismo.
- **BD vectorial**: Qdrant 1.20 en contenedor; embeddings locales `paraphrase-multilingual-MiniLM-L12-v2` (FastEmbed). Indexa un sílabo (20 bloques) en 3 s; reindexar no duplica; búsqueda semántica acierta el bloque 3/4 → la extracción filtra por momento y tipo de bloque.
- **Exactitud de Qwen** (Qwen extrae JSON; renderizador y plantilla iguales; comparación campo a campo contra reglas). 2 corridas por sílabo, **idénticas entre sí**:

| | Medicina | Programación Estructurada |
|---|---|---|
| Campos idénticos | 92.8 % (271/292) | 80.8 % (185/229) |
| Páginas idénticas | 0/4 | 0/4 |
| Lista de control | 16–17/20 (bloquea) | 15–16/20 (bloquea) |
| Tiempo por sílabo | 79–84 s | 66–73 s |

  - Aciertos 100 %: cabecera de momentos, número/fechas de sesiones, **rúbricas completas**, RA y bibliografía de Medicina.
  - Errores sistemáticos: (1) **horas docentes** (columnas vacías extra; confunde con "Otras actividades"); (2) **PIS vacío → copia el rótulo** (inventa); (3) texto del docente mezclado/incompleto; (4) no une texto cortado entre páginas; (5) bibliografía de Programación **no generada** por mi estimación de tokens (`tokens_aprox` subestima inglés+URL → 400 por exceder 8192); (6) punto final de un RA.
  - La **lista de control detectó todos los errores** de Qwen.
- **Estrés** (tarea real: rúbrica, ~1300 tokens entrada / ~1080 salida):

| Concurrencia | OK | p50 | Rendimiento total |
|---|---|---|---|
| 1 | 2/2 | 38.8 s | 28 tok/s |
| 4 | 4/4 | 36.1 s | 119 tok/s |
| 8 | 8/8 | 36.3 s | 237 tok/s |
| 16 | 16/16 | 37.2 s | **450 tok/s** |

  - 0 errores, 0 preempciones, KV-cache máx. 12.9 %. Techo de **16 peticiones simultáneas** (configuración del servidor; hubo hasta 3 en cola por otros usuarios). Capacidad estimada: 2–3 docentes a la vez a velocidad completa; ~40–60 sílabos/hora prudente.
- Visor comparativo: `reportes_ia/visor.html`. Scripts de estrés/monitor quedaron fuera del proyecto (carpeta temporal); el plan los incorpora.

## Pendientes conocidos
- Prueba del usuario en **otros sílabos/carreras** (colocar PDF en `silabos_prueba/`: se prueban solos).
- **Developer Key de Canvas (OAuth)** para no pedir token manual (requiere admin de Canvas de TI).
- **Despliegue** en servidor de la UTI con HTTPS.
- Citas erróneas de los 2 libros de Medicina: corregir en el sistema académico.

### 2026-11-09 · Plan modo híbrido — Tarea 0 y Tarea 1
- **Tarea 0**: repositorio git propio del proyecto (`git init`, rama `main`); la carpeta personal no se toca.
- **Tarea 1**: `docker compose up -d --build` levanta el sistema (puerto 8770) y Qdrant (`qdrant/qdrant:v1.20.0`, volumen persistente, sin exponer 6333). Imagen `python:3.12-slim` con el modelo de embeddings precargado. Nuevo `GET /api/salud` → `{"reglas":"ok","qwen":"ok","qdrant":"ok",...}` verificado contra los contenedores; si Qwen no responde informa `no_disponible` en < 6 s. Config en `.env` (plantilla `.env.example`).
- **Seguridad (revisión automática)**: 3 hallazgos reales corregidos con pruebas que primero fallaron: (1) URL tipo `https://evil.com?.instructure.com/courses/1` pasaba el filtro y el **token viajaba a evil.com** → host validado con regex estricta (sin usuario, contraseña, puerto, `?`, `#`); (2) lo mismo en `publicar_canvas.ps1`; (3) vista previa en `iframe sandbox` (sin scripts). 18 pruebas nuevas en `sistema/tests/test_seguridad.py`.
- Suite: 155 pruebas en verde.
- Si Docker vuelve a fallar con "…sock: The file cannot be accessed by the system": cerrar Docker, `wsl --shutdown`, `wsl -d Ubuntu -u root -- rm -f /mnt/c/Users/Chris/AppData/Local/Docker/run/*.sock /mnt/c/Users/Chris/AppData/Local/docker-secrets-engine/engine.sock`, iniciar Docker.

### 2026-11-09 · Tarea 2 — cliente Qwen robusto
- `ia/qwen.py`: cuenta la entrada con el **tokenizador del servidor** (`POST /tokenize`); sin servidor, estimación conservadora 1 token / 2.5 caracteres (antes 3.2, que subestimaba inglés + URL y causó el error 400 de la bibliografía). Pide como salida solo lo que sobra de los 8192.
- Un reintento: si el servidor responde "maximum context length", reduce `max_tokens` con la cifra que devuelve; si no responde a tiempo (`QWEN_TIMEOUT`, 120 s), lanza `QwenNoDisponible`. `disponible()` en < 4 s (caché 30 s). La configuración se lee del entorno en cada llamada.
- Seguridad: `docker-compose.yml` publica el sistema **solo en 127.0.0.1:8770**; para usarlo en red, proxy con HTTPS delante (el token viaja en el formulario).
- Pruebas: 5 nuevas en `test_qwen_cliente.py` + 1 en `test_seguridad.py`; suite 161 en verde.

### 2026-11-09 · Tarea 3 — extracción más exacta con Qwen
- Las sesiones van **una por tarea** con las celdas **etiquetadas por encabezado** (`documento.registros_sesiones`): filas cortadas entre páginas ya unidas y "Otras actividades con el docente (X h)" ya separado. La fila Total, recursos y política de IA también llegan etiquetados (`documento.pie_momentos`).
- `extractor.limpiar_rotulos` descarta valores que son solo un rótulo (el PIS inventado); la bibliografía se pide por sección (y se parte si no cabe) con un ejemplo de referencia completa.
- Marca `qwen` en `pytest.ini` (excluida por defecto). `test_qwen_integracion.py`: Horas, PIS y Bibliografía 100 % y total ≥ 97 % → **2/2 sílabos pasan**.
- Evaluación final (2 corridas idénticas por sílabo):

| | Antes (06/11) | Ahora |
|---|---|---|
| Programación Estructurada | 80.8 % · 0/4 páginas idénticas | **99.6 % · 4/4 páginas idénticas** (única diferencia: punto final de RA2, que la página agrega igual) |
| Medicina | 92.8 % · 0/4 | **99.3 % · 2/4** (2 diferencias de un carácter; la lista de control las detecta) |
| Tiempo por sílabo | 66–84 s | 67–87 s |

- Suite sin red: verde.

### 2026-11-09 · Tarea 4 — concordancia reglas ↔ IA
- `ia/concordancia.py`: `discrepancias(ref, ia)` lista lo que la IA leyó distinto (gravedad **alta**: horas, sesiones, fechas, códigos RA, cantidades; **media**: textos) e `ia_sin_dato` cuando la IA no trajo un valor que las reglas sí. Ignora diferencias que no cambian la página (espacios, punto final, viñeta, mayúsculas en códigos RA). `resumen()` cuenta por gravedad y categoría. 4 pruebas.

### 2026-11-09 · Tarea 5 — segunda lectura en segundo plano
- `ia/trabajo.py`: al analizar con `usar_ia=1`, Qwen lee el sílabo en un hilo (indexa en Qdrant, extrae, calcula discrepancias). `/api/analizar` responde sin esperar; `GET /api/ia/{sid}` da `estado` (pendiente/en_curso/listo/error/no_disponible/desactivada), `avance`, `discrepancias`, `resumen` y `bloques_ia`.
- **Lo publicado sale de las reglas.** La IA solo completa bloques que las reglas dejaron vacíos (momento sin sesiones/rúbrica, RA sin texto) y agrega la advertencia grave "Leído por IA, revisar".
- Si Qwen no responde, el estado es `no_disponible` y generar/publicar funcionan igual. La API trae `usar_ia` apagado por defecto (la interfaz lo activa).
- 5 pruebas nuevas; suite 177 en verde.

### 2026-11-09 · Tarea 6 — propósito redactado por Qwen
- `core/propuestas.py`: `proposito_ia(momento)` pide a Qwen una oración (20–40 palabras, verbo en infinitivo, sin copiar la evidencia) y la valida; `proponer(sil, usar_ia=False)` la usa por momento cuando es válida y cae a la regla si no sirve, si Qwen no está o si falla. 6 pruebas.
- Seguridad (revisión automática): el error de la IA que llega al navegador ya no incluye el texto interno de la excepción (rutas, direcciones); el detalle va solo al registro del servidor. Prueba nueva.

### 2026-11-09 · Tarea 7 — interfaz de la IA
- **Paso 1**: casilla "Revisar también con la IA de la universidad (Qwen)", marcada si `/api/salud` dice que Qwen responde; si no, deshabilitada con aviso ("se usará solo la lectura por reglas").
- **Paso 2**: tarjeta "Segunda lectura (IA)" con barra de avance (consulta cada 3 s, no bloquea); al terminar muestra las diferencias (importantes en rojo, de texto en naranja), los bloques "Leído por IA, revisar" y los **propósitos redactados por Qwen** con botón "Usar esta redacción".
- **Paso 4**: botones "← Volver al inicio" (avisa si no se descargó el ZIP) y "Cargar otro curso" tras terminar.
- Verificado en navegador (Playwright, Canvas simulado + Qwen real) con el sílabo de Medicina: análisis listo en ~8 s; segunda lectura en ~95 s con **0 diferencias**; el docente pudo generar la vista previa mientras la IA leía; "Usar esta redacción" aplicó el propósito.

### 2026-11-09 · Tarea 8 — evaluación dentro del proyecto y documentación
- `python -m ia.estres` (estrés con monitor de `/metrics`), `python -m ia.visor` (comparación visual) y `python -m ia.evaluar` quedaron dentro del proyecto. Estrés 1/4/16: 0 errores, todos los JSON válidos, 426.6 tok/s con 16, KV-cache máx. 12.6 %, 0 preempciones.
- README con secciones "Arrancar" (Docker) y "Modo IA" (qué hace y qué no, variables, herramientas).
- Suite final: **185 sin red** + **2/2 contra Qwen real**.

### 2026-11-09 · Revisión final independiente y correcciones
- Revisor independiente (modelo más capaz) sobre todo el plan: **0 críticos, 5 importantes, 10 menores**; veredicto "listo con correcciones". Los 5 importantes se corrigieron con pruebas que primero fallaron (`sistema/tests/test_revision_final.py`):
  1. Si Qwen se cae **a mitad** de la lectura, ahora se detiene al primer fallo y el panel dice "no disponible" (antes decía "terminada" con cientos de diferencias falsas y podía tardar ~25 min). Si la mayoría de tareas falla, el estado es "error".
  2. Un bloque **no se completa con la IA si alguna de sus tareas falló**, y tras completar se **recalculan las advertencias** (vuelve a controlar horas y fechas; quita las viejas).
  3. Si la IA completa datos **después** de que el docente generó la vista previa, **publicar exige generarla de nuevo**.
  4. **Semáforo global** (`QWEN_MAX_SIMULTANEAS=12`): con varios docentes a la vez la cola es local y el timeout cuenta solo el tiempo de servicio (antes la cola de vLLM podía agotar el timeout y marcar la IA "no disponible" para todos).
  5. **El sílabo ya no queda en Qdrant**: cada lectura usa un identificador propio y se borra al terminar (el sílabo trae datos del docente).
- 10 menores quedan registrados como pendientes (ver abajo). Suite: **192 sin red + 2/2 contra Qwen real**.

## Pendientes menores de la revisión (diferidos)
- `limpiar_rotulos` también en rúbrica/cabecera/RA · cancelar el hilo de la IA al terminar o volver al inicio · `disponible()` síncrono dentro del endpoint · reconocer otros formatos de mensaje de vLLM al exceder la ventana · partir la tarea de rúbrica si no cabe · quitar `proponer(usar_ia=True)` o documentarlo · no consultar Qwen al importar la prueba de integración · permitir `*.beta/*.test.instructure.com` (o documentar `CANVAS_HOSTS`) · recorrer el PDF una sola vez en `documento`.

### 2026-11-09 · Verificación nueva antes del piloto compartido
- Docker: app y Qdrant activos; `/` devuelve 200 y `/api/salud` informa reglas/Qwen/Qdrant `ok`, con IA activa. Los hashes de `app.py`, `static/index.html`, `ia/trabajo.py` e `ia/qwen.py` coinciden entre el proyecto y el contenedor.
- Suite ejecutada de nuevo: `python -m pytest sistema/tests tests -q --tb=short` → **192 passed, 2 deselected**, 165.38 s. Se ejecutó fuera del sandbox porque este impide usar sockets locales; la primera ejecución restringida se detuvo.
- Evaluación nueva, una corrida por PDF contra Qwen real: Programación **228/229 (99.6 %)**, 4/4 páginas idénticas, 70.1 s; Medicina **290/292 (99.3 %)**, 2/4 páginas idénticas, 86.5 s. Sin errores de extracción ni campos sobrantes; horas, PIS y bibliografía 100 % en ambos. Reporte: `reportes_ia/verificacion_actual/evaluacion_20261109_104442.json` (carpeta ignorada por git).
- El control de literalidad detecta las diferencias de Medicina al renderizar la lectura de IA. En producción se mantiene la lectura por reglas para los bloques que ya tienen datos.
- El mínimo del test de integración es 97 % global + 100 % en horas, PIS y bibliografía: mide coincidencia con reglas, no confianza estadística ni exactitud general en carreras aún no evaluadas. Los resultados permiten un piloto supervisado; faltan otros sílabos y la prueba del compañero en su curso sandbox. No se publicó en Canvas real durante esta verificación.
- Navegador: casilla de Qwen marcada automáticamente con disponibilidad confirmada. La disponibilidad se consulta una vez al cargar; si la consulta inicial falla, hace falta recargar para volver a comprobar. La revisión comienza al pulsar Analizar con la casilla marcada; los propósitos sugeridos requieren el clic del docente.
- Prueba HTTP sobre el contenedor: URL `https://evil.com?.instructure.com/courses/1` rechazada con 422 usando token ficticio; publicación sin sesión rechazada con 404.
- Túnel HTTPS temporal **abierto tras la confirmación explícita del usuario**, después de informar que cualquier persona con el enlace puede acceder. Contenedor `silabos-tunel`, imagen oficial `cloudflare/cloudflared:latest` (2026.10.7), conectado a la red Docker del sistema; no se expusieron puertos adicionales. URL: https://shed-bracelet-viewpicture-zinc.trycloudflare.com . Verificado desde HTTPS: interfaz 200 y `/api/salud` 200 con reglas/Qwen/Qdrant `ok`. Para cerrarlo: `docker stop silabos-tunel`. Requiere mantener el equipo y Docker funcionando; al recrearlo cambia la URL. La revisión automática rechazó el primer intento por faltar autorización explícita de exposición pública; tras solicitarla y recibirla se aprobó el segundo intento.

### 2026-11-09 · Publicación con avisos por solicitud del usuario
- El usuario pidió expresamente permitir subir los cambios aunque la lista de control tenga fallos (captura: bibliografía complementaria). La lista sigue mostrando todos los resultados, pero deja de bloquear continuar, publicar y descargar el ZIP. La confirmación del docente incorpora la revisión de los avisos pendientes.
- Se mantienen confirmación obligatoria, vista previa completa y actualizada, comprobación de destino, respaldo, verificación posterior y restauración. No se publican páginas que no pudieron generarse.
- Regresión observada antes de corregir: el nuevo caso de publicación con control fallido fallaba porque `listo` era falso. Tras el cambio: **42 pruebas aprobadas** en `test_sistema.py`, `test_revision_final.py` y `test_variantes.py`, 89.70 s; incluyen publicación con avisos, rechazo sin confirmación, fallo de generación y regeneración tras cambios de IA.
- Imagen reconstruida y app recreada; las sesiones anteriores se cerraron. El túnel conserva su URL. Verificado por HTTPS: interfaz actualizada 200 y reglas/Qwen/Qdrant `ok`. No se escribió en Canvas real.

### 2026-11-09 · Corrección de IndexError con Bioética y comprobación tras reinicio
- Registro de Docker: `core/silabo.py::_momentos` intentaba leer `r[2]` en una fila `Fecha` con dos celdas. El PDF real `SÍLABO BIOÉTICA - ODONTOLOGÍA.pdf`, localizado en Descargas, usa dos columnas en la cabecera del Momento 1 y nueve en las demás.
- Las cabeceras de título, fechas, RA y evidencia ahora toman las celdas de valor no vacías después del rótulo, sin asumir una tercera columna. Tres variantes reproducibles (2/3/4 celdas): dos fallaban antes de corregir; las tres pasan después.
- Validación: **45 pruebas aprobadas** (`test_variantes.py`, `test_extractor_unit.py`, `test_sistema.py`), 84.02 s. PDF real leído y vista previa de cuatro momentos generada con Canvas simulado; queda un aviso de literalidad en contenidos de sesión 4 del Momento 4, que no bloquea publicar según la decisión vigente. No se publicó en Canvas real.
- Imagen reconstruida y app recreada; lectura del PDF real verificada también dentro de Docker: 4/5/4/4 sesiones y fechas de inicio correctas. Copia temporal del PDF eliminada después de verificar; no se añadió el documento al repositorio.
- Tras el reinicio realizado por el usuario, app/Qdrant/túnel activos y `/api/salud` con reglas/Qwen/Qdrant `ok`. El túnel reiniciado cambió de URL: **https://calculators-concluded-region-finite.trycloudflare.com**. La actualización posterior recreó solo la app, sin reiniciar el túnel. Las sesiones anteriores deben volver a cargarse.

### 2026-11-09 · Bibliografía de Antropología, estructura HTML y aislamiento del contexto
- Causa reproducida desde el texto pegado por el usuario: `_biblio` tomaba la primera mención a «Bibliografía básica» en Recursos y arrastraba sesiones/rúbricas hasta la sección VI. Ahora delimita la sección bibliográfica real, distingue el índice y exige encabezados completos de básica/complementaria. Reconoce referencias con nombres completos y `(Ed.)` como obras separadas. No se dispuso del PDF original de Antropología; la regresión reproduce el formato y las referencias del texto aportado.
- El mismo reconocimiento de autores se aplica al particionado de bibliografía para Qwen: una lista larga con editores se divide en obras completas sin superar el presupuesto de cada fragmento.
- HTML: se conserva la composición de bloques reconocidos y sus estilos, se descartan bloques ajenos de la página usada como plantilla y se limpian textos residuales de las celdas de rúbrica manteniendo su cadena de estilos. La cabecera bibliográfica prevalece al reconocer una tabla que ya contenga texto contaminado de otro bloque. Regresiones con plantillas contaminadas y reutilización de una página generada para otro sílabo.
- Caché/aislamiento: respuestas HTTP con `Cache-Control: no-store`. No se añadió caché de documentos. Las sesiones activas conservan solo sus datos para revisión/publicación; Qwen recibe mensajes independientes por llamada. Se probaron filtros por documento incluso con embeddings idénticos, lecturas simultáneas del mismo PDF con identificadores diferentes y borrado de vectores/archivos temporales tanto con éxito como con error. Qdrant: **0 fragmentos** antes y después de desplegar.
- Pruebas finales: **208 passed, 5 deselected**, 194.82 s (`python -m pytest sistema/tests tests -q --tb=short`). **3/3 contra Qwen real** de contexto consecutivo A/B/A, simultáneo y largo (16.76 s), y **2/2 de extracción completa** con los sílabos de referencia (189.20 s). La prueba de no bloqueo de IA usa ahora un evento de sincronización en vez de un umbral frágil de 2.5 s que incluía el tiempo de lectura del PDF.
- Imagen construida y app recreada, sin reiniciar el túnel. URL vigente: https://calculators-concluded-region-finite.trycloudflare.com . Desde HTTPS: interfaz y salud 200, `no-store`, reglas/Qwen/Qdrant `ok`. No se modificó Canvas real: para corregir páginas ya publicadas, volver a cargar, revisar y publicar el sílabo. Las sesiones anteriores al reinicio se cerraron.

### 2026-11-09 · Recuperación del enlace temporal
- El usuario reportó `DNS_PROBE_FINISHED_NXDOMAIN`. App y Qdrant seguían activos; salud local con reglas/Qwen/Qdrant `ok`. El contenedor del túnel seguía ejecutándose, pero sus registros mostraban desconexión y `Unauthorized: Tunnel not found`: falló el enlace de Cloudflare, no se apagó la app por un temporizador.
- Se reinició únicamente `silabos-tunel`; no se recreó la app ni se borraron sesiones. Nueva URL: **https://caps-republican-api-inclusive.trycloudflare.com**. Se configuró `restart: unless-stopped` en ese contenedor para que vuelva a iniciarse con Docker; esto no detecta un túnel inválido mientras el proceso siga activo ni convierte la URL temporal en permanente.
- Los túneles temporales no tienen un intervalo fijo de apagado ni garantía de continuidad. Para un enlace estable hace falta un túnel configurado con dominio o despliegue permanente.
