"""Estructura del HTML, aislamiento documental y contexto independiente de Qwen."""
import copy
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod
from core import propuestas, render, silabo
from ia import documento, extractor, qwen, trabajo, vectores

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CURSO = dict(host='indoamerica.instructure.com', id='12345', slug='inicio')


@pytest.fixture(scope='module')
def documentos():
    return [silabo.leer(os.path.join(ROOT, p)) for p in (
        'B26_Software_Programacion Estructurada.pdf',
        'silabos_prueba/silabo_pf20261106_165315med-paral_02.pdf')]


def generar(sil, tpl):
    prop = propuestas.proponer(sil)
    return render.render(sil, 1, tpl, CURSO, prop['propositos'][1], prop['complementaria'][1])


def test_html_descarta_bloques_ajenos_y_conserva_composicion(documentos):
    tpl = render.leer_plantilla_institucional()
    vieja = BeautifulSoup(tpl, 'html.parser')
    bibliografia = vieja.find_all('table', recursive=False)[-1]
    bibliografia.find('tbody').find('td').append('Proyecto Interdisciplinario: MARCADOR_ANTERIOR. Fecha Inicio: contenido ajeno.')
    sucia = '<p>MARCADOR_SILABO_ANTERIOR</p>' + str(vieja) + '<table><tr><td>EXTRA_ANTERIOR</td></tr></table>'
    limpio = BeautifulSoup(generar(documentos[0], tpl), 'html.parser')
    resultado = BeautifulSoup(generar(documentos[0], sucia), 'html.parser')
    assert resultado.get_text() == limpio.get_text()
    assert [t.get('style') for t in resultado.find_all(True)] == [t.get('style') for t in limpio.find_all(True)]


def test_plantilla_publicada_no_reutiliza_contenido_del_silabo_anterior(documentos):
    a, b = copy.deepcopy(documentos)
    tpl = render.leer_plantilla_institucional()
    previo = generar(a, tpl)
    esperado = BeautifulSoup(generar(b, tpl), 'html.parser').get_text(' ', strip=True)
    actual = BeautifulSoup(generar(b, previo), 'html.parser').get_text(' ', strip=True)
    assert actual == esperado


def test_rubrica_no_arrastra_textos_fuera_del_span_de_la_plantilla(documentos):
    tpl = render.leer_plantilla_institucional()
    soup = BeautifulSoup(tpl, 'html.parser')
    tabla = soup.find('details').find('table')
    filas = tabla.find_all('tr')
    cab = next(i for i, f in enumerate(filas) if f.find(['th', 'td']).get_text(strip=True) == 'Indicador')
    for fila in filas[cab + 1:]:
        for celda in fila.find_all(['th', 'td'], recursive=False):
            extra = soup.new_tag('p')
            extra.string = 'TEXTO_RESIDUAL_DE_OTRO_SILABO'
            celda.append(extra)
    esperado = BeautifulSoup(generar(documentos[0], tpl), 'html.parser').get_text(' ', strip=True)
    actual = BeautifulSoup(generar(documentos[0], str(soup)), 'html.parser').get_text(' ', strip=True)
    assert actual == esperado


@pytest.mark.parametrize('ruta', ['/', '/api/salud'])
def test_respuestas_no_se_guardan_en_cache(ruta, monkeypatch):
    from ia import salud
    monkeypatch.setattr(salud, 'estado', lambda: {'reglas': 'ok'})
    respuesta = TestClient(appmod.app).get(ruta)
    assert 'no-store' in respuesta.headers.get('cache-control', '')


def test_vectores_aislan_documentos_incluso_con_embeddings_identicos(monkeypatch):
    monkeypatch.setattr(vectores, 'embed', lambda textos: [[1.0, 0.0, 0.0] for _ in textos])
    alm = vectores.Almacen(url='')
    try:
        for sid in ('DOCUMENTO_A', 'DOCUMENTO_B'):
            alm.indexar(sid, [dict(id=0, texto=sid, bloque='bibliografia', momento=1)])
        def consultar(sid):
            assert [f['texto'] for f in alm.bloques(sid, 'bibliografia', 1)] == [sid]
            assert [f['texto'] for f in alm.buscar(sid, 'bibliografia')] == [sid]
            return sid
        with ThreadPoolExecutor(max_workers=2) as ex:
            assert list(ex.map(consultar, ('DOCUMENTO_A', 'DOCUMENTO_B'))) == ['DOCUMENTO_A', 'DOCUMENTO_B']
        alm.borrar('DOCUMENTO_A')
        assert alm.bloques('DOCUMENTO_A', 'bibliografia', 1) == []
        consultar('DOCUMENTO_B')
        alm.borrar('DOCUMENTO_B')
        assert alm.cli.count(vectores.COLECCION).count == 0
    finally:
        alm.cli.close()


