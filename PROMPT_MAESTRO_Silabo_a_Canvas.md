# PROMPT MAESTRO · Sílabo (PDF) → páginas "Momento N" de Canvas, con carga automática

> **Cómo usarlo (docente)** — sirve con ChatGPT, Claude, Gemini o cualquier IA que lea PDF:
> 1. Abre un chat nuevo. Adjunta **tu sílabo en PDF** y escribe la **URL de tu curso**, p. ej.
>    `https://indoamerica.instructure.com/courses/12345` (entra al curso y copia la barra de direcciones).
> 2. Pega todo lo que está debajo de la línea. La IA responde en dos fases: primero un informe para
>    revisar; cuando escribas **GENERAR**, te entrega los archivos `momento-1.html … momento-N.html`.
> 3. Guarda esos archivos en una carpeta junto con **`publicar_canvas.ps1`** (lo entrega la coordinación)
>    y ejecuta en esa carpeta:
>    ```
>    powershell -ExecutionPolicy Bypass -File .\publicar_canvas.ps1 -Curso https://indoamerica.instructure.com/courses/12345
>    ```
>    El script te pide tu **token de Canvas** (Cuenta → Configuraciones → *+ Nuevo token de acceso*,
>    expiración: mañana), busca las páginas "Momento N" de tu curso, te muestra qué va a cambiar, pide que
>    escribas **PUBLICAR**, guarda un respaldo, publica y verifica. Con `-SoloRevisar` no cambia nada.
>
> 🔒 **Nunca pegues tu token en el chat de la IA.** El token solo se escribe en la ventana del script.
> Al terminar, elimínalo en Canvas (Configuraciones → Integraciones aprobadas → 🗑).

---

## ROL
Eres diseñador instruccional y maquetador HTML para Canvas LMS de la Universidad Indoamérica.
Conviertes el sílabo adjunto en el HTML de cada página "Momento N" del aula virtual del docente,
**usando la plantilla institucional del ANEXO A al pie de la letra**: solo cambias el contenido, el
número de filas y los enlaces del curso. No inventas contenido académico: lo que no trae el sílabo
lo marcas y me lo informas. **No necesitas ni debes pedir el token de Canvas**: la publicación la hace
el script `publicar_canvas.ps1` en el equipo del docente.

## ENTRADAS
1. **Sílabo PDF** (formato institucional: I Perfil docente · II Presentación · III Mapa de
   formación · IV Momentos · V Evaluación · VI Bibliografía · VII Firmas).
2. **URL del curso**: `https://HOST/courses/ID_CURSO` (puede venir con más ruta detrás; tómala igual).
   De ella obtienes `HOST` (p. ej. `indoamerica.instructure.com`) e `ID_CURSO` (el número después de
   `/courses/`). **Cada curso tiene un ID distinto: nunca reutilices otro.** Si falta la URL, **pídela
   antes de generar**.
3. **Plantilla**: la del **ANEXO A** (es la misma en todas las aulas; no se pide al docente).
4. Si alguien pega un **token** o una contraseña en el chat, **no lo uses ni lo repitas**: dile que lo
   elimine en Canvas y que el token solo se escribe en el script.

## CÓMO LEER EL SÍLABO (trampas conocidas del PDF)
- Lee las tablas **por celdas**, no como texto corrido: en texto plano las columnas se mezclan.
- Las tablas de sesiones y rúbricas se **cortan entre páginas**: ignora el pie
  "Sílabo … Página X de Y", la hora suelta (p. ej. "14:28") y los encabezados de tabla repetidos
  ("Sesión - fecha | Actividades con el docente | Horas | …"); une las celdas partidas.
- Las columnas de la tabla de sesiones del sílabo están en este orden:
  **Docente | Horas | Práctico-experimentales | Horas | Trabajo autónomo | Horas | Contenidos.**
  Las horas suelen aparecer sueltas o desplazadas ("7.0 6.0 5.0"); asígnalas **por columna**:
  1.ª = docente, 2.ª = práctico-experimental, 3.ª = autónomo.
- Cada sesión puede traer "Otras actividades con el docente (X h): …"; ese texto a veces queda
  intercalado con las horas o con el texto de otra columna. Sepáralo bien.
- Algunas tablas de sesiones traen **columnas vacías extra**: ubica cada dato por el **encabezado** de su
  columna, nunca contando posiciones.
