# -*- coding: utf-8 -*-
"""PDF del sílabo → fragmentos de texto para la BD vectorial.

Cada fragmento es un bloque lógico (cabecera de un momento, tabla de sesiones, rúbrica, RA, PIS,
bibliografía…) escrito como filas de tabla "| a | b |". La segmentación solo marca DÓNDE está cada
cosa; la lectura de los campos la hace el modelo.
"""
import re

import pdfplumber

MAX_CHARS = 6000   # ~1700 tokens por fragmento


def _limpia(c):
    return re.sub(r'\s+', ' ', (c or '').replace('\n', ' ')).strip()


def _fila(r):
    celdas = [_limpia(c) for c in r]
    while celdas and not celdas[-1]:
        celdas.pop()
    return '| ' + ' | '.join(celdas) + ' |' if any(celdas) else ''


ETIQUETAS = (('cab', 'SESIÓN'), ('doc', 'ACTIVIDADES CON EL DOCENTE'), ('hd', 'HORAS DOCENTE'),
             ('otras_h', 'OTRAS ACTIVIDADES (HORAS)'), ('otras', 'OTRAS ACTIVIDADES'),
             ('pe', 'ACTIVIDADES PRÁCTICO-EXPERIMENTALES'), ('hpe', 'HORAS PRÁCTICO'),
             ('aut', 'ACTIVIDADES DE TRABAJO AUTÓNOMO'), ('ha', 'HORAS AUTÓNOMO'), ('cont', 'CONTENIDOS'))
ETIQUETAS_PIE = (('hd', 'TOTAL DOCENTE'), ('hpe', 'TOTAL PRÁCTICO'), ('ha', 'TOTAL AUTÓNOMO'),
                 ('recursos', 'RECURSOS PARA EL APRENDIZAJE'), ('politica', 'POLÍTICA DE IA'))


def registros_sesiones(pdf_path):
    """{momento: [registro por sesión]} con cada celda etiquetada según el ENCABEZADO de su columna
    (las tablas pueden traer columnas vacías extra), las filas que continúan en la página siguiente
    ya unidas y "Otras actividades con el docente (X h): …" ya separado. Es la entrada de Qwen para
    leer sesiones: no tiene que adivinar posiciones ni partir textos."""
    from core.silabo import _split_otras
    ses, _ = _recorrer(pdf_path)
    out = {}
    for m, lista in ses.items():
        for s in lista:
            s['doc'], s['otras_h'], s['otras'] = _split_otras(s['doc'])
        out[m] = ['\n'.join(f'{etq}: {s[k] or ""}' for k, etq in ETIQUETAS) for s in lista]
    return out


def pie_momentos(pdf_path):
    """{momento: registro con la fila Total, los recursos y la política de IA, etiquetados}."""
    _, pies = _recorrer(pdf_path)
    return {m: '\n'.join(f'{etq}: {p.get(k, "")}' for k, etq in ETIQUETAS_PIE) for m, p in pies.items()}


def _recorrer(pdf_path):
    from core.silabo import _columnas, _valores, _join
    res, pies, momento, cols, ses, en_tabla = {}, {}, None, None, None, False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for t in page.extract_tables():
                for r in t:
                    r = [_limpia(c) for c in r]
                    r0 = r[0] if r else ''
                    m = re.fullmatch(r'Momento (\d+)', r0)
                    if m:
                        momento, en_tabla, ses = int(m.group(1)), False, None
                        continue
                    if r0.startswith('Rúbrica de la evidencia del desempeño central'):
                        momento, en_tabla = None, False
                    if momento is None:
                        continue
                    if r0.startswith('Sesión - fecha'):
                        cols, en_tabla = _columnas(r), True
                        continue
                    if r0.startswith('Recursos para') or r0.startswith('Política de'):
                        clave = 'recursos' if r0.startswith('Recursos') else 'politica'
                        pies.setdefault(momento, {})[clave] = next((c for c in r[1:] if c), '')
                        en_tabla, ses = False, None
                        continue
                    if not en_tabla:
                        continue
                    if r0 == 'Total':
                        v = _valores(r, cols)
                        pies.setdefault(momento, {}).update(hd=v['hd'], hpe=v['hpe'], ha=v['ha'])
                        en_tabla, ses = False, None
                        continue
                    v = _valores(r, cols)
                    if r0.startswith('Sesión '):
                        ses = dict(cab=r0, **v)
                        res.setdefault(momento, []).append(ses)
                    elif ses is not None:
                        ses['cab'] = _join(ses['cab'], r0)
                        for k in ('doc', 'pe', 'aut', 'cont'):
                            ses[k] = _join(ses[k], v[k])
                        for k in ('hd', 'hpe', 'ha'):
                            ses[k] = ses[k] or v[k]
    return res, pies


