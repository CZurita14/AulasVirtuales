# -*- coding: utf-8 -*-
"""Compara la extracción de Qwen contra la lectura por reglas (referencia validada) y renderiza ambas."""
import difflib
import re

from bs4 import BeautifulSoup

from core import calidad, propuestas, render


def _n(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def _sim(a, b):
    return difflib.SequenceMatcher(None, _n(a), _n(b)).ratio()


def campos(sil):
    """Aplana los campos que terminan en la página: (categoría, clave, valor)."""
    out = []
    for c, t in sorted(sil['ra'].items()):
        out.append(('RA', c, t))
    out += [('PIS', 'titulo', sil['pis'].get('titulo', '')), ('PIS', 'aporte', sil['pis'].get('aporte', ''))]
    for tipo, lista in sil['bibliografia'].items():
        out.append(('Bibliografía', f'{tipo}#cantidad', len(lista)))
        for i, o in enumerate(lista, 1):
            out += [('Bibliografía', f'{tipo}{i}.texto', o['texto']), ('Bibliografía', f'{tipo}{i}.url', o['url'])]
    for m in sil['momentos']:
        p = f'M{m["n"]}'
        out += [('Cabecera', f'{p}.titulo', m['titulo']), ('Cabecera', f'{p}.inicio', m['inicio']),
                ('Cabecera', f'{p}.fin', m['fin']), ('Cabecera', f'{p}.ra', ','.join(m['ra'])),
                ('Cabecera', f'{p}.evidencia', m['evidencia']), ('Sesiones', f'{p}.cantidad', len(m['sesiones'])),
                ('Horas', f'{p}.totales', '/'.join(str(x) for x in m['totales']))]
        for s in m['sesiones']:
            q = f'{p}.S{s["n"]}'
            out += [('Sesiones', f'{q}.fechas', f'{s["desde"]}-{s["hasta"]}'),
                    ('Horas', f'{q}.horas', f'{s["hd"]}/{s["hpe"]}/{s["ha"]}/{s["otras_h"] or ""}')]
            for k, nom in (('doc', 'docente'), ('otras', 'otras'), ('pe', 'practico'), ('aut', 'autonomo'), ('cont', 'contenidos')):
                out.append(('Texto de sesiones', f'{q}.{nom}', s[k] or ''))
        out.append(('Rúbrica', f'{p}.indicadores', len(m['rubrica'])))
        for i, (nom, niv) in enumerate(m['rubrica'], 1):
            out.append(('Rúbrica', f'{p}.I{i}.nombre', nom))
            for k, v in zip(('rec', 'res', 'ref', 'cri', 'coc'), niv):
                out.append(('Rúbrica', f'{p}.I{i}.{k}', v))
    return out


def comparar(ref, ia):
    a = {k: (c, v) for c, k, v in campos(ref)}
    b = {k: v for _, k, v in campos(ia)}
    filas = []
    for k, (cat, v) in a.items():
        w = b.get(k, None)
        exacto = _n(v) == _n(w) if w is not None else False
        filas.append(dict(categoria=cat, campo=k, exacto=exacto, similitud=1.0 if exacto else (_sim(v, w) if w is not None else 0.0),
                          referencia=_n(v)[:200], ia=_n(w)[:200] if w is not None else '(falta)'))
    sobrantes = [k for k in b if k not in a]
    cats = {}
    for f in filas:
        c = cats.setdefault(f['categoria'], dict(campos=0, exactos=0, sim=0.0))
        c['campos'] += 1; c['exactos'] += f['exacto']; c['sim'] += f['similitud']
    for c in cats.values():
        c['exactitud'] = round(100 * c['exactos'] / c['campos'], 1)
        c['similitud'] = round(100 * c['sim'] / c['campos'], 1)
    total = dict(campos=len(filas), exactos=sum(f['exacto'] for f in filas))
    total['exactitud'] = round(100 * total['exactos'] / max(1, total['campos']), 1)
    return dict(total=total, categorias=cats, filas=filas, sobrantes=sobrantes)


def paginas(sil_ref, sil_ia, curso):
    """Renderiza con la plantilla institucional, con los MISMOS textos propuestos (para aislar la lectura),
    y pasa la lista de control contra el sílabo de referencia (lo que debería decir la página)."""
    tpl = render.leer_plantilla_institucional()
    prop = propuestas.proponer(sil_ref)
    res = {}
    for m in sil_ref['momentos']:
        n = m['n']
        h_ref = render.render(sil_ref, n, tpl, curso, prop['propositos'][n], prop['complementaria'][n])
        try:
            h_ia = render.render(sil_ia, n, tpl, curso, prop['propositos'][n], prop['complementaria'][n])
            ctrl = calidad.controlar(h_ia, m, sil_ref, curso, tpl, prop['complementaria'][n], prop['propositos'][n])
        except Exception as e:
            h_ia, ctrl = '', [dict(nombre='Renderizado', ok=False, bloquea=True, detalle=f'{type(e).__name__}: {e}')]
        t = lambda h: _n(BeautifulSoup(h, 'html.parser').get_text(' '))
        res[n] = dict(identica=t(h_ref) == t(h_ia), similitud=round(100 * _sim(t(h_ref), t(h_ia)), 2),
                      control_ok=sum(i['ok'] for i in ctrl if i['bloquea']), control_total=sum(1 for i in ctrl if i['bloquea']),
                      fallos=[i['nombre'] for i in ctrl if i['bloquea'] and not i['ok']], html=h_ia)
    return res
