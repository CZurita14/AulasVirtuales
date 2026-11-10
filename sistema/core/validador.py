# -*- coding: utf-8 -*-
"""Validaciones del sílabo. Devuelve ADVERTENCIAS: el sistema nunca corrige el sílabo por su cuenta."""
import re
from datetime import date, datetime


def _f(s):
    try:
        return datetime.strptime(s, '%d/%m/%Y').date()
    except (ValueError, TypeError):
        return None


def _num(s):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _corta(d):
    return d.strftime('%d/%m/%Y') if d else '?'


def validar(sil, curso=None, plantilla=None):
    adv = []

    def a(tipo, texto, grave=False):
        adv.append(dict(tipo=tipo, texto=texto, grave=grave))

    fi = sil['ficha']
    try:
        p_ini = date.fromisoformat(fi.get('inicio', ''))
        p_fin = date.fromisoformat(fi.get('fin', ''))
    except ValueError:
        p_ini = p_fin = None

    previo = None
    for m in sil['momentos']:
        n = m['n']
        ini, fin = _f(m.get('inicio')), _f(m.get('fin'))
        if not ini or not fin:
            a('Fechas', f'Momento {n}: no se pudo leer la fecha de inicio o fin.', True)
        elif ini > fin:
            a('Fechas', f'Momento {n}: la fecha de inicio ({_corta(ini)}) es posterior a la de fin ({_corta(fin)}).', True)
        if p_ini and ini and fin and (ini < p_ini or fin > p_fin):
            a('Fechas', f'Momento {n}: sus fechas ({_corta(ini)} – {_corta(fin)}) salen del periodo académico '
                        f'({_corta(p_ini)} – {_corta(p_fin)}).')
        if previo and ini and _f(previo.get('fin')) and ini <= _f(previo['fin']):
            rel = 'empieza el mismo día que termina' if ini == _f(previo['fin']) else 'se solapa con'
            a('Fechas', f'Momento {n} {rel} el Momento {previo["n"]} ({_corta(_f(previo["fin"]))}).')
        previo = m

        ses = m['sesiones']
        if not ses:
            a('Sesiones', f'Momento {n}: no tiene sesiones.', True)
        cruces = []
        for i, s in enumerate(ses):
            d1 = _f(s['desde'])
            d2 = _f(s['hasta']) or d1   # sesión de un solo día ("Sesión 1 06/10/2026")
            if not d1 or not d2:
                a('Sesiones', f'Momento {n}, sesión {s["n"]}: fechas ilegibles.', True); continue
            if ini and fin and (d1 < ini or d2 > fin):
                a('Fechas', f'Momento {n}, sesión {s["n"]}: sus fechas salen del rango del momento.')
            for t in ses[:i]:
                t1 = _f(t['desde'])
                t2 = _f(t['hasta']) or t1
                if t1 and t2 and d1 <= t2 and t1 <= d2:
                    cruces.append(f'S{t["n"]} ({_corta(t1)}–{_corta(t2)}) con S{s["n"]} ({_corta(d1)}–{_corta(d2)})')
        if cruces:
            a('Fechas solapadas', f'Momento {n}: ' + '; '.join(cruces) + '.')

        # horas
        tot = [_num(x) for x in m.get('totales', ('', '', ''))]
        suma = [sum(_num(s[k]) or 0 for s in ses) for k in ('hd', 'hpe', 'ha')]
        nombres = ['docente', 'práctico-experimental', 'autónomo']
        for nom, t, s_ in zip(nombres, tot, suma):
            if t is None:
                a('Horas', f'Momento {n}: no se encontró el total de horas ({nom}).', True)
            elif abs(t - s_) > 1e-6:
                a('Horas', f'Momento {n}: las horas {nom} de las sesiones suman {s_:g} y el total dice {t:g}.', True)
        for s in ses:
            for k, nom in (('hd', 'docente'), ('hpe', 'práctico-experimental'), ('ha', 'autónomo')):
                if _num(s[k]) is None:
                    a('Horas', f'Momento {n}, sesión {s["n"]}: falta la hora {nom}.', True)

        # RA y rúbrica
        for code in m['ra']:
            if code not in sil['ra']:
                a('RA', f'Momento {n} cita {code}, pero no se encontró su texto en el sílabo.', True)
        if not m['rubrica']:
            a('Rúbrica', f'Momento {n}: no se encontró la rúbrica.', True)
        for nombre, niveles in m['rubrica']:
            if len(niveles) != 5 or not all(niveles):
                a('Rúbrica', f'Momento {n}: el indicador "{nombre}" no tiene los 5 niveles completos.', True)
        if m.get('evidencia') and m.get('rubrica_ev') and \
                re.sub(r'\W', '', m['evidencia']) != re.sub(r'\W', '', m['rubrica_ev']):
            a('Evidencia', f'Momento {n}: la evidencia de la rúbrica no coincide con la del encabezado del momento.')

    otras = sum(_num(s['otras_h']) or 0 for m in sil['momentos'] for s in m['sesiones'])
    if otras:
        a('Horas (informativo)', f'Las "Otras actividades con el docente" suman {otras:g} h y no se cuentan en los '
                                 'totales de los momentos.')

    # totales del curso vs Presentación (por encabezado)
    pres = sil.get('presentacion') or {}
    mapa = {'Aprendizaje en contacto con el docente': 0, 'Aprendizaje práctico-experimental': 1,
            'Aprendizaje autónomo': 2}
    for etq, idx in mapa.items():
        if etq in pres:
            esperado = _num(pres[etq])
            real = sum(_num(m['totales'][idx]) or 0 for m in sil['momentos'])
            if esperado is not None and abs(esperado - real) > 1e-6:
                a('Horas', f'{etq}: la Presentación dice {esperado:g} h y los momentos suman {real:g} h.', True)

    if not (sil.get('pis') or {}).get('titulo') and not (sil.get('pis') or {}).get('aporte'):
        a('PIS', 'El sílabo no registra Proyecto Interdisciplinario Socioformativo (título y aporte vacíos): '
                 'la sección PIS no se incluirá en las páginas.')
    for tipo, lista in sil['bibliografia'].items():
        if not lista:
            a('Bibliografía', f'No se encontró bibliografía {tipo}.', tipo == 'basica')
        for e in lista:
            if not e['url']:
                a('Bibliografía (informativo)', f'Obra sin URL ni DOI: "{e["texto"][:70]}…". Se mostrará sin enlace "Acceder".')
            elif not re.match(r'^https?://\S+\.\S+$', e['url']):
                a('Bibliografía', f'URL/DOI con formato no válido: "{e["url"][:70]}".')

    if curso and plantilla and plantilla.get('ids') and curso['id'] not in plantilla['ids']:
        a('Curso', f'El HTML pegado apunta al curso {", ".join(sorted(plantilla["ids"]))}; '
                   f'se usará el de tu URL ({curso["id"]}).')
    return adv
