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
| **Guías prácticas → tareas PAE + rúbricas** (nuevo, 2026-11-11) | ✔ Probado contra Canvas simulado y con Qwen real; **falta probarlo en un curso de prueba de Canvas** | `sistema/core/guia.py`, `pae.py`, `servicio_guias.py`, `static/guias.html` |
| **Historial de cargas** (nuevo, 2026-11-14) | ✔ Botón 🕘 Historial + `/historial`; SQLite en volumen Docker; siembra de lo anterior; correcciones manuales; CSV | `sistema/core/historial.py`, `static/historial.html` |

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
- Túnel HTTPS temporal **abierto tras la confirmación explícita del usuario**, después de informar que cualquier persona con el enlace puede acceder. Contenedor `silabos-tunel`, imagen oficial `cloudflare/cloudflared:latest` (2026.10.7), conectado a la red Docker del sistema; no se expusieron puertos adicionales. URL: (URL temporal del túnel: se comparte por chat, no se publica) . Verificado desde HTTPS: interfaz 200 y `/api/salud` 200 con reglas/Qwen/Qdrant `ok`. Para cerrarlo: `docker stop silabos-tunel`. Requiere mantener el equipo y Docker funcionando; al recrearlo cambia la URL. La revisión automática rechazó el primer intento por faltar autorización explícita de exposición pública; tras solicitarla y recibirla se aprobó el segundo intento.

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
- Tras el reinicio realizado por el usuario, app/Qdrant/túnel activos y `/api/salud` con reglas/Qwen/Qdrant `ok`. El túnel reiniciado cambió de URL: **(URL temporal del túnel: se comparte por chat, no se publica)**. La actualización posterior recreó solo la app, sin reiniciar el túnel. Las sesiones anteriores deben volver a cargarse.

### 2026-11-09 · Bibliografía de Antropología, estructura HTML y aislamiento del contexto
- Causa reproducida desde el texto pegado por el usuario: `_biblio` tomaba la primera mención a «Bibliografía básica» en Recursos y arrastraba sesiones/rúbricas hasta la sección VI. Ahora delimita la sección bibliográfica real, distingue el índice y exige encabezados completos de básica/complementaria. Reconoce referencias con nombres completos y `(Ed.)` como obras separadas. No se dispuso del PDF original de Antropología; la regresión reproduce el formato y las referencias del texto aportado.
- El mismo reconocimiento de autores se aplica al particionado de bibliografía para Qwen: una lista larga con editores se divide en obras completas sin superar el presupuesto de cada fragmento.
- HTML: se conserva la composición de bloques reconocidos y sus estilos, se descartan bloques ajenos de la página usada como plantilla y se limpian textos residuales de las celdas de rúbrica manteniendo su cadena de estilos. La cabecera bibliográfica prevalece al reconocer una tabla que ya contenga texto contaminado de otro bloque. Regresiones con plantillas contaminadas y reutilización de una página generada para otro sílabo.
- Caché/aislamiento: respuestas HTTP con `Cache-Control: no-store`. No se añadió caché de documentos. Las sesiones activas conservan solo sus datos para revisión/publicación; Qwen recibe mensajes independientes por llamada. Se probaron filtros por documento incluso con embeddings idénticos, lecturas simultáneas del mismo PDF con identificadores diferentes y borrado de vectores/archivos temporales tanto con éxito como con error. Qdrant: **0 fragmentos** antes y después de desplegar.
- Pruebas finales: **208 passed, 5 deselected**, 194.82 s (`python -m pytest sistema/tests tests -q --tb=short`). **3/3 contra Qwen real** de contexto consecutivo A/B/A, simultáneo y largo (16.76 s), y **2/2 de extracción completa** con los sílabos de referencia (189.20 s). La prueba de no bloqueo de IA usa ahora un evento de sincronización en vez de un umbral frágil de 2.5 s que incluía el tiempo de lectura del PDF.
- Imagen construida y app recreada, sin reiniciar el túnel. URL vigente: (URL temporal del túnel: se comparte por chat, no se publica) . Desde HTTPS: interfaz y salud 200, `no-store`, reglas/Qwen/Qdrant `ok`. No se modificó Canvas real: para corregir páginas ya publicadas, volver a cargar, revisar y publicar el sílabo. Las sesiones anteriores al reinicio se cerraron.