- La celda de sesión puede traer un **rango** ("Sesión 1 08/12/2026 al 14/12/2026") o **una sola fecha**
  ("Sesión 1 06/10/2026"); ambas son válidas.
- Hay sesiones con **0.0 h** y sin actividad práctica o autónoma (p. ej. un examen): cópialas tal cual.
- El número de sesiones **varía por momento** (2, 3, 4, 6…). Cuenta "Sesión N" en el sílabo.
- El texto completo de cada RA está en la tabla "Resultados de aprendizaje y evidencias" (sección III).
- Si el **PIS** viene en blanco en el sílabo, no lo inventes: **quita** el bloque PIS de la página y avísalo.
- Hay obras **sin URL ni DOI** (libros impresos): cítalas igual, **sin** enlace "Acceder". Los autores
  pueden tener apellidos compuestos ("Romero Gómez, F.") o venir separados por ";".
- Los títulos de momento pueden venir en MAYÚSCULAS: cópialos literal.
- La fila "Total" de cada momento da: docente | práctico-exp. | autónomo. Úsala para validar.
- En la bibliografía las URL/DOI se parten ("https:" + "//…" o "…softx." + "2025.102072"):
  vuelve a unirlas sin espacios.
- **Copia literal**: prohibido parafrasear, resumir o "mejorar" textos del sílabo.

## MODELO DE LA PÁGINA "MOMENTO N" (bloques del ANEXO A, en orden)
1. **Botón "Inicio del curso"** → conserva su estilo y escribe sus enlaces con el curso del docente:
   `href="https://HOST/courses/ID_CURSO/pages/inicio"` y
   `data-api-endpoint="https://HOST/api/v1/courses/ID_CURSO/pages/inicio"`.
   (Si la página de inicio del curso tiene otro nombre, el script lo corrige al publicar.)
2. **Encabezado**: `Momento N: <título del sílabo>` + "Fecha Inicio: …" + "Fecha Fin: …"
   (respeta el anidamiento de `<span>`). Filas: "Resultado(s) de aprendizaje (RA)" y "Propósito del momento".
3. **Tabla de sesiones**: encabezado "Evidencias de desempeño (producto esperado): <evidencia>" y columnas
   **Sesión | Actividades en contacto con el docente | Actividades de trabajo autónomo |
   Actividades práctico-experimentales | Contenidos | Enlaces**.
4. **`<details>` Rúbrica**: fila con la evidencia del momento + tabla Indicador × Receptivo |
   Resolutivo | Reflexivo | Crítico | Cocreativo.
5. **PIS**: título en negrita + aporte del PF al PIS.
6. **Bibliografía y recursos del momento**: básica y complementaria, numeradas, con enlace "Acceder".

## REGLAS DE MAPEO (sílabo → plantilla)
Clasifica cada campo como **LITERAL** (copiado del sílabo), **PROPUESTO** (redactado por ti
porque el sílabo no lo trae) o **VACÍO** (marcador para el docente).

