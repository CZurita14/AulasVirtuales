# -*- coding: utf-8 -*-
"""Historial de cargas: almacén SQLite, siembra, correcciones, registro desde los flujos y API."""
import os
import sqlite3
import sys

import pytest

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SIS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import historial  # noqa: E402

CURSO = dict(id='36732', nombre='B26-MED-1-COMPUTACION Y SOCIEDAD PARALELO 02')


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setenv('HISTORIAL_DB', str(tmp_path / 'h.sqlite'))
    monkeypatch.delenv('HISTORIAL', raising=False)
    monkeypatch.delenv('HISTORIAL_CLAVE', raising=False)
    monkeypatch.setenv('HISTORIAL_LOCAL', '1')       # uso en el propio equipo (opción explícita)
    return tmp_path / 'h.sqlite'


# ---------------- Tarea 1: almacén ----------------
def test_registrar_y_listar():
    a = historial.registrar('silabos', 'Analizado', 'ok', archivos=['med.pdf'], curso=CURSO, fecha='2026-11-10T09:00')
    b = historial.registrar('guias', 'PAE creadas: PAE3', 'ok', archivos=['G3.pdf'], curso=dict(id='36283', nombre='PE'),
                            enlaces=[dict(texto='PAE3', url='https://x.instructure.com/courses/36283/assignments/9')],
                            fecha='2026-11-12T10:00')
    assert a and b
    todo = historial.listar()
    assert [e['id'] for e in todo] == [b, a]                         # más reciente primero
    assert [e['id'] for e in historial.listar(orden='asc')] == [a, b]
    assert [e['id'] for e in historial.listar(tipo='guias')] == [b]
    assert [e['id'] for e in historial.listar(curso='36732')] == [a]
    assert [e['id'] for e in historial.listar(texto='g3.PDF')] == [b]   # sin distinguir mayúsculas
    e = todo[0]
    assert e['archivos'] == ['G3.pdf'] and e['enlaces'][0]['texto'] == 'PAE3' and e['correccion'] is None
    assert e['reconstruido'] is False and e['curso_nombre'] == 'PE'


def test_no_guarda_token(db):
    historial.registrar('silabos', 'Analizado', 'ok', archivos=['x.pdf'], curso=CURSO)
    cols = [r[1] for r in sqlite3.connect(db).execute('PRAGMA table_info(eventos)')]
    assert not any('token' in c for c in cols)


def test_correccion_conserva_original():
    i = historial.registrar('guias', 'Publicar PAE1–PAE4', 'error', detalle='Bloqueado: cambios sin vista previa')
    historial.corregir(i, 'ok', 'Se regeneró la vista previa y se publicaron.')
    e = historial.listar()[0]
    assert e['resultado'] == 'error' and e['detalle'] == 'Bloqueado: cambios sin vista previa'
    assert e['correccion']['resultado'] == 'ok' and e['correccion']['nota'].startswith('Se regeneró')
    assert e['correccion']['fecha']
    with pytest.raises(ValueError):
        historial.corregir(i, 'quizás', 'x')
    with pytest.raises(KeyError):
        historial.corregir(999, 'ok', 'x')


def test_quitar_correccion():
    i = historial.registrar('silabos', 'Publicar', 'error')
    historial.corregir(i, 'ok', 'sí se publicó')
    historial.quitar_correccion(i)
    assert historial.listar()[0]['correccion'] is None


def test_siembra_idempotente():
    assert historial.sembrar() == 8
    assert historial.sembrar() == 0
    filas = historial.listar()
    assert len(filas) == 8 and all(e['reconstruido'] and e['fuente'] for e in filas)
    med = [e for e in filas if e['curso_id'] == '36732']
    assert med and med[0]['archivos'] == ['silabo_pf20261106_165315med-paral_02.pdf']
    # lo que no se registró no se inventa
    assert any(e['archivos'] == [] and e['fecha'].startswith('2026-11-12T18:0') for e in filas)


def test_resumen_usa_correccion():
    i = historial.registrar('silabos', 'Publicado Momentos 1–4', 'error', curso=CURSO)
    historial.registrar('silabos', 'Analizado', 'ok', curso=CURSO)
    r = historial.resumen(historial.listar())
    assert r == dict(eventos=2, cursos=1, publicaciones=0, errores=1)
    historial.corregir(i, 'ok', 'quedó publicado')
    assert historial.resumen(historial.listar()) == dict(eventos=2, cursos=1, publicaciones=1, errores=0)