### 2026-11-09 · Recuperación del enlace temporal
- El usuario reportó `DNS_PROBE_FINISHED_NXDOMAIN`. App y Qdrant seguían activos; salud local con reglas/Qwen/Qdrant `ok`. El contenedor del túnel seguía ejecutándose, pero sus registros mostraban desconexión y `Unauthorized: Tunnel not found`: falló el enlace de Cloudflare, no se apagó la app por un temporizador.
- Se reinició únicamente `silabos-tunel`; no se recreó la app ni se borraron sesiones. Nueva URL: **(URL temporal del túnel: se comparte por chat, no se publica)**. Se configuró `restart: unless-stopped` en ese contenedor para que vuelva a iniciarse con Docker; esto no detecta un túnel inválido mientras el proceso siga activo ni convierte la URL temporal en permanente.
- Los túneles temporales no tienen un intervalo fijo de apagado ni garantía de continuidad. Para un enlace estable hace falta un túnel configurado con dominio o despliegue permanente.

### 2026-11-11 · Menú principal y flujo "Guías prácticas" (tareas PAE + rúbricas)
- **Pedido del usuario**: menú con dos opciones (Sílabos, que ya existía, y Guías prácticas). De cada guía se crea una
  tarea en **Tareas → grupo Actividades** con el nombre **`PAE#-Nombre de la guía`** y una rúbrica con **el mismo nombre**,
  tomada de la rúbrica del momento del sílabo y adaptada al contexto de la guía. Mockup previo: `diseno/mockup_guias.html`.
- **Rutas**: `/` = menú (`static/menu.html`), `/silabos` = flujo anterior (sin cambios salvo enlace "← Menú principal"),
  `/guias` = flujo nuevo. Enlaces relativos: funciona también detrás de `/aulasvirtuales/` (deploy/nginx).
- **Lectura de la guía** (`core/guia.py`): tablas de pdfplumber del formato FOR-GPFM; varias guías por PDF; título y textos
  en MAYÚSCULAS → tipo oración respetando siglas (IA, PIS, SQL…). Campo "Resultados de Aprendizaje" = `null` → se toma el RA del momento.
- **Emparejado guía ↔ momento** (`core/pae.py`): por título del momento y por fechas; avisa si no coinciden. El docente puede cambiarlo.
- **Decisiones (suposiciones del mockup, aplicadas y editables en pantalla)**:
  1. N° de PAE = "Guía N°" del PDF. 2. 10 pts por tarea; repartidos por igual entre indicadores; niveles al 20/40/60/80/100 %.
  3. Se conservan los indicadores y los 5 niveles del momento; solo cambia la redacción. 4. Tarea **sin publicar**,
  disponible desde 00:00 del inicio y entrega 23:59 del fin (−05:00), entregas en línea (archivo o URL), y se agrega al módulo "Momento N".
  5. Descripción de la tarea = guía completa (objetivo, fundamento, procedimiento, resultado, conclusiones, RA) con cabecera institucional.
- **Canvas (API oficial revisada)**: `GET assignment_groups` (busca "Actividades"), `GET assignments?search_term=PAE` (secuencia y duplicados),
  `POST assignments`, `POST rubrics` (formulario `rubric[criteria][i][ratings][j]…` + `rubric_association` Assignment/grading),
  `POST modules/:id/items`. Tras crear, **relee** la tarea (grupo, rúbrica asociada, sin publicar) y el apartado Rúbricas.
  "Deshacer" borra solo lo creado en la sesión (`DELETE rubrics/:id` y `assignments/:id`). Nada se escribe sin la casilla de confirmación.
- **Qwen**: primera versión (toda la rúbrica en una llamada) corría los niveles de lugar y anteponía "Receptivo:". Ahora: **una llamada por
  indicador** con un campo por nivel, limpieza de prefijos y rellenos, y una celda solo se acepta si aporta términos de la guía y se parece más a
  su propio nivel original que a los demás; si no, queda el texto del sílabo. Prueba real Guía N° 3: 9 de 20 descriptores adaptados, sin niveles corridos.
