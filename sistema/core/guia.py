# -*- coding: utf-8 -*-
"""Lector de la Guía práctica institucional (PDF, formato FOR-GPFM) → lista de guías.

Lee las tablas con pdfplumber: cada rótulo ("Título de la práctica", "Procedimiento"…) va en una fila
y su valor en la siguiente; los datos de cabecera (fechas, N°, horas, momento) van en la misma fila.
Un PDF puede traer varias guías: cada "GUÍA PRACTICA … Pág.1" abre una nueva.
"""
import re
from datetime import date

import pdfplumber


class FormatoNoReconocido(ValueError):
    """El PDF no tiene la estructura de la guía práctica institucional."""


def _clean(c):
    return re.sub(r'\s+', ' ', (c or '').replace('\n', ' ')).strip()


# rótulo de bloque → clave (el valor viene en la fila siguiente)
_BLOQUES = {
    'título de la práctica': 'titulo', 'procedimiento': 'procedimiento', 'objetivos': 'objetivos',
    'fundamento teórico': 'fundamento', 'resultados de aprendizaje': 'ra', 'resultados': 'resultados',
    'laboratorios': 'laboratorios', 'equipos': 'equipos', 'otros': 'otros',
}
# rótulo en línea → clave (el valor es la siguiente celda no vacía de la misma fila)
_EN_FILA = {
    'fecha inicio de práctica': 'inicio_txt', 'fecha fin de práctica': 'fin_txt', 'guia n°': 'n_txt',
    'guía n°': 'n_txt', 'proyecto formativo': 'proyecto', 'nivel': 'nivel', 'n° horas': 'horas',
    'momento': 'momento', 'modalidad': 'modalidad', 'carrera': 'carrera', 'facultad': 'facultad',
}


def leer(origen):
    """`origen`: ruta o archivo binario. Devuelve lista de guías (dict)."""
    try:
        with pdfplumber.open(origen) as pdf:
            paginas = [[[c or '' for c in r] for t in p.extract_tables() for r in t] for p in pdf.pages]
    except Exception as e:
        raise FormatoNoReconocido(f'No se pudo abrir el PDF de la guía: {e}') from e

    guias, cur, pendiente = [], None, None
    for filas in paginas:
        for crudo in filas:
            r = [_clean(c) for c in crudo]
            no_vacias = [c for c in r if c]
            if not no_vacias:
                continue
            if any(re.match(r'Pág\.\s*1$', c) for c in r):            # primera página de una guía
                cur = dict(_crudo={}); guias.append(cur); pendiente = None
                continue
            if cur is None or 'GUÍA PRACTICA' in no_vacias or any(c.startswith('Código Formato') for c in r):
                continue
            etq = no_vacias[0].lower()
            if len(no_vacias) == 1 and etq in _BLOQUES:
                pendiente = _BLOQUES[etq]
                continue
            if pendiente:
                # se conservan los saltos de línea originales (pasos del procedimiento)
                cur['_crudo'][pendiente] = (cur['_crudo'].get(pendiente, '') + '\n' + '\n'.join(c for c in crudo if c)).strip()
                pendiente = None
                continue
            for i, c in enumerate(r):
                k = _EN_FILA.get(c.lower())
                if k:
                    cur[k] = next((v for v in r[i + 1:] if v and v.lower() not in _EN_FILA), '')
            if etq.startswith('elaborado por') or etq.startswith('coordinador'):
                continue

    if not guias:
        raise FormatoNoReconocido('No reconozco el formato de la guía práctica (FOR-GPFM). '
                                  '¿Es el PDF que genera el sistema académico?')
    return [_normalizar(g) for g in guias]


def _fecha(txt):
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', txt or '')
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    return date(y + 2000 if y < 100 else y, mth, d)


def _pasos(txt):
    t = _clean(txt)
    partes = re.split(r'(?:^|\s)(\d{1,2})\.\s+(?=\S)', t)
    pasos = [p.strip() for p in partes[2::2] if p.strip()]
    return pasos or ([t] if t else [])


def _resultados(txt):
    t = _clean(txt)
    esperado, concl = t, ''
    m = re.search(r'CONCLUSIONES?\s*:\s*', t, re.I)
    if m:
        esperado, concl = t[:m.start()], t[m.end():]
    esperado = re.sub(r'^RESULTADO\s+ESPERADO\s*:\s*', '', esperado.strip(), flags=re.I)
    return esperado.strip(), concl.strip()


_SIGLAS = {'IA', 'PIS', 'RA', 'API', 'SQL', 'HTML', 'CSS', 'UML', 'TIC', 'TICS', 'PAE', 'BD', 'ERP', 'CRM', 'IOT',
           'PDF', 'URL', 'JSON', 'XML', 'HTTP', 'CPU', 'RAM', 'GPS', 'ONU', 'ODS', 'NIIF', 'IVA', 'SRI', 'IESS', 'POO'}
_PROPIOS = {'python': 'Python', 'java': 'Java', 'excel': 'Excel', 'canvas': 'Canvas', 'github': 'GitHub',
            'ecuador': 'Ecuador', 'quito': 'Quito', 'ambato': 'Ambato', 'javascript': 'JavaScript', 'git': 'Git'}


def tipo_oracion(txt):
    """'IMPLEMENTAR UN ÁRBOL…' → 'Implementar un árbol…' (respeta siglas y algunos nombres propios).
    Si el texto no está todo en mayúsculas, se deja tal cual."""
    t = _clean(txt)
    letras = [c for c in t if c.isalpha()]
    if not letras or sum(c.isupper() for c in letras) / len(letras) < 0.8:
        return t

    def palabra(m):
        w = m.group(0)
        if w.upper() in _SIGLAS or any(ch.isdigit() for ch in w):
            return w.upper()
        return _PROPIOS.get(w.lower(), w.lower())
    t = re.sub(r'[^\W_]+', palabra, t)
    return re.sub(r'(^|[.!?:]\s+)([a-záéíóúñ])', lambda m: m.group(1) + m.group(2).upper(), t)


def _normalizar(g):
    c = g.pop('_crudo')
    n = re.search(r'\d+', g.get('n_txt', ''))
    esperado, concl = _resultados(c.get('resultados', ''))
    ra = _clean(c.get('ra', ''))
    out = dict(
        n=int(n.group()) if n else None,
        titulo=tipo_oracion(c.get('titulo', '')),
        titulo_original=_clean(c.get('titulo', '')),
        inicio=_fecha(g.get('inicio_txt')), fin=_fecha(g.get('fin_txt')),
        horas=g.get('horas', ''), momento=_clean(g.get('momento', '')),
        proyecto=g.get('proyecto', ''), nivel=g.get('nivel', ''), modalidad=g.get('modalidad', ''),
        carrera=g.get('carrera', ''),
        procedimiento=[tipo_oracion(p) for p in _pasos(c.get('procedimiento', ''))],
        objetivos=tipo_oracion(c.get('objetivos', '')),
        fundamento=tipo_oracion(c.get('fundamento', '')),
        ra='' if ra.lower() in ('', 'null', 'none', 'n/a') else ra,
        resultado_esperado=tipo_oracion(esperado), conclusiones=tipo_oracion(concl),
        recursos={k: tipo_oracion(c.get(k, '')) for k in ('laboratorios', 'equipos', 'otros')
                  if _clean(c.get(k, '')) and _clean(c.get(k, '')).lower() not in ('no aplica', 'null')},
    )
    faltan = [k for k in ('n', 'titulo', 'inicio', 'fin') if not out[k]]
    if not out['procedimiento']:
        faltan.append('procedimiento')
    out['faltan'] = faltan
    return out
