# Pruebas de los HTML "Momento N"

Comprueban que `html/momento-*.html` cumplen las reglas de `PROMPT_MAESTRO_Silabo_a_Canvas.md`
comparándolos con el sílabo PDF, que se lee **de forma independiente** (`silabo_parser.py`, no usa los
datos del generador).

## Ejecutar
```bash
python -m pip install pdfplumber beautifulsoup4 pytest
python -m pytest tests -v
```
Variables opcionales (para otro curso o sílabo):
- `SILABO_PDF` — ruta del PDF (por defecto, el único `.pdf` de la carpeta).
- `CURSO_URL` — URL de la página Inicio del curso (por defecto el curso 36283).
- `HTML_DIR` — carpeta de los HTML (por defecto `html/`).

## Qué se verifica (27 pruebas por cada momento, 99 en total)
| Regla del prompt | Prueba |
|---|---|
| Bloques y orden de la plantilla | `test_bloques_en_orden`, `test_columnas_en_orden_de_plantilla` |
| Solo etiquetas permitidas, bien cerradas, `&` escapado | `test_solo_etiquetas_permitidas`, `test_etiquetas_balanceadas`, `test_ampersands_escapados` |
| Sin marcadores ni marcas de PROPUESTO | `test_sin_marcadores` |
| Botón Inicio y enlaces con el ID del curso del docente | `test_boton_inicio_apunta_al_curso`, `test_enlaces_internos_mismo_curso` |
| Título, fechas largas, RA con texto completo | `test_titulo`, `test_fechas_formato_largo`, `test_ra_texto_completo` |
| Propósito: 1 oración, infinitivo, ≤45 palabras | `test_proposito_propuesto` |
| Evidencia literal en tabla y rúbrica | `test_evidencia_en_encabezado_y_rubrica`, `test_rubrica_evidencia_del_silabo_coincide` |
| N sesiones, texto literal, columnas por significado, horas | `test_numero_de_sesiones`, `test_sesiones_contenido_literal_y_mapeo_por_significado`, `test_horas_suman_totales` |
| Estilo de filas intermedias y última | `test_estilo_filas_intermedias_y_ultima` |
| Rúbrica: K indicadores × 5 niveles, literal | `test_rubrica_niveles_e_indicadores` |
| PIS literal | `test_pis` |
| Bibliografía: básica completa, 2 complementarias, APA sin editorial, "Acceder" | `test_bibliografia_*`, `test_reparto_complementaria_cubre_todas` |
| Estilos idénticos a la plantilla aprobada | `test_estilos_son_los_de_la_plantilla`, `test_momento1_igual_al_aprobado` |

`fixtures/momento1_aprobado.html` es la página Momento 1 aprobada que sirve de plantilla de referencia.
