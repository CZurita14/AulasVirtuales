# -*- coding: utf-8 -*-
"""Exactitud mínima de Qwen contra la lectura por reglas (requiere el servidor de IA; marca `qwen`)."""
import glob
import os
import sys

import pytest

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)

from core import silabo  # noqa: E402
from ia import comparar, documento, extractor, qwen, vectores  # noqa: E402

PDFS = sorted(glob.glob(os.path.join(ROOT, 'silabos_prueba', '*.pdf')) + glob.glob(os.path.join(ROOT, '*.pdf')))
pytestmark = [pytest.mark.qwen, pytest.mark.skipif(not qwen.disponible(), reason='servidor Qwen no disponible')]


@pytest.fixture(scope='module')
def alm():
    return vectores.Almacen(url='')


@pytest.mark.parametrize('pdf', PDFS, ids=[os.path.basename(p) for p in PDFS])
def test_exactitud_minima(alm, pdf):
    ref = silabo.leer(pdf)
    sid = alm.id_silabo(pdf)
    alm.indexar(sid, documento.fragmentos(pdf))
    ia, met = extractor.extraer(alm, sid, ficha=ref['ficha'], pdf_path=pdf)
    c = comparar.comparar(ref, ia)
    cats = {k: v['exactitud'] for k, v in c['categorias'].items()}
    difs = [(f['campo'], f['referencia'][-60:], f['ia'][-60:]) for f in c['filas'] if not f['exacto']][:15]
    assert met['errores'] == [], met['errores']
    assert cats['Horas'] == 100.0, difs
    assert cats['PIS'] == 100.0, difs
    assert cats['Bibliografía'] == 100.0, difs
    assert c['total']['exactitud'] >= 97.0, (cats, difs)