def test_cliente_qwen_no_envia_historial_entre_peticiones(monkeypatch):
    llamadas = []
    def crear(**kw):
        llamadas.append(copy.deepcopy(kw['messages']))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"codigo":"ok"}'), finish_reason='stop')],
                               usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))
    monkeypatch.setattr(qwen, 'cliente', lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear))))
    monkeypatch.setattr(qwen, 'contar_tokens', lambda t: 10)
    esquema = {'type': 'object', 'properties': {'codigo': {'type': 'string'}}, 'required': ['codigo']}
    for sid in ('DOCUMENTO_A', 'DOCUMENTO_B', 'DOCUMENTO_A'):
        qwen.json_con_esquema('Extrae solo el documento activo.', sid, esquema)
    assert [m[1]['content'] for m in llamadas] == ['DOCUMENTO_A', 'DOCUMENTO_B', 'DOCUMENTO_A']
    assert all(len(m) == 2 and [x['role'] for x in m] == ['system', 'user'] for m in llamadas)


@pytest.mark.parametrize('falla', [False, True])
def test_mismo_pdf_simultaneo_tiene_contextos_distintos_y_se_borra(monkeypatch, falla):
    monkeypatch.setattr(vectores, 'embed', lambda textos: [[1.0, 0.0, 0.0] for _ in textos])
    alm = vectores.Almacen(url='')
    monkeypatch.setattr(trabajo, '_almacen', lambda: alm)
    monkeypatch.setattr(documento, 'fragmentos', lambda p: [dict(id=0, texto='DOCUMENTO_ACTIVO', bloque='ra', momento=None)])
    barrera = threading.Barrier(2)
    ids, rutas = [], []
    sil = dict(ficha={}, momentos=[], ra={}, pis={}, bibliografia={'basica': [], 'complementaria': []})
    def extraer(alm, sid, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None):
        ids.append(sid)
        rutas.append(pdf_path)
        barrera.wait(timeout=10)
        assert [f['texto'] for f in alm.bloques(sid, 'ra')] == ['DOCUMENTO_ACTIVO']
        if falla:
            raise RuntimeError('Fallo simulado de extracción')
        return copy.deepcopy(sil), dict(errores=[], tareas=1)
    monkeypatch.setattr(extractor, 'extraer', extraer)
    sesiones = [dict(silabo=copy.deepcopy(sil), ia={}) for _ in range(2)]
    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(lambda s: trabajo._correr(s, b'%PDF-documento-igual'), sesiones))
        assert len(set(ids)) == 2
        assert all(s['ia']['estado'] == ('error' if falla else 'listo') for s in sesiones)
        assert alm.cli.count(vectores.COLECCION).count == 0
        assert all(not os.path.exists(p) for p in rutas)
    finally:
        alm.cli.close()


@pytest.mark.qwen
@pytest.mark.parametrize('modo', ['consecutivo', 'simultaneo', 'contexto_largo'])
def test_qwen_real_respeta_contexto_independiente(modo):
    if not qwen.disponible():
        pytest.skip('servidor Qwen no disponible')
    esquema = {'type': 'object', 'properties': {'codigo': {'type': 'string'}, 'titulo': {'type': 'string'}},
               'required': ['codigo', 'titulo'], 'additionalProperties': False}
    datos = [('CTX-ANT-7631', 'Antropología médica'), ('CTX-PRO-9284', 'Programación estructurada')]
    def extraer(dato):
        codigo, titulo = dato
        relleno = ('Nota de formato sin datos bibliográficos.\n' * 600) if modo == 'contexto_largo' else ''
        usuario = f'<documento>\nCódigo: {codigo}\n{relleno}Título: {titulo}\n</documento>'
        salida, met = qwen.json_con_esquema('Extrae únicamente el código y el título literales del documento activo. No inventes datos.',
                                           usuario, esquema, max_tokens=150)
        assert salida == {'codigo': codigo, 'titulo': titulo}
        assert met['entrada'] + met['salida'] <= qwen.contexto()
    if modo == 'simultaneo':
        with ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(extraer, datos))
    else:
        for dato in datos + datos[:1]:
            extraer(dato)