- **Verificación**: 15 pruebas nuevas (`sistema/tests/test_guias.py`, usa `B26_Software_Programacion Estructurada.pdf` y
  `sistema/tests/fixtures/guia_pe_n3.pdf`, ambos ignorados por git); suite completa 267 ✔. Flujo completo en navegador contra Canvas simulado:
  creada y verificada (grupo Actividades, rúbrica asociada y visible en Rúbricas, módulo Momento 3). Docker reconstruido; se recreó el contenedor de
  Qdrant porque había quedado sin nombre en la red nueva (`192.168.240.0/24`).
- **Pendiente**: prueba en un curso de prueba de Canvas real (la publica el docente). Confirmar ahí: que la rúbrica aparezca en "Rúbricas → Guardado",
  cómo muestra la interfaz nueva de Rúbricas los 5 niveles y que el token tenga permiso para crear tareas y rúbricas.


### 2026-11-11 · Guías: error "Hay cambios sin vista previa" con 4 guías (prueba del usuario, curso 36283)
- **Causa**: Qwen adapta las rúbricas una guía tras otra en segundo plano; el usuario generó la vista previa antes de que
  terminara alguna. Al terminar, Qwen cambió esa rúbrica y el servidor (correctamente) bloqueó publicar algo no revisado.
- **Arreglo** (`static/guias.html`): mientras Qwen trabaja, "Vista previa →", "Adaptar con Qwen" y "Volver a la rúbrica del
  sílabo" quedan deshabilitados, la rúbrica de la guía en curso no se puede editar, las pestañas muestran ⏳ y un aviso lista
  las PAE pendientes. Si aun así aparece el error en el paso 5, hay un botón "Generar la vista previa de nuevo".
- **Verificado** en navegador contra Canvas simulado + Qwen real: bloqueado durante la adaptación, habilitado al terminar,
  creada y verificada. Docker reconstruido.

### 2026-11-11 · Medición del contexto frente al modelo local (Qwen3-8B, ventana 8192 entrada+salida)
- Herramienta nueva `sistema/ia/medir_contexto.py`: arma los mismos mensajes que enviaría el sistema y los cuenta con el
  tokenizador del servidor (`/tokenize` con plantilla de chat, sin razonamiento); la salida se proyecta con la relación
  salida/entrada más alta de las corridas reales (o con el tope fijo de la llamada). No genera texto (carga mínima).
- **31 sílabos** (Arquitectura, Enfermería, Ingeniería, Medicina, Odontología) + Guía N° 3: 1 621 llamadas medidas.
  **Peor llamada: rúbrica de momento, 3 443 tokens = 42 % de la ventana**; ninguna supera el 75 % ni deja de caber.
  Por tipo (máximo): rúbrica 42 %, guía/indicador 23 % (con tope 900), bibliografía 20 %, pie 20 %, sesión 20 %,
  propósito 19 %, RA 14 %, PIS 10 %, cabecera 9 %.
- La estimación local `len/2.5` siempre **sobreestima** (×1.04–×1.70): el corte de bibliografía es seguro.
- Prueba real de la adaptación de rúbrica (4 llamadas): 930–949 tokens de entrada, **141–206 de salida**, 8.4 s en total.
- Carga por sílabo en modo IA: 15–72 llamadas (mediana 51), ~15 k–79 k tokens (mediana 56 k); las sesiones son la mayoría.
- Informe: `reportes_ia/contexto_20261111_124651.json`.

### 2026-11-11 · Sílabos: columna "Enlaces" borrada en la página del curso (sílabo de maestría)
- **Problema**: la página "Momento N" del curso, usada como plantilla, había perdido por accidente la última columna
  de la tabla de sesiones ("Enlaces"); el sistema la aceptaba como válida y generaba las páginas sin esa columna.
  Además, al volver a publicar, la columna Enlaces se reescribía con "(Pegar enlace)" y se perdían los enlaces del docente.
- **Arreglo** (`core/render.py`, `core/servicio.py`): las 6 columnas del modelo institucional son obligatorias; si falta
  alguna, se usa la plantilla institucional completa y el aviso del paso 2 dice exactamente qué faltaba
  (p. ej. `sesiones: falta la columna "Enlaces"`). Los enlaces que el docente ya pegó en cada sesión se conservan al republicar.
