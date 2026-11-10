# Sílabo → Aula virtual

Asistente web que convierte el sílabo institucional (PDF) en las páginas **"Momento N"** de un curso
de Canvas y **las publica en el curso con el token del docente**, previa revisión y aprobación.
Implementa las reglas de `../PROMPT_MAESTRO_Silabo_a_Canvas.md` en código.

## Qué pide al docente
1. **Sílabo PDF**.
2. **URL del curso**: `https://indoamerica.instructure.com/courses/12345`.
3. **Token de Canvas**: Cuenta → Configuraciones → *+ Nuevo token de acceso* (expiración: mañana).

Ya **no** se pide el HTML de la página: el sistema lee la página "Momento N" actual del curso y la usa
como plantilla (si no tiene la estructura, usa `plantillas/momento_institucional.html`).

## Flujo
| Paso | Qué pasa |
|---|---|
| 1. Tus datos | Valida PDF, URL (`*.instructure.com`) y token; lee el curso **solo con GET**. |
| 2. Revisión | Ficha, momentos y **página de Canvas destino** de cada uno (buscada en la página de inicio → módulos → búsqueda), **advertencias** (incluye "el curso no parece del mismo proyecto formativo"), propósitos y bibliografía **editables**. |
| 3. Vista previa | HTML real por momento + **lista de control**. Los fallos quedan visibles como avisos: el docente puede continuar y confirmar que publica de todos modos. Se exige una vista previa completa y actualizada. |
| 4. Publicar | Casilla de confirmación → por cada página: respaldo del contenido actual, `PUT` solo del cuerpo (no cambia título ni estado de publicación), relectura y verificación. Botón **Restaurar anterior** por página, ZIP con HTML + informe + respaldo, y **Terminar** (borra sesión y token). |

## Seguridad del token
- Vive solo en memoria durante la sesión (máx. 1 h); no se guarda, no se registra y no vuelve al navegador.
- Solo se envía al servidor del curso (`*.instructure.com` o `CANVAS_HOSTS`).
- El cliente rechaza cualquier escritura sin aprobación explícita.
- **Si se publica en red, debe ir detrás de HTTPS** (el token viaja en el formulario).

## Arrancar
Con Docker (sistema + BD vectorial Qdrant), desde la raíz del proyecto:
```powershell
copy .env.example .env
docker compose up -d --build      # → http://localhost:8770 (solo este equipo)
```
Sin Docker (Qdrant en memoria):
```powershell
.\iniciar.ps1          # solo este equipo → http://localhost:8770
.\iniciar.ps1 -Red     # en red (servidor de la UTI) — solo detrás de HTTPS
```
`GET /api/salud` muestra el estado de las piezas: `{"reglas":"ok","qwen":"ok|no_disponible","qdrant":"ok|memoria|no_disponible"}`.

## Modo IA (modelo local de la universidad)
La IA **no publica nada por su cuenta**. Qwen3-8B (vLLM, `QWEN_URL`) lee el mismo sílabo en segundo plano y:
1. **Compara** su lectura con la de las reglas y muestra las diferencias en el paso 2 (importantes en rojo, de texto en naranja).
2. **Completa solo bloques que las reglas dejaron vacíos** (momento sin sesiones/rúbrica, RA sin texto), con la advertencia grave "Leído por IA, revisar".
3. **Redacta el propósito** de cada momento (PROPUESTO, validado); el docente decide con "Usar esta redacción".

Lo publicado sale siempre de la lectura por reglas y pasa por la lista de control. Si Qwen no responde, todo funciona igual.

Cada lectura usa su propio identificador y cada petición a Qwen incluye únicamente su contexto actual, sin historial de otras cargas. Los fragmentos temporales del sílabo en Qdrant se borran al finalizar, también si falla la IA. Las respuestas HTTP llevan `Cache-Control: no-store`; los datos necesarios para revisar y publicar viven en la sesión activa hasta terminarla o hasta que expire.

La plantilla aporta los bloques y estilos del HTML. Al generar se reemplazan sus datos y se eliminan bloques ajenos, fechas anteriores y texto residual de las celdas de rúbrica. Al volver a publicar se sustituye el cuerpo de la misma página Momento, con respaldo restaurable. La bibliografía se toma de la sección VI, sin confundirla con menciones en Recursos ni con el índice. Se incluyen todas las obras complementarias en cada momento por defecto; el docente puede desmarcarlas en la revisión. Las notas de consulta se conservan como texto, fuera de la URL.