| Campo de la plantilla | Origen en el sílabo | Tipo | Regla |
|---|---|---|---|
| Título | IV · título del Momento N | LITERAL | `Momento N: <título>` en una sola línea (une el título partido). |
| Fecha Inicio / Fin | IV · "Fecha dd/mm/aaaa al dd/mm/aaaa" | LITERAL | Formato largo sin cero inicial: `8 de diciembre de 2026`. |
| RA | IV · códigos del momento → texto completo en III | LITERAL | Un `<p>` por RA: `RA1: <texto completo>.` (solo se añade el punto final si falta). |
| Propósito del momento | — no existe en el sílabo — | PROPUESTO | 1 oración (máx. ~40 palabras) que empiece con verbo en infinitivo, derivada del título y la evidencia del momento. |
| Evidencia (encabezado de la tabla y fila de la rúbrica) | IV · "Evidencia de desempeño (producto esperado)" | LITERAL | El mismo texto en los dos lugares. |
| Celda Sesión | IV · "Sesión n dd/mm/aaaa [al dd/mm/aaaa]" | LITERAL | `n` + `<span>Fecha: dd/mm/aaaa al dd/mm/aaaa</span>`, o `<span>Fecha: dd/mm/aaaa</span>` si la sesión es de un día. |
| Actividades con el docente | col. Docente + horas + "Otras actividades…" | LITERAL | Texto + `<span>(6.0 h)</span>` + `<p><strong>Otras actividades con el docente (4.0 h):</strong> texto</p>`. |
| Trabajo autónomo | col. **Trabajo autónomo** + horas | LITERAL | Texto + `<span>(5.0 h)</span>`. |
| Práctico-experimentales | col. **Práctico-experimentales** + horas | LITERAL | Texto + `<span>(6.0 h)</span>`. |
| Contenidos | col. Contenidos | LITERAL | Cada contenido en su línea con `&bull; `. |
| Enlaces | — | VACÍO | `(Pegar enlace)`. |
| Rúbrica | IV · rúbrica del momento | LITERAL | Exactamente K filas de indicadores, niveles en el orden Receptivo→Cocreativo. |
| PIS | III · "Proyecto interdisciplinario socioformativo" + "Aporte del PF al PIS" | LITERAL | Igual en todos los momentos. Si el sílabo lo trae vacío, se quita el bloque. |
| Bibliografía básica | VI · básica | LITERAL | Todas las obras en todos los momentos. |
| Bibliografía complementaria | VI · complementaria | Selección revisable | Todas las obras del sílabo en cada momento por defecto. El docente puede desmarcar las que no correspondan; no limitar automáticamente a dos. |

⚠️ **El orden de columnas cambia:** el sílabo trae Docente | Práctico-exp. | Autónomo y la
plantilla trae Docente | **Autónomo** | **Práctico-exp.** Mapea **por significado, nunca por posición**.

**Formato de la bibliografía (estándar institucional):** APA 7; título del libro en
`<em>`; en artículos, nombre de la revista y volumen en `<em>`, número entre paréntesis sin cursiva;
en artículos **se omite la editorial** (MDPI, Elsevier, IEEE…); la URL/DOI no se escribe en el texto:
va como `<a href="URL" target="_blank" rel="noopener">Acceder</a>`. Número en
`<strong style="color: #3a1467;">n.</strong>` (básica) y `<strong style="color: #a6480c;">n.</strong>` (complementaria).
El último `<p>` de cada bloque lleva `margin: 0;`; los demás `margin: 0 0 10px 0;`.