- Pruebas nuevas en `test_plantillas_incompletas.py` (columna borrada → plantilla institucional y aviso; enlace del docente conservado).

### 2026-11-14 · Historial de cargas (botón "🕘 Historial")
- **Pedido**: registro histórico propio de todo lo cargado (sílabos y guías). Mockup aprobado: `diseno/mockup_historial.html`
  (botón arriba a la derecha + corrección manual de registros). Diseño: `docs/superpowers/specs/2026-11-14-historial-design.md`;
  plan: `docs/superpowers/plans/2026-11-14-historial.md` (5 tareas, ejecutadas en esta sesión).
- **Qué hace**: cada analizar / publicar / restaurar (Sílabos) y analizar / crear PAE / deshacer (Guías) deja una fila con fecha
  (hora de Ecuador), tipo, nombre del archivo, curso, acción, resultado (ok / avisos / error), detalle y enlaces a Canvas.
  Errores también (token rechazado, publicación bloqueada). **Nunca** guarda el token ni el PDF. Si el historial falla, el flujo sigue.
- **Página `/historial`**: resumen (eventos, cursos, publicaciones, errores), filtros (tipo, curso, texto, orden), detalle por fila,
  **✎ Corregir** (resultado real + nota; el original queda tachado; "Quitar corrección") y **⬇ Exportar CSV** (UTF-8 con BOM, `;`).
- **Siembra** (8 filas "reconstruido", una sola vez): Medicina 36732 (06/11, 4/4 momentos), PE 36283 Momento 1 (06/11, prompt maestro),
  PAE1–PAE4 bloqueadas (11/11), y las 5 acciones del 12/11 17:59–18:05 sacadas del registro de Docker (sin nombre: no se registró).
- **Almacenamiento**: SQLite en `HISTORIAL_DB`; Docker: volumen `historial_data` → `/datos/historial.sqlite` (sobrevive a reconstruir).
  Local: `datos/` (ignorado por git). `HISTORIAL=0` lo apaga; `HISTORIAL_CLAVE` exige clave — **obligatoria en un servidor compartido**
  (documentado en `.env.example` y `deploy/README.md`).
- **Pruebas**: `sistema/tests/test_historial.py` (18) + `conftest.py` que manda toda la suite a una base temporal. Suite completa
  **296 passed**. Un defecto real detectado por `test_ruta_publica`: el script que oculta el botón quedó dentro de un texto JS de
  index.html → se movió antes del último `</body>`.
- **Verificado en Docker**: siembra visible (8 eventos, 2 cursos, 6 publicaciones, 2 errores); corrección desde la pantalla con texto
  HTML mostrado escapado y luego quitada; tras reiniciar el contenedor siguen 8 filas (sin duplicar la siembra); CSV correcto.
- **Pendientes menores**: CSV sin neutralizar celdas que empiezan con "=" (Excel); "%" y "_" funcionan como comodines en la búsqueda.


### 2026-11-14 · Historial: carga de los sílabos ya publicados (carpeta SILABOS B26)
- Pedido del usuario: incluir en el historial todos los sílabos ya cargados entre el vie 06/11 y el jue 12/11/2026
  (vie 13 feriado local), **con la fecha en blanco**. Fuente: `C:\Users\Chris\Desktop\SILABOS B26` (34 PDF, todos legibles).
- Se agregaron **32** filas "reconstruido" (tipo Sílabos, acción "Publicado (carga previa al historial)", curso = nombre del
  proyecto formativo + código académico, detalle = carpeta · carrera · periodo, fuente "Carpeta SILABOS B26"). **No se
  duplicaron** los 2 que ya estaban por nombre de archivo: Computación y Sociedad (Medicina 36732) y Programación Estructurada.
  Carga única (marca `carga_silabos_b26` en `meta`). Odontología trae Anatomía General dos veces (dos archivos con el mismo
  código B26-ODO-1-54622-1736): quedaron ambas filas.
- Defecto encontrado y corregido: `registrar(fecha='')` ponía la fecha actual (`fecha or ahora()`); ahora solo `None` usa la
  hora actual. Prueba `test_fecha_en_blanco_se_respeta`. Durante el arreglo, una edición dejó roto el INSERT (~1 min en Docker,
  sin uso real); detectado por las pruebas y corregido; Docker reconstruido y comprobado con un registro de prueba (borrado).
