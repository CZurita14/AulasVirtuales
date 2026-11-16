# -*- coding: utf-8 -*-
"""Guías prácticas → tareas PAE + rúbricas, contra un Canvas SIMULADO.

Usa el sílabo de Programación Estructurada (raíz del proyecto) y la Guía N° 3 (tests/fixtures).
"""
import os
import sys
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod  # noqa: E402
from core import canvas, guia, pae, silabo  # noqa: E402
from mock_canvas import CURSO, TOKEN, MockCanvas  # noqa: E402

SILABO = os.path.join(ROOT, 'B26_Software_Programacion Estructurada.pdf')
GUIA = os.path.join(SIS, 'tests', 'fixtures', 'guia_pe_n3.pdf')
URL = f'https://indoamerica.instructure.com/courses/{CURSO}'
pytestmark = pytest.mark.skipif(not (os.path.exists(SILABO) and os.path.exists(GUIA)),
                                reason='faltan los PDF de prueba (sílabo PE y guía N° 3)')
client = TestClient(appmod.app)
NOMBRE = 'PAE3-Implementación de árboles y grafos e integración de la primera versión del prototipo'


@pytest.fixture
def mock(monkeypatch):
    m = MockCanvas()
    monkeypatch.setattr(appmod, 'TRANSPORT', httpx.MockTransport(m.handler))
    monkeypatch.setenv('IA_ACTIVA', '0')
    return m


def analizar(token=TOKEN, url=URL):
    with open(SILABO, 'rb') as s, open(GUIA, 'rb') as g:
        return client.post('/api/guias/analizar', data=dict(url=url, token=token),
                           files=[('silabo', ('silabo.pdf', s.read(), 'application/pdf')),
                                  ('guias', ('guia3.pdf', g.read(), 'application/pdf'))])


# ---------------- lector ----------------
def test_lee_la_guia():
    g, = guia.leer(GUIA)
    assert g['n'] == 3 and g['inicio'] == date(2027, 1, 12) and g['fin'] == date(2027, 1, 26)
    assert g['titulo'] == 'Implementación de árboles y grafos e integración de la primera versión del prototipo'
    assert len(g['procedimiento']) == 8 and g['procedimiento'][0].startswith('Implementar un árbol binario')
    assert g['ra'] == '' and g['horas'] == '24.0' and not g['faltan']
    assert g['resultado_esperado'].startswith('Primera versión funcional')
    assert g['conclusiones'].startswith('Cada equipo redacta')


def test_tipo_oracion_respeta_siglas():
    assert guia.tipo_oracion('DECLARAR EL USO DE IA EN PYTHON. LUEGO PUBLICAR') == \
        'Declarar el uso de IA en Python. Luego publicar'
    assert guia.tipo_oracion('Texto ya normal') == 'Texto ya normal'


def test_empareja_por_titulo_y_fechas():
    sil = silabo.leer(SILABO)
    g, = guia.leer(GUIA)
    m, info, aviso = pae.emparejar(g, sil['momentos'])
    assert m['n'] == 3 and info == dict(titulo=True, fechas=True) and aviso is None


def test_puntos_y_reglas_de_rubrica():
    assert pae.puntos(10, 4) == (2.5, [0.5, 1.0, 1.5, 2.0, 2.5])
    rub = [dict(indicador='A', niveles=['x'] * 5)] * 3
    assert any('no cuadran' in e for e in pae.revisar_rubrica(rub, 10))
    assert pae.revisar_rubrica(rub, 9) == []
    assert any('vacía' in e for e in pae.revisar_rubrica([dict(indicador='A', niveles=['x', '', 'x', 'x', 'x'])], 10))