def test_apagado(monkeypatch):
    monkeypatch.setenv('HISTORIAL', '0')
    assert not historial.habilitado()
    assert historial.registrar('silabos', 'Analizado', 'ok') is None


def test_ruta_no_escribible_no_lanza(monkeypatch, tmp_path):
    (tmp_path / 'soy_archivo').write_text('x')          # una carpeta que en realidad es un archivo
    monkeypatch.setenv('HISTORIAL_DB', str(tmp_path / 'soy_archivo' / 'h.sqlite'))
    assert historial.registrar('silabos', 'Analizado', 'ok') is None


# ---------------- Tarea 2: registro desde los flujos ----------------
import glob  # noqa: E402

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app as appmod  # noqa: E402
from core import render  # noqa: E402
from mock_canvas import CURSO as CURSO_MOCK, TOKEN, MockCanvas  # noqa: E402

ROOT = os.path.dirname(SIS)
PDF_PE = os.path.join(ROOT, 'B26_Software_Programacion Estructurada.pdf')
GUIA = os.path.join(SIS, 'tests', 'fixtures', 'guia_pe_n3.pdf')
URL = f'https://indoamerica.instructure.com/courses/{CURSO_MOCK}'
client = TestClient(appmod.app, client=('127.0.0.1', 50000))   # el propio equipo
con_pdfs = pytest.mark.skipif(not (os.path.exists(PDF_PE) and os.path.exists(GUIA)), reason='faltan PDF de prueba')


@pytest.fixture
def mock(monkeypatch):
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    monkeypatch.setattr(appmod, 'TRANSPORT', httpx.MockTransport(m.handler))
    monkeypatch.setenv('IA_ACTIVA', '0')
    return m


def _analizar_silabo(token=TOKEN):
    with open(PDF_PE, 'rb') as f:
        return client.post('/api/analizar', data=dict(url=URL, token=token),
                           files={'pdf': ('Mi Silabo PE.pdf', f.read(), 'application/pdf')})


@con_pdfs
def test_flujo_silabos_queda_en_historial(mock):
    j = _analizar_silabo().json()
    client.post('/api/generar', json=dict(sid=j['sid']))
    client.post('/api/publicar', json=dict(sid=j['sid'], momentos=[1, 2], confirmado=True))
    client.post('/api/restaurar', json=dict(sid=j['sid'], momento=1))
    ev = historial.listar(orden='asc')
    assert [e['accion'] for e in ev] == ['Analizado', 'Publicado Momentos 1, 2', 'Restaurado Momento 1']
    assert all(e['tipo'] == 'silabos' and e['archivos'] == ['Mi Silabo PE.pdf'] and e['curso_id'] == CURSO_MOCK for e in ev)
    assert ev[0]['curso_nombre'] and ev[1]['resultado'] == 'ok'
    assert [x['texto'] for x in ev[1]['enlaces']] == ['Momento 1', 'Momento 2']
    assert TOKEN not in str(ev)


@con_pdfs
def test_flujo_guias_queda_en_historial(mock):
    with open(PDF_PE, 'rb') as s, open(GUIA, 'rb') as g:
        j = client.post('/api/guias/analizar', data=dict(url=URL, token=TOKEN),
                        files=[('silabo', ('PE.pdf', s.read(), 'application/pdf')),
                               ('guias', ('G3 guia.pdf', g.read(), 'application/pdf'))]).json()
    client.post('/api/guias/generar', json=dict(sid=j['sid'], items=[dict(i=0)]))
    client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True))
    client.post('/api/guias/publicar', json=dict(sid=j['sid'], indices=[0], confirmado=True))   # repetido: no duplica
    client.post('/api/guias/deshacer', json=dict(sid=j['sid'], i=0))
    ev = historial.listar(orden='asc')
    assert [e['accion'] for e in ev] == ['Analizado', 'PAE creadas: PAE3', 'Deshecho: PAE3']
    assert ev[0]['tipo'] == 'guias' and ev[0]['archivos'] == ['G3 guia.pdf'] and 'PE.pdf' in ev[0]['detalle']
    assert ev[1]['resultado'] == 'ok' and {x['texto'] for x in ev[1]['enlaces']} == {'Tarea PAE3', 'Rúbrica PAE3'}