- Estado en Docker: 40 eventos, 33 cursos, 38 publicaciones, 2 errores; 32 filas sin fecha al final de la lista.
- **Decisión del usuario (2026-11-14)**: el historial queda tal como está, incluidas las filas repetidas (algunos proyectos
  formativos se subieron 2 veces, p. ej. Anatomía General de Odontología). No borrar ni fusionar filas.

### 2026-11-14 · Commit
- Commit `80f5ef9` en `main` (repositorio local, sin remoto): menú, Guías prácticas, Historial, columna Enlaces, medición de
  contexto, deploy y pruebas (45 archivos). Sin secretos ni PDF (ignorados: `.env`, `*.pdf`, `datos/`, `reportes_ia/`).

### 2026-11-14 · Revisión de seguridad automática del commit (historial) — 3 hallazgos corregidos
1. **Historial abierto por defecto en un servidor** → ahora **falla cerrado**: si la petición llega por el proxy (cabeceras
   `X-Forwarded-For`/`X-Real-IP` que pone nginx) y no hay `HISTORIAL_CLAVE`, la API responde 403. En el propio equipo sigue abierto.
2. **Inyección de fórmulas en el CSV** → toda celda que empiece con `= + - @`, tabulador o retorno se antepone con `'`.
3. **Clave en la URL** (`?clave=` en el enlace del CSV) → la clave solo se acepta en la cabecera `X-Historial-Clave`; el CSV se
   descarga con `fetch` + blob. Se quitó el parámetro `clave` de todos los endpoints.
- Pruebas nuevas: `test_detras_de_un_proxy_sin_clave_se_cierra`, `test_detras_de_un_proxy_con_clave_funciona`,
  `test_csv_neutraliza_formulas` y la de clave ajustada (rechaza `?clave=`): primero fallaron, luego pasan (22 + ruta pública).
- Docker reconstruido: 40 eventos intactos, proxy sin clave → 403, CSV desde la página (8.5 KB, sin clave en ningún enlace).

### 2026-11-14 · Historial: nueva lectura de SILABOS B26 (subcarpetas) y acceso sin clave solo por opción explícita
- La carpeta ahora tiene **51 archivos** (39 sílabos + 12 guías prácticas) en subcarpetas nuevas (`Arquitectura\Guias Practicas`,
  `Ingenieria\Guias practica`, `Maestrias`). Se agregaron **17** que faltaban (sin fecha, "reconstruido", fuente "Carpeta SILABOS B26"):
  6 guías de Ciudad y Planificación Territorial (G1–G6), 4 de Programación Estructurada, 2 de Introducción a la Seguridad Informática,
  3 sílabos nuevos de Arquitectura (Análisis Matemático, Optativa/Electiva II, Ciudad y Planificación Territorial) y 2 de Maestrías
  (Ciberseguridad, Sistemas de Control). Guías como "PAE creadas (carga previa al historial)"; su código de curso se tomó del sílabo
  del mismo proyecto. Los 34 ya registrados (mismo nombre de archivo) no se repitieron. Historial: **57 eventos, 39 cursos**.
- **Revisión de seguridad** (aviso automático): la protección "sin clave → cerrado detrás del proxy" dependía de cabeceras. Ahora
  **sin `HISTORIAL_CLAVE` el historial está cerrado por defecto**; solo se abre sin clave con `HISTORIAL_LOCAL=1` (y aun así nunca si
  la petición viene por un proxy). En el `.env` de este equipo se puso `HISTORIAL_LOCAL=1`; `.env.example` trae `0`; el servidor no
  debe usarlo. Prueba `test_sin_clave_y_sin_opcion_local_se_cierra` (falló primero). 25 pruebas del historial y ruta pública en verde;
  Docker reconstruido: local abierto, proxy sin clave → 403.

### 2026-11-14 · Menú: se quitó la etiqueta "NUEVO" de Guías prácticas
- Pedido del usuario. Solo `sistema/static/menu.html` (etiqueta y su estilo); sin cambios de lógica. Docker reconstruido y comprobado.

