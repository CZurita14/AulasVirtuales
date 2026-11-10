# -*- coding: utf-8 -*-
"""Segunda lectura con IA en segundo plano: no bloquea, no cambia lo publicado y solo completa bloques vacíos."""
import copy
import glob
import os
import sys
import threading
import time

import httpx
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod  # noqa: E402
from core import calidad, propuestas, render, silabo  # noqa: E402
from ia import extractor, qwen, trabajo  # noqa: E402
from mock_canvas import CURSO, TOKEN, MockCanvas  # noqa: E402

B26 = os.path.join(ROOT, 'B26_Software_Programacion Estructurada.pdf')
URL = f'https://indoamerica.instructure.com/courses/{CURSO}'
client = TestClient(appmod.app)


@pytest.fixture
def canvas(monkeypatch):
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    monkeypatch.setattr(appmod, 'TRANSPORT', httpx.MockTransport(m.handler))
    monkeypatch.setenv('QDRANT_URL', '')
    return m


def analizar(usar_ia='1'):
    r = client.post('/api/analizar', data={'url': URL, 'token': TOKEN, 'usar_ia': usar_ia},
                    files={'pdf': ('s.pdf', open(B26, 'rb').read(), 'application/pdf')})
    assert r.status_code == 200, r.text
    return r.json()


def esperar(sid, estados=('listo', 'error', 'no_disponible'), max_s=60):
    t = time.time()
    while time.time() - t < max_s:
        j = client.get(f'/api/ia/{sid}').json()
        if j['estado'] in estados:
            return j
        time.sleep(0.3)
    raise AssertionError(f'la IA no terminó: {j}')


def test_analizar_no_espera_a_la_ia(canvas, monkeypatch):
    monkeypatch.setattr(qwen, 'disponible', lambda: True)
    liberar = threading.Event()

    def lento(alm, sid, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None):
        assert liberar.wait(15), 'El análisis debe devolver la respuesta antes de liberar la IA'
        return silabo.leer(pdf_path), dict(segundos_total=3, errores=[])
    monkeypatch.setattr(extractor, 'extraer', lento)
    j = analizar()
    assert j['ia']['estado'] in ('pendiente', 'en_curso')
    liberar.set()
    fin = esperar(j['sid'])
    assert fin['estado'] == 'listo' and fin['discrepancias'] == [] and fin['bloques_ia'] == []


def test_qwen_caido_sistema_funciona(canvas, monkeypatch):
    monkeypatch.setattr(qwen, 'disponible', lambda: False)
    j = analizar()
    assert client.get(f'/api/ia/{j["sid"]}').json()['estado'] == 'no_disponible'
    g = client.post('/api/generar', json={'sid': j['sid']}).json()
    assert g['listo']
    p = client.post('/api/publicar', json={'sid': j['sid'], 'momentos': [1, 2, 3, 4], 'confirmado': True}).json()
    assert all(v['ok'] for v in p['resultados'].values())


def test_ia_desactivada_por_el_docente(canvas, monkeypatch):
    monkeypatch.setattr(qwen, 'disponible', lambda: True)
    j = analizar(usar_ia='0')
    assert client.get(f'/api/ia/{j["sid"]}').json()['estado'] == 'desactivada'


def test_fusion_solo_bloques_vacios():
    ref = silabo.leer(B26)
    ia = silabo.leer(B26)
    m3 = next(m for m in ref['momentos'] if m['n'] == 3)
    m3['rubrica'] = []
    ia['momentos'][0]['titulo'] = 'TÍTULO CAMBIADO POR LA IA'   # no debe usarse: el bloque no estaba vacío
    sil, bloques = trabajo.fusionar(ref, ia)
    assert bloques == ['M3.rubrica']
    assert next(m for m in sil['momentos'] if m['n'] == 3)['rubrica'] == next(m for m in ia['momentos'] if m['n'] == 3)['rubrica']
    assert sil['momentos'][0]['titulo'] == ref['momentos'][0]['titulo']
    assert ref['momentos'][2]['rubrica'] == []  # la referencia no se modifica
    curso = dict(host='indoamerica.instructure.com', id='1', slug='inicio')
    tpl = render.leer_plantilla_institucional()
    prop = propuestas.proponer(sil)
    m = next(m for m in sil['momentos'] if m['n'] == 3)
    h = render.render(sil, 3, tpl, curso, prop['propositos'][3], prop['complementaria'][3])
    assert all(i['ok'] for i in calidad.controlar(h, m, sil, curso, tpl, prop['complementaria'][3], prop['propositos'][3])
               if i['bloquea'])


def test_discrepancia_no_cambia_lo_publicado(canvas, monkeypatch):
    monkeypatch.setattr(qwen, 'disponible', lambda: True)

    def distinta(alm, sid, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None):
        ia = silabo.leer(pdf_path)
        ia['momentos'][1]['sesiones'][0]['hd'] = '99.0'
        return ia, dict(segundos_total=1, errores=[])
    monkeypatch.setattr(extractor, 'extraer', distinta)
    j = analizar()
    fin = esperar(j['sid'])
    assert any(d['campo'] == 'M2.S1.horas' and d['gravedad'] == 'alta' for d in fin['discrepancias'])
    client.post('/api/generar', json={'sid': j['sid']})
    client.post('/api/publicar', json={'sid': j['sid'], 'momentos': [2], 'confirmado': True})
    texto = BeautifulSoup(canvas.paginas['momento-2']['body'], 'html.parser').get_text(' ')
    assert '(99.0 h)' not in texto and '(6.0 h)' in texto


def test_error_de_la_ia_no_expone_detalles_internos(canvas, monkeypatch):
    monkeypatch.setattr(qwen, 'disponible', lambda: True)

    def revienta(*a, **k):
        raise RuntimeError(r'fallo en C:\secreto\ruta al llamar http://172.16.8.69:8000/v1')
    monkeypatch.setattr(extractor, 'extraer', revienta)
    fin = esperar(analizar()['sid'])
    assert fin['estado'] == 'error'
    assert 'secreto' not in fin['error'] and '172.16' not in fin['error']
    assert fin['error'].startswith('La revisión con IA no se pudo completar')


def test_segunda_lectura_trae_propositos_de_la_ia(canvas, monkeypatch):
    monkeypatch.setattr(qwen, 'disponible', lambda: True)
    monkeypatch.setattr(extractor, 'extraer', lambda alm, sid, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None:
                        (silabo.leer(pdf_path), dict(segundos_total=1, errores=[])))
    monkeypatch.setattr(propuestas, 'proposito_ia', lambda m: f'Desarrollar el momento {m["n"]} con criterios de calidad.')
    fin = esperar(analizar()['sid'])
    assert fin['propositos'] == {str(n): f'Desarrollar el momento {n} con criterios de calidad.' for n in (1, 2, 3, 4)}
