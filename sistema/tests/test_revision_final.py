# -*- coding: utf-8 -*-
"""Hallazgos de la revisión final: fallos de la IA a mitad de camino, fusión parcial, datos que cambian tras
generar, carga de varios docentes y datos que quedaban en la BD vectorial."""
import copy
import os
import sys
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod  # noqa: E402
from core import render, silabo, servicio  # noqa: E402
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
    monkeypatch.setattr(qwen, 'disponible', lambda: True)
    return m


def analizar():
    r = client.post('/api/analizar', data={'url': URL, 'token': TOKEN, 'usar_ia': '1'},
                    files={'pdf': ('s.pdf', open(B26, 'rb').read(), 'application/pdf')})
    assert r.status_code == 200, r.text
    return r.json()


def esperar(sid, max_s=90):
    t = time.time()
    while time.time() - t < max_s:
        j = client.get(f'/api/ia/{sid}').json()
        if j['estado'] in ('listo', 'error', 'no_disponible'):
            return j
        time.sleep(0.3)
    raise AssertionError(j)


# ---- 1. Qwen se cae a mitad de la extracción ----
def test_qwen_cae_a_mitad_marca_no_disponible_sin_diferencias_falsas(canvas, monkeypatch):
    llamadas = []

    def json_falso(sistema, usuario, esquema, nombre='salida', **kw):
        llamadas.append(nombre)
        if len(llamadas) > 3:
            raise qwen.QwenNoDisponible('caído')
        return {}, dict(segundos=0.01, entrada=1, salida=1, fin='stop')
    monkeypatch.setattr(qwen, 'json_con_esquema', json_falso)
    monkeypatch.setattr(trabajo.propuestas, 'proposito_ia', lambda m: None)
    fin = esperar(analizar()['sid'])
    assert fin['estado'] == 'no_disponible'
    assert fin['discrepancias'] == []
    assert len(llamadas) < 20, 'debe detenerse en cuanto Qwen deja de responder, no agotar todas las tareas'


def test_mayoria_de_tareas_fallidas_es_error_no_listo(canvas, monkeypatch):
    def lento_roto(alm, sid, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None):
        return {'momentos': [], 'ra': {}, 'pis': {}, 'bibliografia': {}}, dict(
            segundos_total=1, tareas=10, errores=[dict(tarea='sesion', momento=1, error='x')] * 8)
    monkeypatch.setattr(extractor, 'extraer', lento_roto)
    fin = esperar(analizar()['sid'])
    assert fin['estado'] == 'error' and fin['discrepancias'] == []


# ---- 2. Fusión parcial y revalidación ----
def test_fusion_no_usa_bloque_con_tareas_fallidas():
    ref, ia = silabo.leer(B26), silabo.leer(B26)
    m3 = next(m for m in ref['momentos'] if m['n'] == 3)
    m3['sesiones'], m3['rubrica'] = [], []
    sil, bloques = trabajo.fusionar(ref, ia, errores=[dict(tarea='sesion', momento=3, error='x')])
    assert bloques == ['M3.rubrica']
    assert next(m for m in sil['momentos'] if m['n'] == 3)['sesiones'] == []


def test_revalidar_tras_fusion_quita_avisos_viejos_y_controla_horas():
    ref = silabo.leer(B26)
    m3 = next(m for m in ref['momentos'] if m['n'] == 3)
    m3['sesiones'] = []
    sesion = dict(silabo=ref, curso=dict(host='indoamerica.instructure.com', id='1', slug='inicio'),
                  advertencias=[dict(tipo='Sesiones', texto='Momento 3: no tiene sesiones.', grave=True),
                                dict(tipo='Canvas', texto='aviso de canvas', grave=True)])
    ia = silabo.leer(B26)
    next(m for m in ia['momentos'] if m['n'] == 3)['sesiones'][0]['hd'] = '1.0'   # la IA lee mal una hora
    sil, bloques = trabajo.fusionar(ref, ia)
    trabajo.revalidar(sesion, sil, bloques)
    textos = [a['texto'] for a in sesion['advertencias']]
    assert 'Momento 3: no tiene sesiones.' not in textos
    assert 'aviso de canvas' in textos
    assert any(a['tipo'] == 'Horas' and 'Momento 3' in a['texto'] for a in sesion['advertencias'])
    assert any(a['tipo'] == 'Leído por IA' for a in sesion['advertencias'])


# ---- 3. Datos que cambian después de generar ----
def test_fusion_despues_de_generar_obliga_a_regenerar(canvas, monkeypatch):
    original = silabo.leer

    def sin_rubrica_m3(pdf):
        d = original(pdf)
        next(m for m in d['momentos'] if m['n'] == 3)['rubrica'] = []
        return d
    monkeypatch.setattr(silabo, 'leer', sin_rubrica_m3)
    evento = threading.Event()

    def extraer_tras_generar(alm, sid, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None):
        evento.wait(10)
        return original(pdf_path), dict(segundos_total=1, tareas=10, errores=[])
    monkeypatch.setattr(extractor, 'extraer', extraer_tras_generar)
    monkeypatch.setattr(trabajo.propuestas, 'proposito_ia', lambda m: None)
    j = analizar()
    client.post('/api/generar', json={'sid': j['sid']})
    evento.set()
    fin = esperar(j['sid'])
    assert fin['bloques_ia'] == ['M3.rubrica']
    r = client.post('/api/publicar', json={'sid': j['sid'], 'momentos': [3], 'confirmado': True})
    assert r.status_code == 409 and canvas.puts == []
    g = client.post('/api/generar', json={'sid': j['sid']}).json()
    from bs4 import BeautifulSoup
    assert g['listo'] and 'Implementación de estructuras no lineales' in BeautifulSoup(g['paginas']['3'], 'html.parser').get_text()
    assert client.post('/api/publicar', json={'sid': j['sid'], 'momentos': [3], 'confirmado': True}).status_code == 200


# ---- 4. Varios docentes: cola local con límite global ----
def test_semaforo_global_limita_peticiones_simultaneas(monkeypatch):
    monkeypatch.setenv('QWEN_MAX_SIMULTANEAS', '3')
    qwen._semaforos.clear()
    activos, maximo, lock = [0], [0], threading.Lock()

    def create(**kw):
        with lock:
            activos[0] += 1; maximo[0] = max(maximo[0], activos[0])
        time.sleep(0.15)
        with lock:
            activos[0] -= 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'), finish_reason='stop')],
                               usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2))
    monkeypatch.setattr(qwen, 'cliente', lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    monkeypatch.setattr(qwen, 'contar_tokens', lambda t: 5)
    esq = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}
    hilos = [threading.Thread(target=qwen.json_con_esquema, args=('s', 'u', esq)) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert maximo[0] == 3


# ---- 5. La BD vectorial no conserva el sílabo ----
def test_vectores_del_silabo_se_borran_al_terminar(canvas, monkeypatch):
    monkeypatch.setattr(extractor, 'extraer', lambda alm, sid, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None:
                        (silabo.leer(pdf_path), dict(segundos_total=1, tareas=10, errores=[])))
    monkeypatch.setattr(trabajo.propuestas, 'proposito_ia', lambda m: None)
    fin = esperar(analizar()['sid'])
    assert fin['estado'] == 'listo'
    assert trabajo._almacen().cli.count('silabos').count == 0