### 2026-11-16 · Sistema y puente (túnel) levantados para compartir con un compañero de otra sede
- Pedido del usuario: levantar todo para compartir. App y Qdrant iniciados (`docker compose up -d`).
- El contenedor `silabos-tunel` apuntaba a la red Docker anterior (se recreó al fijar la subred 192.168.240.0/24) y no arrancaba:
  se recreó con la misma configuración e imagen local (`cloudflare/cloudflared:latest`, `tunnel --no-autoupdate --protocol http2
  --url http://app:8770`, red `aulasvirtuales-silabos_default`, `restart: unless-stopped`).
- **URL vigente: (URL temporal del túnel: se comparte por chat, no se publica)** (cualquiera con el enlace puede abrir el sistema;
  cada docente usa su propio token de Canvas). Verificado por HTTPS: menú, Sílabos y Guías 200; salud reglas/Qwen/Qdrant `ok`.
- Historial: por el túnel queda **cerrado** (estado `requiere_clave`, API 403), así el compañero no ve el historial del usuario;
  en este equipo sigue abierto (57 eventos). Lo que el compañero cargue sí queda registrado en el historial de este equipo.
- Para cerrar el puente: `docker stop silabos-tunel`. Al reiniciarlo cambia la URL.

### 2026-11-16 · Cambios subidos a GitHub (https://github.com/CZurita14/AulasVirtuales, **público**)
- El repo de GitHub se creó aparte el 10/11 (sin historia en común con este repo local) y **no publica PDF de docentes**.
  Para no reescribir lo que hay allí ni publicar los 2 PDF que sí están en la historia local, se subió **un commit de
  sincronización** encima de `origin/main`: commit `18b8d4b` (avance rápido desde `3e09732`, sin forzar). Contiene el árbol de
  `main` local **sin** `B26_Software_Programacion Estructurada.pdf`, `silabos_prueba/*.pdf` ni `.claude/`, y el README raíz con
  la sección "Qué incluye" (Sílabos, Guías prácticas, Historial).
- Antes se quitaron de `progress.md` las URL del túnel (una estaba activa): en un repo público abrirían el sistema a cualquiera.
- Rama local `github` = `origin/main`. **Para la próxima subida** repetir el mismo método (árbol de `main` sin PDF ni `.claude/`
  como commit nuevo sobre `origin/main`); **no** hacer `git push` de `main` ni forzar.

### 2026-11-16 · Se cayó el puente: causa, arreglo y vigilante
- **Síntoma:** el compañero veía `DNS_PROBE_FINISHED_NXDOMAIN` en la URL del túnel. La app local seguía bien (200) y los 3
  contenedores estaban "Up".
- **Causa:** a las 14:49 UTC Cloudflare cortó la conexión y al reconectar respondió `Unauthorized: Tunnel not found`: borró el
  **túnel rápido** (trycloudflare no garantiza duración). `cloudflared` reintenta para siempre pero nunca pide uno nuevo.
- **Arreglo:** `docker restart silabos-tunel` → túnel nuevo con **otra URL** (compartida por chat, no se anota aquí). Verificado:
  página 200 y `/api/historial` 403 por el túnel (el historial sigue cerrado desde fuera).
- **Vigilante:** `deploy/vigilar_tunel.ps1`. Comprueba la app (si no responde, `docker compose up -d`) y el túnel (si no existe lo
  crea; si su URL no responde 2 veces lo reinicia). Guarda la URL vigente en `datos\tunel_url.txt` (ignorado por git), anota en
  `datos\vigilancia.log` y avisa en pantalla cuando cambia la URL. Probado a mano: sin fallos, escribió la URL.
- **Tarea programada** `AulasVirtuales - vigilar puente` (cada 5 min y al iniciar sesión), registrada por el usuario. Primera
  ejecución 10:30: resultado 0, sin incidencias y sin reiniciar el túnel (la URL sigue igual).
- **Límite:** con túnel rápido la URL cambia en cada caída. Una URL fija requiere un túnel con nombre (cuenta de Cloudflare +
  dominio) o el despliegue en el servidor de la UTI (Fase 1 del plan del historial).

### 2026-11-16 · Dirección fija con Tailscale Funnel (reemplaza al túnel temporal)
- **Por qué:** el túnel rápido de Cloudflare cambia de URL en cada caída. Se descartó Supabase (es base de datos; no ejecuta
  la app en Python) y un hosting en la nube (no llega al Qwen interno 172.16.8.69 y los tokens pasarían por terceros).