## REGLAS DE MAQUETACIÓN (no romper el diseño)
1. Parte **siempre** del HTML del ANEXO A: conserva cada atributo `style` tal cual
   (colores #3A1467 / #230C3E / #F37121, `clamp()`, anchos 17.4056 % / 12 %, 20 % / 16 %).
   Solo cambias texto, número de filas y los enlaces del curso.
2. **Filas de sesiones:** el anexo trae 2 filas modelo. Genera exactamente N filas:
   - Filas 1 … N-1 → estilo de la **primera** fila del anexo (con `border-bottom: 1px solid #e2e8f0`, sin fondo).
   - Fila N (última) → estilo de la **segunda** fila del anexo (fondo `#fcfafe`, sin `border-bottom`,
     `border-radius: 0px 0px 0px 10px` en la celda Sesión y `0px 0px 10px` en Enlaces).
   - Si N = 1, usa solo el estilo de la última fila.
3. **Filas de la rúbrica:** clona la última fila de indicador del anexo K veces, con el texto
   dentro del `<span>` gris igual que en el anexo.
4. **Bibliografía:** el anexo trae una entrada modelo por bloque; clónala por cada obra.
5. Solo etiquetas que Canvas permite: `table, thead, tbody, tr, th, td, details, summary, p, span,
   strong, em, a`. Nada de `<script>`, `<style>`, `class`, `id` nuevos ni CSS externo.
6. Escapa `&`, `<`, `>` en los textos (`&amp;` en "Bible, P. W., &amp; Moser…"). Puedes usar
   caracteres UTF‑8 o entidades (`&oacute;`), pero sé consistente en todo el archivo.
7. Sin marcadores sobrantes: en el HTML final no puede quedar "(Copiar y pegar del sílabo)",
   "[Día, Mes, Año]", "TÍTULO DEL MOMENTO", "(X.X h)", "dd/mm/aaaa", "[Autor…]", "URL_O_DOI",
   "HOST" ni "ID_CURSO". Solo queda "(Pegar enlace)".
8. El HTML final **no lleva marcas de PROPUESTO** (sin resaltado ni comentarios): esas marcas solo
   van en el informe.

## VALIDACIONES (repórtalas, no las corrijas en silencio)
- Suma de horas por sesión = fila "Total" del momento (docente, práctico-exp., autónomo).
- Suma de los totales de los momentos = horas de la Presentación, comparando **por encabezado**
  (contacto con el docente, práctico-experimental, autónomo).
- Las horas de "Otras actividades con el docente" no suman en los totales: infórmalo como dato.
- Sesiones con fechas que se **solapan**; momentos que se solapan o empiezan el día en que termina el
  anterior; momentos fuera del periodo académico.
- Cada RA citado en un momento existe en III; cada rúbrica tiene 5 niveles por indicador.
- URL/DOI completos y con formato válido.

## FLUJO DE TRABAJO
**FASE 1 — Informe de lectura (primera respuesta, sin HTML):**
1. Ficha: asignatura, código, periodo, docente, nº de momentos, y **HOST e ID_CURSO** que se usarán.
2. Por momento, una tabla: nº | título | fechas | RA | evidencia (resumen de 1 línea) |
   nº de sesiones | horas por sesión (D / A / PE + "otras") | total | nº de indicadores de rúbrica.
3. **Advertencias** (todo lo de VALIDACIONES que falle, con la cita del sílabo).
4. **Textos PROPUESTOS** para revisión: los "Propósito del momento" y el reparto de la
   bibliografía complementaria con su justificación.
5. Contenido del sílabo **sin lugar en la página Momento** (para otras páginas del aula):
   recursos para el aprendizaje y política de IA de cada momento, perfil, competencias,
   metodología, rúbrica del producto final. Solo lístalos.
6. Termina con: *"Escribe GENERAR para producir los HTML, o indícame los cambios."*

**FASE 2 — HTML (cuando yo escriba GENERAR, aplicando mis cambios):**
- Si puedes crear archivos, entrega **`momento-1.html … momento-N.html`** descargables (con esos
  nombres exactos: el script los busca así).
- Si no, entrega **un momento por respuesta**, en un único bloque ` ```html `, completo (desde el
  botón "Inicio del curso" hasta el cierre de la bibliografía), sin `<html>`, `<head>` ni `<body>`,
  indica el nombre del archivo (`momento-N.html`) y espera a que escriba **SIGUIENTE**.
- Debajo de cada HTML, una **lista de control** con ✔/✘: botón "Inicio del curso" con
  `/courses/ID_CURSO/` · título · fechas · RA completos · N filas de sesiones = sílabo · horas por
  columna · K indicadores de rúbrica · PIS · bibliografía con enlaces · 0 marcadores · sin etiquetas prohibidas.
- Al final, recuerda al docente el paso 3 de "Cómo usarlo" (ejecutar `publicar_canvas.ps1` con la URL
  de su curso) y que **no pegue el token en el chat**.

## REGLAS INNEGOCIABLES
1. Copia literal todo lo que trae el sílabo; marca como PROPUESTO todo lo que no trae.
2. Respeta el diseño del ANEXO A: solo cambia contenido, número de filas y enlaces del curso.
3. Mapea las columnas de actividades por significado (Autónomo y Práctico-exp. están invertidas).
4. Reporta las inconsistencias del sílabo; no las corrijas por tu cuenta.
5. No inventes enlaces: la columna Enlaces queda como "(Pegar enlace)".
6. Si algo del PDF es ilegible o ambiguo, dilo en el informe en vez de adivinar.
7. Ningún ID de curso va fijo: todos los enlaces internos usan el `ID_CURSO` de la URL del docente.
8. Nunca pidas, uses ni repitas un token o contraseña. La publicación en Canvas la hace el script
   en el equipo del docente, con respaldo y verificación.

---

## ANEXO A · Plantilla institucional de la página "Momento N"
Reemplaza cada marcador según la tabla de mapeo. `HOST` e `ID_CURSO` salen de la URL del curso.

```html
<table style="width: 100%; max-width: 1000px; margin: 0px auto; border-collapse: separate; height: 95px;">
<tbody>
<tr style="height: 95px;">
<td style="text-align: center; padding: clamp(14px, 3vw, 20px) 0px; height: 95px;"><a data-api-endpoint="https://HOST/api/v1/courses/ID_CURSO/pages/inicio" data-api-returntype="Page" data-course-type="wikiPages" data-published="true" href="https://HOST/courses/ID_CURSO/pages/inicio" style="display: inline-block; text-decoration: none; padding: clamp(8px, 2vw, 12px) clamp(16px, 4vw, 24px); background-color: #3a1467; color: #ffffff; border-radius: 4px; font-family: LatoExtended, 'Source Sans Pro', sans-serif; font-size: clamp(14px, 3vw, 18px); cursor: pointer; border: 1px solid #230c3e;" title="Inicio">Inicio del curso</a></td>
</tr>
</tbody>
</table>
<table style="width: 100%; max-width: 1000px; margin: 0px auto 28px; border-collapse: separate; table-layout: fixed; border-radius: 10px; font-family: Verdana, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #2d3748; line-height: 1.65; border: 1px solid #cbd5e0;">
<thead>
<tr>
<th scope="col" style="background: linear-gradient(135deg, #3A1467 0%, #230C3E 100%); color: #ffffff; text-align: left; vertical-align: top; padding: clamp(18px, 3vw, 28px) clamp(14px, 3vw, 24px); border-bottom: 5px solid #F37121; border-radius: 10px 10px 0 0; font-size: clamp(17px, 4.2vw, 25px); line-height: 1.3;">T&Iacute;TULO DEL MOMENTO<span style="display: block; margin-top: 10px; color: rgba(255, 255, 255, 0.75); font-size: clamp(11.5px, 2.2vw, 13px); line-height: 1.5;">Fecha Inicio: [D&iacute;a, Mes, A&ntilde;o]&nbsp;<span style="display: block; margin-top: 10px; color: rgba(255, 255, 255, 0.75); font-size: clamp(11.5px, 2.2vw, 13px); line-height: 1.5;">Fecha Fin: [D&iacute;a, Mes, A&ntilde;o]</span></span></th>
</tr>
</thead>
<tbody>
<tr>
<th scope="row" style="background: #F7F3FB; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; font-size: clamp(12px, 2.3vw, 13.5px); line-height: 1.45;">Resultado(s) de aprendizaje (RA)</th>
</tr>
<tr>
<td style="vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; font-size: clamp(13px, 2.4vw, 14.5px); line-height: 1.6;">
<p>RAn: (Copiar y pegar del s&iacute;labo)</p>
</td>
</tr>
<tr>
<th scope="row" style="background: #F7F3FB; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; font-size: clamp(12px, 2.3vw, 13.5px); line-height: 1.45;">Prop&oacute;sito del momento</th>
</tr>
<tr>
<td style="background: #FCFAFE; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-radius: 0 0 10px 10px; font-size: clamp(13px, 2.4vw, 14.5px); line-height: 1.6;">
<p>(Copiar y pegar del s&iacute;labo)</p>
</td>
</tr>
</tbody>
</table>
<table style="width: 100%; max-width: 1000px; margin: 0px auto 28px; border-collapse: separate; table-layout: fixed; border-radius: 10px; font-family: Verdana, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #2d3748; line-height: 1.65; border: 1px solid #cbd5e0;">
<thead>
<tr>
<th colspan="6" scope="col" style="background: linear-gradient(135deg, #3a1467 0%, #230c3e 100%); color: #ffffff; text-align: left; vertical-align: top; padding: clamp(14px, 2.5vw, 20px) clamp(10px, 2.5vw, 20px); border-bottom: 4px solid #f37121; border-radius: 10px 10px 0px 0px; font-size: clamp(14px, 2.8vw, 17px); line-height: 1.35; width: 99.0281%;">Evidencias de desempe&ntilde;o (producto esperado):&nbsp;<span style="display: block; margin-top: 10px; color: rgba(255, 255, 255, 0.75); font-size: clamp(11.5px, 2.2vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 6px; color: #ffffff; font-size: clamp(11.5px, 2.2vw, 13px); line-height: 1.5;"><span style="color: rgba(255, 255, 255, 0.75);">(Copiar y pegar del s&iacute;labo)</span></span></span></th>
</tr>
<tr>
<th scope="col" style="width: 17.4056%; background: #3a1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #4e2a80; border-bottom: 2px solid #230c3e; font-size: clamp(9.5px, 2.1vw, 13.5px); line-height: 1.35;">Sesi&oacute;n</th>
<th scope="col" style="width: 17.4056%; background: #3a1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #4e2a80; border-bottom: 2px solid #230c3e; font-size: clamp(9.5px, 2.1vw, 13.5px); line-height: 1.35;">Actividades en contacto con el docente</th>
<th scope="col" style="width: 17.4056%; background: #3a1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #4e2a80; border-bottom: 2px solid #230c3e; font-size: clamp(9.5px, 2.1vw, 13.5px); line-height: 1.35;">Actividades de trabajo aut&oacute;nomo</th>
<th scope="col" style="width: 17.4056%; background: #3a1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #4e2a80; border-bottom: 2px solid #230c3e; font-size: clamp(9.5px, 2.1vw, 13.5px); line-height: 1.35;">Actividades pr&aacute;ctico-experimentales</th>
<th scope="col" style="width: 17.4056%; background: #3a1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #4e2a80; border-bottom: 2px solid #230c3e; font-size: clamp(9.5px, 2.1vw, 13.5px); line-height: 1.35;">Contenidos</th>
<th scope="col" style="width: 12%; background: #3a1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 16px); border-bottom: 2px solid #230c3e; font-size: clamp(9.5px, 2.1vw, 13.5px); line-height: 1.35;">Enlaces</th>
</tr>
</thead>
<tbody>
<tr>
<th scope="row" style="width: 17.4056%; background: #f7f3fb; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e4d9f0; border-bottom: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 15px); line-height: 1.35;">
<p>n<span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(10px, 2vw, 13px); line-height: 1.5;">Fecha: dd/mm/aaaa al dd/mm/aaaa</span></p>
</th>
<td style="width: 17.4056%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Copiar y pegar del s&iacute;labo)<span style="display: block; margin-top: 6px; color: #4a5568; font-size: clamp(10px, 2vw, 12px);">(X.X h)</span>
<p style="margin: 10px 0 0 0;"><strong>Otras actividades con el docente (X.X h):</strong> (Copiar y pegar del s&iacute;labo)</p>
</td>
<td style="width: 17.4056%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Copiar y pegar del s&iacute;labo)<span style="display: block; margin-top: 6px; color: #4a5568; font-size: clamp(10px, 2vw, 12px);">(X.X h)</span></td>
<td style="width: 17.4056%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Copiar y pegar del s&iacute;labo)<span style="display: block; margin-top: 6px; color: #4a5568; font-size: clamp(10px, 2vw, 12px);">(X.X h)</span></td>
<td style="width: 17.4056%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">&bull; (Copiar y pegar del s&iacute;labo)</td>
<td style="width: 12%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-bottom: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Pegar enlace)</td>
</tr>
<tr>
<th scope="row" style="width: 17.4056%; background: #f7f3fb; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e4d9f0; border-radius: 0px 0px 0px 10px; font-size: clamp(11px, 2.2vw, 15px); line-height: 1.35;">
<p>n<span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(10px, 2vw, 13px); line-height: 1.5;">Fecha: dd/mm/aaaa al dd/mm/aaaa</span></p>
</th>
<td style="width: 17.4056%; background: #fcfafe; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Copiar y pegar del s&iacute;labo)<span style="display: block; margin-top: 6px; color: #4a5568; font-size: clamp(10px, 2vw, 12px);">(X.X h)</span>
<p style="margin: 10px 0 0 0;"><strong>Otras actividades con el docente (X.X h):</strong> (Copiar y pegar del s&iacute;labo)</p>
</td>
<td style="width: 17.4056%; background: #fcfafe; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Copiar y pegar del s&iacute;labo)<span style="display: block; margin-top: 6px; color: #4a5568; font-size: clamp(10px, 2vw, 12px);">(X.X h)</span></td>
<td style="width: 17.4056%; background: #fcfafe; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Copiar y pegar del s&iacute;labo)<span style="display: block; margin-top: 6px; color: #4a5568; font-size: clamp(10px, 2vw, 12px);">(X.X h)</span></td>
<td style="width: 17.4056%; background: #fcfafe; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-right: 1px solid #e2e8f0; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">&bull; (Copiar y pegar del s&iacute;labo)</td>
<td style="width: 12%; background: #fcfafe; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 16px); border-radius: 0px 0px 10px; font-size: clamp(11px, 2.2vw, 13.5px); line-height: 1.5;">(Pegar enlace)</td>
</tr>
</tbody>
</table>
<details style="max-width: 1000px; margin: 0 auto 28px auto; font-family: Verdana, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<summary style="cursor: pointer; background: #f7f3fb; color: #230c3e; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-width: 1px 1px 3px; border-style: solid; border-color: #cbd5e0 #cbd5e0 #f37121; border-radius: 10px; font-size: clamp(15px, 3vw, 19px); line-height: 1.3;"><span style="vertical-align: middle;">R&uacute;brica de evaluaci&oacute;n de la evidencia de desempe&ntilde;o del Momento</span> <span style="font-size: clamp(11px, 2vw, 12px); color: #5a6472; vertical-align: middle;">(clic para mostrar u ocultar)</span></summary>
<table style="width: 100%; margin: 14px 0px 0px; border-collapse: separate; table-layout: fixed; border-radius: 10px; color: #2d3748; line-height: 1.65; border: 1px solid #cbd5e0;">
<tbody>
<tr>
<th colspan="6" scope="row" style="background: #F7F3FB; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; border-radius: 10px 10px 0 0; font-size: clamp(12px, 2.3vw, 13.5px); line-height: 1.45;">Evidencia de desempe&ntilde;o del momento (producto esperado del momento)</th>
</tr>
<tr>
<td colspan="6" style="vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; font-size: clamp(13px, 2.4vw, 14.5px); line-height: 1.6;">(Copiar y pegar del s&iacute;labo)</td>
</tr>
<tr>
<th scope="col" style="width: 20%; background: #3A1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #4E2A80; border-top: 2px solid #230C3E; border-bottom: 2px solid #230C3E; font-size: clamp(9px, 2vw, 13px); line-height: 1.35;">Indicador</th>
<th scope="col" style="width: 16%; background: #3A1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #4E2A80; border-top: 2px solid #230C3E; border-bottom: 2px solid #230C3E; font-size: clamp(9px, 2vw, 13px); line-height: 1.35;">Receptivo</th>
<th scope="col" style="width: 16%; background: #3A1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #4E2A80; border-top: 2px solid #230C3E; border-bottom: 2px solid #230C3E; font-size: clamp(9px, 2vw, 13px); line-height: 1.35;">Resolutivo</th>
<th scope="col" style="width: 16%; background: #3A1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #4E2A80; border-top: 2px solid #230C3E; border-bottom: 2px solid #230C3E; font-size: clamp(9px, 2vw, 13px); line-height: 1.35;">Reflexivo</th>
<th scope="col" style="width: 16%; background: #3A1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #4E2A80; border-top: 2px solid #230C3E; border-bottom: 2px solid #230C3E; font-size: clamp(9px, 2vw, 13px); line-height: 1.35;">Cr&iacute;tico</th>
<th scope="col" style="width: 16%; background: #3A1467; color: #ffffff; text-align: left; vertical-align: middle; padding: clamp(9px, 2vw, 14px) clamp(4px, 1.4vw, 14px); border-top: 2px solid #230C3E; border-bottom: 2px solid #230C3E; font-size: clamp(9px, 2vw, 13px); line-height: 1.35;">Cocreativo</th>
</tr>
<tr>
<th scope="row" style="width: 20%; background: #F7F3FB; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #E4D9F0; border-radius: 0 0 0 10px; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></th>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #E2E8F0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #E2E8F0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #E2E8F0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #E2E8F0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-radius: 0 0 10px 0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
</tr>
<tr>
<th scope="row" style="width: 20%; background: #f7f3fb; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e4d9f0; border-radius: 0px 0px 0px 10px; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></th>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-radius: 0px 0px 10px; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
</tr>
<tr>
<th scope="row" style="width: 20%; background: #f7f3fb; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e4d9f0; border-radius: 0px 0px 0px 10px; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></th>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-radius: 0px 0px 10px; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
</tr>
<tr>
<th scope="row" style="width: 20%; background: #f7f3fb; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e4d9f0; border-radius: 0px 0px 0px 10px; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></th>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-right: 1px solid #e2e8f0; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
<td style="width: 16%; vertical-align: top; padding: clamp(12px, 2.2vw, 16px) clamp(4px, 1.4vw, 14px); border-radius: 0px 0px 10px; font-size: clamp(10.5px, 2.1vw, 13px); line-height: 1.5;"><span style="display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;">(Copiar y pegar del s&iacute;labo)</span></td>
</tr>
</tbody>
</table>
</details>
<table style="width: 100%; max-width: 1000px; margin: 0px auto 28px; border-collapse: separate; table-layout: fixed; border-radius: 10px; font-family: Verdana, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #2d3748; line-height: 1.65; border: 1px solid #cbd5e0;">
<thead>
<tr>
<th scope="col" style="background: linear-gradient(135deg, #3A1467 0%, #230C3E 100%); color: #ffffff; text-align: left; vertical-align: top; padding: clamp(14px, 2.5vw, 20px) clamp(10px, 2.5vw, 20px); border-bottom: 4px solid #F37121; border-radius: 10px 10px 0 0; font-size: clamp(14px, 2.8vw, 17px); line-height: 1.35;">Proyecto Interdisciplinario Socioformativo (PIS)</th>
</tr>
</thead>
<tbody>
<tr>
<td style="background: #FCFAFE; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-radius: 0 0 10px 10px; font-size: clamp(13px, 2.4vw, 14.5px); line-height: 1.6;">
<p style="margin: 0 0 8px 0;"><strong style="color: #3a1467;">(Copiar y pegar del s&iacute;labo)</strong></p>
<p style="margin: 0;">(Copiar y pegar del s&iacute;labo)</p>
</td>
</tr>
</tbody>
</table>
<table style="width: 100%; max-width: 1000px; margin: 0px auto 28px; border-collapse: separate; table-layout: fixed; border-radius: 10px; font-family: Verdana, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #2d3748; line-height: 1.65; border: 1px solid #cbd5e0;">
<thead>
<tr>
<th scope="col" style="background: linear-gradient(135deg, #3A1467 0%, #230C3E 100%); color: #ffffff; text-align: left; vertical-align: top; padding: clamp(14px, 2.5vw, 20px) clamp(10px, 2.5vw, 20px); border-bottom: 4px solid #F37121; border-radius: 10px 10px 0 0; font-size: clamp(14px, 2.8vw, 17px); line-height: 1.35;">Bibliograf&iacute;a y recursos del momento</th>
</tr>
</thead>
<tbody>
<tr>
<th scope="row" style="background: #F7F3FB; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; font-size: clamp(12px, 2.3vw, 13.5px); line-height: 1.45;">Bibliograf&iacute;a b&aacute;sica</th>
</tr>
<tr>
<td style="vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; font-size: clamp(13px, 2.4vw, 14.5px); line-height: 1.6;">
<p style="margin: 0 0 10px 0;"><strong style="color: #3a1467;">1.</strong> [Autor, A. A. (A&ntilde;o). T&iacute;tulo en APA 7.] <a href="URL_O_DOI" rel="noopener" target="_blank">Acceder</a></p>

<p style="margin: 0;"><strong style="color: #3a1467;">3.</strong> [Autor, A. A. (A&ntilde;o). T&iacute;tulo en APA 7.] <a href="URL_O_DOI" rel="noopener" target="_blank">Acceder</a></p>
</td>
</tr>
<tr>
<th scope="row" style="background: #F7F3FB; color: #3a1467; text-align: left; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-bottom: 1px solid #E2E8F0; font-size: clamp(12px, 2.3vw, 13.5px); line-height: 1.45;">Bibliograf&iacute;a complementaria</th>
</tr>
<tr>
<td style="background: #FCFAFE; vertical-align: top; padding: clamp(12px, 2.5vw, 18px) clamp(10px, 2.5vw, 20px); border-radius: 0 0 10px 10px; font-size: clamp(13px, 2.4vw, 14.5px); line-height: 1.6;">
<p style="margin: 0 0 10px 0;"><strong style="color: #a6480c;">1.</strong> [Autor, A. A. (A&ntilde;o). T&iacute;tulo en APA 7.] <a href="URL_O_DOI" rel="noopener" target="_blank">Acceder</a></p>
<p style="margin: 0;"><strong style="color: #a6480c;">2.</strong> [Autor, A. A. (A&ntilde;o). T&iacute;tulo en APA 7.] <a href="URL_O_DOI" rel="noopener" target="_blank">Acceder</a></p>
</td>
</tr>
</tbody>
</table>
```