@con_pdfs
def test_error_de_analisis_queda_registrado(mock):
    assert _analizar_silabo(token='malo_0123456789').status_code == 422
    e = historial.listar()[0]
    assert e['resultado'] == 'error' and e['accion'] == 'Analizar' and 'token' in e['detalle'].lower()
    assert 'malo_0123456789' not in str(e) and e['curso_id'] == CURSO_MOCK


@con_pdfs
def test_falla_historial_no_rompe_publicar(mock, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError('disco lleno')
    monkeypatch.setattr(historial, 'registrar', roto)
    j = _analizar_silabo().json()
    client.post('/api/generar', json=dict(sid=j['sid']))
    r = client.post('/api/publicar', json=dict(sid=j['sid'], momentos=[1], confirmado=True))
    assert r.status_code == 200 and r.json()['resultados']['1']['ok']


@con_pdfs
def test_publicar_rechazado_queda_como_error(mock):
    j = _analizar_silabo().json()
    assert client.post('/api/publicar', json=dict(sid=j['sid'], momentos=[1], confirmado=False)).status_code == 409
    e = historial.listar()[0]
    assert e['accion'] == 'Publicar Momento 1' and e['resultado'] == 'error'


# ---------------- Tarea 3: API ----------------
def test_api_listar_y_corregir():
    a = historial.registrar('silabos', 'Publicar Momentos 1', 'error', archivos=['a.pdf'], curso=CURSO, fecha='2026-11-10T10:00')
    historial.registrar('guias', 'PAE creadas: PAE1', 'ok', archivos=['g1.pdf'], curso=dict(id='1', nombre='X'),
                        fecha='2026-11-11T10:00')
    assert client.get('/api/historial/estado').json() == dict(habilitado=True, requiere_clave=False)
    j = client.get('/api/historial').json()
    assert [e['accion'] for e in j['eventos']] == ['PAE creadas: PAE1', 'Publicar Momentos 1']
    assert j['resumen'] == dict(eventos=2, cursos=2, publicaciones=1, errores=1)
    assert {c['id'] for c in j['cursos']} == {'36732', '1'}
    assert len(client.get('/api/historial', params=dict(tipo='silabos', q='A.PDF')).json()['eventos']) == 1
    r = client.post(f'/api/historial/{a}/corregir', json=dict(resultado='ok', nota='<b>sí</b> se publicó'))
    assert r.status_code == 200 and r.json()['correccion']['nota'] == '<b>sí</b> se publicó'
    assert client.get('/api/historial').json()['resumen']['errores'] == 0
    assert client.post(f'/api/historial/{a}/corregir', json=dict(resultado='quizas', nota='')).status_code == 422
    assert client.post('/api/historial/9999/corregir', json=dict(resultado='ok', nota='')).status_code == 404
    assert client.post(f'/api/historial/{a}/corregir', json=dict(resultado='ok', nota='x' * 501)).status_code == 422
    assert client.delete(f'/api/historial/{a}/correccion').json()['correccion'] is None


def test_csv():
    i = historial.registrar('silabos', 'Publicado Momentos 1–4', 'error', archivos=['Sílabo Ñandú.pdf'], curso=CURSO)
    historial.corregir(i, 'ok', 'quedó bien; revisado')
    r = client.get('/api/historial.csv')
    assert r.status_code == 200 and 'text/csv' in r.headers['content-type']
    assert r.content.startswith('\ufeff'.encode('utf-8'))
    lineas = r.content.decode('utf-8-sig').splitlines()
    assert lineas[0].split(';')[:6] == ['fecha', 'tipo', 'archivos', 'curso', 'accion', 'resultado']
    assert 'Sílabo Ñandú.pdf' in lineas[1] and '"quedó bien; revisado"' in lineas[1]


def test_clave_requerida(monkeypatch):
    monkeypatch.setenv('HISTORIAL_CLAVE', 'secreto-123')
    assert client.get('/api/historial/estado').json() == dict(habilitado=True, requiere_clave=True)
    assert client.get('/api/historial').status_code == 401
    assert client.get('/api/historial', headers={'X-Historial-Clave': 'otra'}).status_code == 401
    assert client.get('/api/historial', headers={'X-Historial-Clave': 'secreto-123'}).status_code == 200
    assert client.get('/api/historial.csv', headers={'X-Historial-Clave': 'secreto-123'}).status_code == 200
    assert client.get('/api/historial', params={'clave': 'secreto-123'}).status_code == 401   # nunca en la URL
    assert client.post('/api/historial/1/corregir', json=dict(resultado='ok', nota='')).status_code == 401


def test_apagado_404(monkeypatch):
    monkeypatch.setenv('HISTORIAL', '0')
    assert client.get('/api/historial/estado').json()['habilitado'] is False
    assert client.get('/api/historial').status_code == 404
    assert client.get('/api/historial.csv').status_code == 404


# ---------------- Tarea 4: interfaz ----------------
def test_paginas_tienen_boton_historial():
    for ruta in ('/', '/silabos', '/guias'):
        h = client.get(ruta).text
        assert 'href="historial"' in h and 'Historial' in h, ruta
    h = client.get('/historial').text
    assert client.get('/historial').status_code == 200
    for texto in ('Historial de cargas', 'Exportar CSV', 'Corregir', 'reconstruido', 'api/historial'):
        assert texto in h, texto


def test_fecha_en_blanco_se_respeta():
    i = historial.registrar('silabos', 'Publicado (carga previa al historial)', 'ok', archivos=['x.pdf'], fecha='')
    e = next(x for x in historial.listar() if x['id'] == i)
    assert e['fecha'] == ''


# ---------------- revisión de seguridad ----------------
def test_detras_de_un_proxy_sin_clave_se_cierra():
    """En un servidor (petición que llega por nginx) sin HISTORIAL_CLAVE, el historial no se abre a cualquiera."""
    h = {'X-Forwarded-For': '10.1.2.3'}
    assert client.get('/api/historial', headers=h).status_code == 403
    assert client.get('/api/historial.csv', headers=h).status_code == 403
    assert client.post('/api/historial/1/corregir', json=dict(resultado='ok', nota=''), headers=h).status_code == 403
    assert client.get('/api/historial/estado', headers=h).json() == dict(habilitado=True, requiere_clave=True)
    assert client.get('/api/historial').status_code == 200        # en el propio equipo (sin proxy) sigue abierto


def test_detras_de_un_proxy_con_clave_funciona(monkeypatch):
    monkeypatch.setenv('HISTORIAL_CLAVE', 'secreto-123')
    h = {'X-Forwarded-For': '10.1.2.3', 'X-Historial-Clave': 'secreto-123'}
    assert client.get('/api/historial', headers=h).status_code == 200


def test_csv_neutraliza_formulas():
    historial.registrar('silabos', '=HYPERLINK("http://x","clic")', 'ok', archivos=['+cmd.pdf', '-a.pdf'], curso=CURSO)
    i = historial.registrar('silabos', 'Publicar', 'error', archivos=['@SUM(A1).pdf'])
    historial.corregir(i, 'ok', '=1+1')
    t = client.get('/api/historial.csv').content.decode('utf-8-sig')
    for peligro in ('=HYPERLINK', '+cmd.pdf', '@SUM', '=1+1'):
        assert f";{peligro}" not in t and f';"{peligro}' not in t, peligro
    assert "'=HYPERLINK" in t and "'@SUM(A1).pdf" in t and "'=1+1" in t


def test_sin_clave_y_sin_opcion_local_se_cierra(monkeypatch):
    """Falla cerrado sin depender de cabeceras: sin HISTORIAL_CLAVE ni HISTORIAL_LOCAL=1, nadie lo ve."""
    monkeypatch.delenv('HISTORIAL_LOCAL', raising=False)
    assert client.get('/api/historial').status_code == 403
    assert client.get('/api/historial.csv').status_code == 403
    assert client.post('/api/historial/1/corregir', json=dict(resultado='ok', nota='')).status_code == 403
    assert client.get('/api/historial/estado').json() == dict(habilitado=True, requiere_clave=True)
    monkeypatch.setenv('HISTORIAL_CLAVE', 'secreto-123')          # con clave sí funciona aunque no sea local
    assert client.get('/api/historial', headers={'X-Historial-Clave': 'secreto-123'}).status_code == 200


# ---------------- protecciones extra (dirección pública) ----------------
@pytest.fixture(autouse=True)
def _sin_fallos_previos():
    appmod._FALLOS.clear()
    yield
    appmod._FALLOS.clear()


def test_sin_clave_solo_abre_desde_el_propio_equipo_por_ip(monkeypatch):
    """Sin clave, aunque el puente no agregue cabeceras, una visita desde otra IP (p. ej. el contenedor del puente) no entra."""
    monkeypatch.setattr(appmod, '_ips_locales', lambda: {'127.0.0.1', '::1', '192.168.240.1'})
    puente = TestClient(appmod.app, client=('192.168.240.4', 40000))
    assert puente.get('/api/historial').status_code == 403
    assert puente.get('/api/historial/estado').json()['requiere_clave'] is True
    equipo = TestClient(appmod.app, client=('192.168.240.1', 40000))   # el propio equipo visto desde Docker
    assert equipo.get('/api/historial').status_code == 200


def test_puerta_de_enlace_se_lee_de_la_tabla_de_rutas(tmp_path, monkeypatch):
    rutas = tmp_path / 'route'
    filas = [['Iface', 'Destination', 'Gateway', 'Flags', 'RefCnt', 'Use', 'Metric', 'Mask'],
             ['eth0', '00000000', '01F0A8C0', '0003', '0', '0', '0', '00000000'],     # ruta por defecto
             ['eth0', '00F0A8C0', '00000000', '0001', '0', '0', '0', '00FFFFFF']]
    rutas.write_text(''.join(chr(9).join(f) + chr(10) for f in filas))
    assert appmod._puerta_de_enlace(str(rutas)) == '192.168.240.1'
    assert appmod._puerta_de_enlace(str(tmp_path / 'no-existe')) is None


def test_limita_intentos_fallidos_de_clave(monkeypatch):
    monkeypatch.setenv('HISTORIAL_CLAVE', 'secreto-123')
    h = lambda k: {'X-Historial-Clave': k, 'X-Forwarded-For': '203.0.113.9'}
    for _ in range(appmod._MAX_FALLOS):
        assert client.get('/api/historial', headers=h('mala')).status_code == 401
    r = client.get('/api/historial', headers=h('secreto-123'))
    assert r.status_code == 429 and 'intentos' in r.json()['detail']     # bloqueado aunque ahora acierte
    otro = {'X-Historial-Clave': 'secreto-123', 'X-Forwarded-For': '198.51.100.7'}
    assert client.get('/api/historial', headers=otro).status_code == 200  # otra persona no queda bloqueada


def test_el_limite_usa_la_ip_que_agrega_el_proxy(monkeypatch):
    """Cambiar la primera IP de X-Forwarded-For (la que inventa el cliente) no salta el límite."""
    monkeypatch.setenv('HISTORIAL_CLAVE', 'secreto-123')
    for i in range(appmod._MAX_FALLOS):
        client.get('/api/historial', headers={'X-Historial-Clave': 'mala', 'X-Forwarded-For': f'10.0.0.{i}, 203.0.113.9'})
    r = client.get('/api/historial', headers={'X-Historial-Clave': 'secreto-123', 'X-Forwarded-For': '10.9.9.9, 203.0.113.9'})
    assert r.status_code == 429


def test_limite_global_de_fallos(monkeypatch):
    monkeypatch.setenv('HISTORIAL_CLAVE', 'secreto-123')
    for i in range(appmod._MAX_FALLOS_TOTAL):
        client.get('/api/historial', headers={'X-Historial-Clave': 'mala', 'X-Forwarded-For': f'203.0.113.{i}'})
    r = client.get('/api/historial', headers={'X-Historial-Clave': 'secreto-123', 'X-Forwarded-For': '198.51.100.200'})
    assert r.status_code == 429


def test_sin_clave_escrita_no_cuenta_como_fallo(monkeypatch):
    monkeypatch.setenv('HISTORIAL_CLAVE', 'secreto-123')
    for _ in range(appmod._MAX_FALLOS + 2):
        assert client.get('/api/historial').status_code == 401
    assert client.get('/api/historial', headers={'X-Historial-Clave': 'secreto-123'}).status_code == 200


def test_pagina_permite_olvidar_la_clave():
    h = client.get('/historial').text
    assert 'id="bolvidar"' in h and 'Olvidar la clave en este equipo' in h