# ---------------- flujo completo ----------------
def test_flujo_completo_crea_tarea_y_rubrica(mock):
    r = analizar()
    assert r.status_code == 200, r.text
    j = r.json()
    it = j['items'][0]
    assert it['nombre'] == NOMBRE and it['momento'] == 3 and it['puntos'] == 10
    assert len(it['rubrica']) == 4 and it['rubrica'][0]['indicador'] == 'Implementación de estructuras no lineales'
    assert it['ra'].startswith('RA2: Aplica las estructuras lineales')
    assert j['grupo_id'] == 502 and j['secuencia']['faltan'] == [1, 2]
    assert any('Resultados de Aprendizaje' in a['texto'] for a in j['advertencias'])

    v = client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0)])).json()
    assert v['items'][0]['listo'], v['items'][0]['controles']
    assert 'Implementar un árbol binario' in v['items'][0]['descripcion']

    assert client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0])).status_code == 409  # sin confirmar
    res = client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True)).json()['resultados']['0']
    assert res['ok'] and res['verificado'], res

    tarea = next(t for t in mock.tareas.values() if t['name'] == NOMBRE)
    assert tarea['assignment_group_id'] == 502 and tarea['published'] is False and tarea['points_possible'] == 10
    assert tarea['due_at'] == '2027-01-26T23:59:00-05:00' and tarea['unlock_at'] == '2027-01-12T00:00:00-05:00'
    rub = next(x for x in mock.rubricas.values() if x['title'] == NOMBRE)
    assert rub['points_possible'] == 10 and len(rub['data']) == 4
    assert [x['description'] for x in rub['data'][0]['ratings']] == ['Cocreativo', 'Crítico', 'Reflexivo', 'Resolutivo', 'Receptivo']
    assert [x['points'] for x in rub['data'][0]['ratings']] == [2.5, 2.0, 1.5, 1.0, 0.5]
    assert mock.items_modulo and mock.items_modulo[0]['module_id'] == 13 and mock.items_modulo[0]['content_id'] == tarea['id']

    # no duplica si se pulsa otra vez
    client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True))
    assert sum(t['name'] == NOMBRE for t in mock.tareas.values()) == 1

    d = client.post('/api/guias/deshacer', json=dict(sid=j['sid'], i=0))
    assert d.status_code == 200
    assert not any(t['name'] == NOMBRE for t in mock.tareas.values())
    assert not any(x['title'] == NOMBRE for x in mock.rubricas.values())


def test_ediciones_del_docente(mock):
    j = analizar().json()
    rub = j['items'][0]['rubrica']
    rub[0]['niveles'][1] = 'Implementa el árbol con los tres recorridos.'
    v = client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(
        i=0, nombre='PAE3-Árboles y grafos', puntos=20, inicio='2027-01-13', fin='2027-01-25', rubrica=rub, modulo=False)])).json()
    assert v['items'][0]['listo']
    client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True))
    t = next(t for t in mock.tareas.values() if t['name'] == 'PAE3-Árboles y grafos')
    assert t['points_possible'] == 20 and t['due_at'].startswith('2027-01-25')
    r = next(x for x in mock.rubricas.values() if x['title'] == 'PAE3-Árboles y grafos')
    assert r['data'][0]['ratings'][3]['long_description'] == 'Implementa el árbol con los tres recorridos.'
    assert r['data'][0]['ratings'][0]['points'] == 5.0
    assert not mock.items_modulo


def test_cambios_sin_vista_previa_no_se_publican(mock):
    j = analizar().json()
    client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0)]))
    appmod._sesiones[j['sid']]['version'] += 1          # p. ej. la IA cambió la rúbrica después
    r = client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True))
    assert r.status_code == 409 and 'vista previa' in r.json()['detail']


def test_rubrica_incompleta_se_crea_igual_y_avisa(mock):
    j = analizar().json()
    rub = j['items'][0]['rubrica']
    rub[2]['niveles'][4] = ''
    v = client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0, rubrica=rub)])).json()
    assert not v['items'][0]['listo'] and v['items'][0]['publicable']
    res = client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True)).json()['resultados']['0']
    assert res['ok'] and res['verificado'] is False and any('Rúbrica' in p for p in res['pendientes'])
    t = next(t for t in mock.tareas.values() if t['name'].startswith('PAE3'))
    assert t['published'] is False


def test_sin_grupo_no_se_crea(mock):
    mock.grupos = [dict(id=501, name='Tareas')]
    j = analizar().json()
    v = client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0)])).json()
    assert not v['items'][0]['publicable']
    res = client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True)).json()['resultados']['0']
    assert not res['ok'] and 'Grupo' in res['mensaje']
    assert not any(t['name'].startswith('PAE3') for t in mock.tareas.values())


def test_pae_existente_no_se_duplica(mock):
    mock.tareas[650] = dict(id=650, name='PAE3-Versión anterior', assignment_group_id=502, published=True)
    j = analizar().json()
    assert j['items'][0]['incluir'] is False and j['items'][0]['existe']['nombre'] == 'PAE3-Versión anterior'
    client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0, incluir=True)]))
    res = client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True)).json()['resultados']['0']
    assert not res['ok'] and 'existe' in res['mensaje']