def fragmentos(pdf_path):
    """Devuelve una lista de dict(texto, pagina, seccion, momento, bloque)."""
    out, cur = [], None
    momento, bloque, seccion = None, 'general', 'I-III'

    def cerrar():
        nonlocal cur
        if cur and cur['texto'].strip():
            out.append(cur)
        cur = None

    def abrir(pag):
        nonlocal cur
        cur = dict(texto='', pagina=pag, seccion=seccion, momento=momento, bloque=bloque)

    with pdfplumber.open(pdf_path) as pdf:
        for pag, page in enumerate(pdf.pages, 1):
            texto_pag = page.extract_text() or ''
            if 'V. EVALUACIÓN' in texto_pag:
                pass
            for t in page.extract_tables():
                for r in t:
                    r0 = _limpia(r[0]) if r else ''
                    nuevo_bloque = None
                    m = re.fullmatch(r'Momento (\d+)', r0)
                    if m:
                        momento, seccion, nuevo_bloque = int(m.group(1)), 'IV', 'cabecera'
                    elif r0.startswith('Sesión - fecha') and bloque != 'sesiones':
                        nuevo_bloque = 'sesiones'
                    elif r0.startswith('Rúbrica de evaluación') and momento:
                        nuevo_bloque = 'rubrica'
                    elif r0.startswith('Rúbrica de la evidencia del desempeño central'):
                        momento, seccion, nuevo_bloque = None, 'V', 'rubrica_final'
                    elif r0.startswith('Resultados de aprendizaje y evidencias'):
                        nuevo_bloque = 'ra'
                    elif r0 == 'Proyecto interdisciplinario socioformativo':
                        nuevo_bloque = 'pis'
                    elif r0.startswith('Metodología activa') or r0.startswith('Problema del territorio'):
                        nuevo_bloque = 'general'
                    elif r0.startswith('Créditos') or r0.startswith('Aprendizaje en contacto'):
                        nuevo_bloque = 'presentacion'
                    if nuevo_bloque and nuevo_bloque != bloque or m:
                        bloque = nuevo_bloque or bloque
                        cerrar()
                    linea = _fila(r)
                    if not linea:
                        continue
                    if cur is None:
                        abrir(pag)
                    if len(cur['texto']) + len(linea) > MAX_CHARS:
                        cerrar(); abrir(pag)
                    cur['texto'] += linea + '\n'
        textos = [p.extract_text() or '' for p in pdf.pages]
    cerrar()
    # la bibliografía no está en tablas: texto corrido desde "Bibliografía básica" hasta "VII.", aunque cruce páginas
    todo = '\n'.join(l for l in '\n'.join(textos).split('\n')
                     if not re.match(r'^Sílabo .* Página \d+ de \d+', l) and not re.fullmatch(r'\d\d:\d\d', l.strip()))
    i = todo.rfind('Bibliografía básica')
    if i >= 0:
        bib = todo[i:].split('VII. FIRMAS', 1)[0].strip()
        pag = next((k for k, t in enumerate(textos, 1) if 'Bibliografía básica' in t), None)
        out.append(dict(texto=bib, pagina=pag, seccion='VI', momento=None, bloque='bibliografia'))
    for i, f in enumerate(out):
        f['id'] = i
    return out