Antes de reutilizar una página del curso se comprueba también la estructura interna de sus tablas (cabeceras, cuerpos, celdas y filas modelo de la rúbrica). Si está incompleta, se avisa y se usa la plantilla institucional; el contenido anterior se respalda al publicar.

Pruebas de contexto del modelo real (documentos alternados, simultáneos y contexto largo):
```powershell
python -m pytest sistema/tests/test_aislamiento_contexto.py -m qwen -q
```

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `QWEN_URL` | `http://172.16.8.69:8000/v1` | servidor vLLM (ventana de 8192 tokens, JSON con esquema) |
| `QWEN_MODEL` | `Qwen/Qwen3-8B-AWQ` | modelo |
| `QWEN_TIMEOUT` | `120` | segundos por petición (un reintento) |
| `IA_ACTIVA` | `1` | `0` apaga la IA para todos |
| `IA_PARALELO` | `6` | peticiones simultáneas por docente (el servidor atiende 16) |
| `QDRANT_URL` | vacío (memoria) | `http://qdrant:6333` en Docker |

Herramientas de evaluación (desde `sistema/`):
```powershell
python -m ia.evaluar ..\silabos_prueba\*.pdf --repeticiones 2   # exactitud campo a campo vs reglas → reportes_ia/
python -m ia.visor                                              # reportes_ia/visor.html (páginas lado a lado)
python -m ia.estres --niveles 1 4 16                            # estrés del servidor Qwen
```
Resultados al 2026-11-09: exactitud 99.3–99.6 % de campos; 16 peticiones simultáneas sin errores (≈ 430 tokens/s).

## Estructura
```
app.py                 API: /api/analizar · /generar · /publicar · /restaurar · /descargar/{sid} · /terminar/{sid}
core/canvas.py         cliente Canvas (token) y localización de las páginas Momento
core/silabo.py         lector del PDF → datos
core/validador.py      advertencias del sílabo
core/propuestas.py     propósito y reparto de bibliografía
core/render.py         llena la plantilla sobre el árbol HTML
core/calidad.py        lista de control
core/paquete.py        ZIP + informe + respaldo
core/servicio.py       orquesta el flujo
static/index.html      interfaz (4 pasos)
tests/mock_canvas.py   Canvas simulado (pruebas y servidor local en :8771)
tests/test_sistema.py  extremo a extremo contra el Canvas simulado
tests/test_kit.py      coherencia del prompt maestro y de publicar_canvas.ps1
ia/qwen.py             cliente del modelo local (ventana, reintento, disponibilidad)
ia/documento.py        PDF → bloques para la BD vectorial y registros etiquetados por columna
ia/vectores.py         Qdrant + embeddings locales (FastEmbed)
ia/extractor.py        tareas a Qwen con esquema JSON → mismo formato que core/silabo
ia/concordancia.py     diferencias reglas ↔ IA con gravedad
ia/trabajo.py          segunda lectura en segundo plano y respaldo por bloque
ia/salud.py            /api/salud
ia/evaluar.py · visor.py · estres.py   herramientas de evaluación
```

## Pruebas
```bash
python -m pytest sistema/tests tests -v          # 185 pruebas, sin red: nunca tocan Canvas real ni Qwen
python -m pytest sistema/tests -m qwen -v        # exactitud contra el servidor Qwen real (~3 min)
```
Para probar la interfaz completa en local:
```bash
python sistema/tests/mock_canvas.py 8771
```
```powershell
$env:CANVAS_API_OVERRIDE='http://127.0.0.1:8771'; python -m uvicorn --app-dir sistema app:app --port 8772
```
Curso `https://indoamerica.instructure.com/courses/36254`, token `TOKEN_PRUEBA_0123456789`.

## Antes de usarlo con cursos reales
Probar una vez en un **curso sandbox** con un token de prueba (que se elimina al terminar): confirmar
que encuentra las páginas, que Canvas guarda el HTML sin alterarlo ("Publicada y verificada") y que
"Restaurar" funciona.