def test_sin_grupo_actividades_pide_elegir(mock):
    mock.grupos = [dict(id=501, name='Tareas')]
    j = analizar().json()
    assert j['grupo_id'] is None and any('Actividades' in a['texto'] for a in j['advertencias'])
    v = client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0)])).json()
    assert not v['items'][0]['listo']
    v = client.post('/api/guias/generar', json=dict(sid=j['sid'], grupo_id=501, items=[dict(i=0)])).json()
    assert v['items'][0]['listo']
    assert client.post('/api/guias/generar', json=dict(sid=j['sid'], grupo_id=999, items=[])).status_code == 422


def test_falla_la_rubrica_informa_y_permite_deshacer(mock):
    mock.fallar_rubrica = True
    j = analizar().json()
    client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0)]))
    res = client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True)).json()['resultados']['0']
    assert not res['ok'] and 'rúbrica' in res['mensaje']
    assert client.post('/api/guias/deshacer', json=dict(sid=j['sid'], i=0)).status_code == 200
    assert not any(t['name'] == NOMBRE for t in mock.tareas.values())


def test_entradas_invalidas(mock):
    assert analizar(token='malo_0123456789').status_code == 422
    assert analizar(url='https://evil.com/courses/1').status_code == 422
    with open(SILABO, 'rb') as s:
        r = client.post('/api/guias/analizar', data=dict(url=URL, token=TOKEN),
                        files=[('silabo', ('s.pdf', s.read(), 'application/pdf')),
                               ('guias', ('g.pdf', b'no es pdf', 'application/pdf'))])
    assert r.status_code == 422


def test_ia_adapta_y_valida(mock, monkeypatch):
    from ia import qwen
    j = analizar().json()
    orig = j['items'][0]['rubrica'][0]['niveles']

    def falso(sis, usuario, esquema, **k):
        assert 'Implementar un árbol binario' in usuario and set(esquema['required']) == {
            'receptivo', 'resolutivo', 'reflexivo', 'critico', 'cocreativo'}
        if 'INDICADOR: Implementación de estructuras no lineales' not in usuario:
            return dict(zip(esquema['required'], ['x'] * 5)), {}      # sin cambios útiles
        return dict(
            receptivo='Receptivo: Reconoce el árbol binario de búsqueda y el grafo, pero los codifica de forma incompleta.',
            resolutivo='',
            reflexivo=orig[3] + ' con matriz de adyacencia',               # texto del nivel Crítico: nivel corrido
            critico='palabra ' * 60,
            cocreativo='Crea soluciones con árbol binario de búsqueda y grafos que aportan mejoras verificables al prototipo.'), {}
    monkeypatch.setattr(qwen, 'json_con_esquema', falso)
    r = client.post(f'/api/guias/adaptar/{j["sid"]}/0').json()
    assert r['ok'] and r['cambiadas'] == 2
    f = r['rubrica'][0]
    assert f['ia'] == [True, False, False, False, True]
    assert f['niveles'][0].startswith('Reconoce el árbol binario')        # sin el prefijo "Receptivo:"
    assert f['niveles'][2] == orig[2] and f['indicador'] == 'Implementación de estructuras no lineales'
    assert not any(any(x['ia']) for x in r['rubrica'][1:])

    monkeypatch.setattr(qwen, 'json_con_esquema', lambda *a, **k: (_ for _ in ()).throw(qwen.QwenNoDisponible('x')))
    r = client.post(f'/api/guias/adaptar/{j["sid"]}/0').json()
    assert not r['ok']


def test_cliente_canvas_exige_aprobacion(mock):
    cv = canvas.Canvas(canvas.curso_desde_url(URL), TOKEN, httpx.MockTransport(mock.handler))
    for f in (lambda: cv.crear_tarea({}), lambda: cv.crear_rubrica('x', [], 1),
              lambda: cv.agregar_a_modulo(1, 1), lambda: cv.borrar_tarea(1), lambda: cv.borrar_rubrica(1)):
        with pytest.raises(PermissionError):
            f()


def test_paginas_menu_silabos_guias():
    assert 'Guías prácticas' in client.get('/').text and 'Sílabos' in client.get('/').text
    assert 'Token de acceso de Canvas' in client.get('/silabos').text
    assert 'Guías prácticas' in client.get('/guias').text