- **Qué se hizo:** servicio `funnel` en `docker-compose.yml` (perfil `publico`, imagen `tailscale/tailscale:v1.90.6`, modo
  userspace, identidad en el volumen `tailscale_estado`) + `deploy/tailscale/funnel.json` (HTTPS 443 → `http://app:8770`,
  Funnel activado). El usuario inició sesión en su cuenta de Tailscale y activó HTTPS/Funnel en su red.
- **Dirección fija:** `aulasvirtuales.<tailnet>.ts.net` (completa: se comparte por chat, no se publica en el repo).
- **Verificado por la dirección fija:** `/`, `/silabos`, `/guias`, `/historial` → 200; `/api/historial` → 403 y
  `requiere_clave: true` (el historial sigue cerrado desde fuera). Los primeros intentos fallaban (reset TLS) hasta que
  Tailscale emitió el certificado (~2 min). Tras `docker restart` del puente vuelve en ≤10 s con la **misma** dirección.
- **Túnel temporal de Cloudflare apagado:** `silabos-tunel` detenido y sin reinicio automático (sigue creado, no borrado).
- **Vigilante reescrito** (`deploy/vigilar_tunel.ps1`): ahora vigila la app y el puente Tailscale (`docker compose --profile
  publico up -d` si algo cae; reinicia el puente si la dirección fija no responde 3 veces). Probado: salida 0, sin incidencias.
- Documentado en `deploy/README.md`.

### 2026-11-16 · Historial visible para todo el equipo con una clave compartida
- El usuario quiere ver el historial desde cualquier equipo. Como la dirección fija es pública en internet, se eligió una
  **clave del equipo** (no abrirlo a cualquiera).
- `historial.html`: la clave se guarda en `localStorage` (antes `sessionStorage`), así cada navegador la pide **una sola vez**;
  si el servidor responde 401 (clave cambiada o incorrecta) se olvida y se vuelve a pedir. Suite: 202 passed. App reconstruida.
- **Pendiente del usuario:** definir `HISTORIAL_CLAVE` en `.env` (la elige y la escribe él; no pasa por el chat) y recrear la app.
  Con clave definida, también se pide en este equipo (una vez por navegador).

### 2026-11-16 · Sílabos: publicar solo los momentos elegidos
- **Pedido:** poder cargar un momento concreto (p. ej. solo el Momento 2). Mockup aprobado: `diseno/mockup_publicar_momentos.html`.
- **Paso 4 (`index.html`):** columna **Publicar** con una casilla por momento (por defecto todos marcados → igual que antes),
  accesos *Marcar todos / Ninguno*, filas desmarcadas en gris ("No se publicará"; tras publicar, "Sin cambios en Canvas").
  La confirmación dice cuántos y cuáles ("1 página Momento (Momento 2)") y el botón "Publicar 1 momento". Cambiar la selección
  quita la confirmación; tras publicar se desmarca todo (para publicar otro: marcarlo, confirmar y "Publicar de nuevo").
  Con ninguno marcado, el botón queda desactivado ("Elige al menos un momento"). Restaurar no cambia.
- **Servidor (`servicio.publicar`):** quita repetidos, rechaza lista vacía y momentos que el sílabo no tiene (sin publicar nada).
  Historial: "Publicado Momento 2" (singular) o "Publicado Momentos 1, 3".
- **Pruebas:** +3 (`test_publicar_solo_un_momento_elegido`, `…sin_momentos…`, `…momento_inexistente…`); ajustado el texto
  esperado en `test_historial`. Suite: **205 passed**. Probado en navegador contra el Canvas simulado: solo Momento 2 →
  "✔ Publicada y verificada" y los demás "Sin cambios en Canvas". App de Docker reconstruida; en la dirección fija ya está.
- `.claude/launch.json` (local, no se sube): el servidor de prueba `guias-prueba` arranca con `HISTORIAL=0` para no ensuciar
  el historial.
- **Clave del equipo creada por el usuario** (en `.env`; no se anota aquí). Verificado por la dirección fija y en local:
  sin clave → 401, clave incorrecta → 401, con la clave → 200. La app en Docker la tiene cargada.

