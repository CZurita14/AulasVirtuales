# -*- coding: utf-8 -*-
"""Segundo lector: diferencias entre la lectura por reglas y la de Qwen, para mostrarlas al docente.

No cambia nada: solo informa. Ignora diferencias que no cambian la página (espacios, punto final,
viñeta, mayúsculas en códigos de RA).
"""
import re

from .comparar import campos

_ALTAS_CAT = {'Horas', 'Sesiones', 'RA'}
_ALTAS_SUFIJO = ('.inicio', '.fin', '.ra', '.indicadores', '#cantidad')


def _norm(v, clave):
    s = re.sub(r'\s+', ' ', str(v if v is not None else '')).strip()
    s = re.sub(r'^•\s*', '', s).rstrip('.').strip()
    return s.upper() if clave.endswith('.ra') else s


def _gravedad(cat, clave):
    return 'alta' if cat in _ALTAS_CAT or clave.endswith(_ALTAS_SUFIJO) else 'media'


def discrepancias(ref, ia):
    b = {k: v for _, k, v in campos(ia)}
    out = []
    for cat, k, v in campos(ref):
        w = b.get(k)
        a_, b_ = _norm(v, k), _norm(w, k)
        if a_ == b_:
            continue
        if a_ and not b_:
            out.append(dict(campo=k, categoria=cat, reglas=str(v), ia='', tipo='ia_sin_dato', gravedad='media'))
        else:
            out.append(dict(campo=k, categoria=cat, reglas=str(v), ia=str(w if w is not None else ''), tipo='distinto',
                            gravedad=_gravedad(cat, k)))
    return sorted(out, key=lambda x: x['gravedad'] != 'alta')


def resumen(lista):
    cats = {}
    for x in lista:
        cats[x['categoria']] = cats.get(x['categoria'], 0) + 1
    return dict(total=len(lista), altas=sum(x['gravedad'] == 'alta' for x in lista),
                medias=sum(x['gravedad'] == 'media' for x in lista), por_categoria=cats)