### 2026-11-16 · Segunda subida a GitHub
- Commit de sincronización `83fbe0d` sobre `origin/main` (avance rápido desde `18b8d4b`, sin forzar) con el árbol de `main`
  local (`d430604`) sin PDF ni `.claude/`. Revisado antes de subir: 0 PDF, sin `.env`, sin la clave del historial y sin
  direcciones del puente. README raíz: selección de momentos, clave del equipo y dirección fija opcional.

### 2026-11-16 · Protecciones extra del historial (revisión de seguridad del commit d430604)
- **Local sin clave solo por IP:** con `HISTORIAL_LOCAL=1` y sin clave, el historial se abre solo si la visita viene del propio
  equipo **por IP** (127.0.0.1/::1 o la puerta de enlace de Docker, leída de `/proc/net/route`; dentro del contenedor detecta
  `192.168.240.1`) y sin cabeceras de proxy. El puente llega desde `192.168.240.4`: aunque no agregara cabeceras, no entra.
- **Límite de intentos:** 10 claves erróneas por origen en 15 min → 429 (aunque luego acierte); 40 en total → 429 para todos.
  El origen es la IP que agrega el proxy (la última de `X-Forwarded-For`), no la que inventa el cliente. Sin clave escrita no
  cuenta. Se subió de 5 a 10 porque el equipo puede salir a internet por la misma IP de la universidad.
- **Botón "🔒 Olvidar la clave en este equipo"** en el Historial (visible solo si hay clave guardada): la borra del navegador y
  vuelve a pedirla. Para computadoras compartidas.
- Pruebas: +7 en `test_historial.py` (el cliente de pruebas ahora es 127.0.0.1). Suite: **212 passed**. App reconstruida.
  Verificado por la dirección fija: sin clave 401, clave mala 401, con clave 200; en local con clave 200.
- Subido a GitHub: commit de sincronización `90e8611` sobre `83fbe0d` (avance rápido, sin forzar; 0 PDF, sin `.env` ni la clave).

### 2026-11-16 · Corrección del límite de intentos (revisión de seguridad del commit 33bf24e)
- **Sin bloqueo global:** con 40 fallos en total se bloqueaba a todos → cualquiera podía dejar sin historial al equipo. Ahora
  el límite es solo por origen (10 fallos en 15 min).
- **Atómico:** revisar, comparar la clave y anotar el fallo ocurre bajo un mismo candado; intentos simultáneos no se cuelan.
- **X-Forwarded-For solo del proxy:** se usa únicamente si la conexión viene del puente (no del propio equipo); una visita
  directa no puede repartir sus fallos inventando cabeceras. Los orígenes sin fallos recientes se descartan (no crece sin fin).
- Pruebas: +2 netas (sin bloqueo global, XFF solo del proxy, 40 intentos simultáneos → exactamente 10 cuentan). Suite:
  **214 passed**. App reconstruida; por la dirección fija: sin clave 401, mala 401, con clave 200; local con clave 200.
- Subido a GitHub: commit de sincronización `8e0dec1` sobre `90e8611` (avance rápido, sin forzar; 0 PDF, sin `.env` ni la clave).

### 2026-11-16 · Límite de intentos: tabla acotada, IPv6 por red y clave mínima (revisión del commit f783849)
- **Tabla de fallos con tope:** `OrderedDict` de hasta 10 000 orígenes; al llenarse se descarta el más antiguo en O(1). Ya no
  se recorre toda la tabla bajo el candado.
- **IPv6 agrupado por /64:** cambiar la parte final de la dirección no salta el límite.
- **Clave mínima de 12 caracteres:** con una `HISTORIAL_CLAVE` más corta el historial responde 403 explicando el motivo. Es la
  defensa contra intentos repartidos entre muchas IP. La clave actual cumple (verificado sin mostrarla).
- **Decisión:** no se vuelve a poner un límite global. Bloquear a todos permitiría a un extraño dejar sin historial al equipo;
  frenarlo con esperas ocuparía los hilos del servidor. Queda el límite por origen + la longitud de la clave.
- Pruebas: +3 (claves de prueba ahora de 12 caracteres). Suite: **217 passed**. App reconstruida; dirección fija: sin clave
  401, mala 401, con clave 200; local con clave 200.
