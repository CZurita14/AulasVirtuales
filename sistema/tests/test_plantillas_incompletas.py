"""Páginas con bloques reconocibles pero tablas incompletas no deben romper la vista previa."""
import copy
import sys
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import render, servicio, silabo
from mock_canvas import MockCanvas, TOKEN


@pytest.fixture(params=['sin_tbody', 'cabecera_sesiones', 'cuerpo_encabezado',
                       'cuerpo_bibliografia', 'tabla_rubrica', 'celda_pis', 'sesiones_vacias',
                       'sin_columna_enlaces'])
def incompleta(request):
    soup = BeautifulSoup(render.leer_plantilla_institucional(), 'html.parser')
    b = render._bloques(soup)
    if request.param == 'sin_tbody':
        for t in soup.find_all('tbody'):
            t.unwrap()
    elif request.param == 'cabecera_sesiones':
        b['sesiones'].find('thead').unwrap()
    elif request.param == 'cuerpo_encabezado':
        b['encabezado'].find('tbody').unwrap()
    elif request.param == 'cuerpo_bibliografia':
        b['biblio'].find('tbody').unwrap()
    elif request.param == 'tabla_rubrica':
        b['rubrica'].find('table').unwrap()
    elif request.param == 'celda_pis':
        b['pis'].find('td').unwrap()
    elif request.param == 'sin_columna_enlaces':      # la última casilla del modelo borrada por accidente
        for tr in b['sesiones'].find_all('tr'):
            celdas = tr.find_all(['th', 'td'], recursive=False)
            if len(celdas) > 1:
                celdas[-1].decompose()
    else:
        b['sesiones'].find('tbody').clear()
    return str(soup)


@pytest.fixture(scope='module', params=['programacion', 'anatomia', 'integracion'])
def documento(request):
    raiz = Path(__file__).resolve().parents[2]
    rutas = {
        'programacion': raiz / 'B26_Software_Programacion Estructurada.pdf',
        'anatomia': Path(__file__).parent / 'fixtures' / 'anatomia_general_b26.pdf',
        'integracion': Path(__file__).parent / 'fixtures' / 'integracion.pdf',
    }
    return silabo.leer(str(rutas[request.param]))


def test_detecta_estructura_incompleta_antes_de_generar(incompleta):
    info = render.analizar_plantilla(incompleta)
    assert not info['valida']
    assert info['faltan']


def test_vista_previa_y_publicacion_usan_plantilla_segura(incompleta, documento, monkeypatch):
    monkeypatch.setattr(silabo, 'leer', lambda _: copy.deepcopy(documento))
    mock = MockCanvas(plantilla_body=incompleta)
    s = servicio.analizar('documento.pdf', 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                          transport=httpx.MockTransport(mock.handler))
    servicio.generar(s)
    assert s['listo'], s['control']
    assert all(v == 'institucional' for v in s['plantilla_origen'].values())
    assert any('plantilla institucional' in a['texto'] for a in s['advertencias'])
    assert all(c['ok'] for items in s['control'].values() for c in items if c['bloquea'])
    assert mock.puts == []
    assert all(r['ok'] for r in servicio.publicar(s, [1], confirmado=True).values())
    assert s['respaldos'][1] == incompleta


def test_solo_momento_1_incompleto_conserva_plantillas_de_los_demas(documento, monkeypatch):
    monkeypatch.setattr(silabo, 'leer', lambda _: copy.deepcopy(documento))
    valida = render.leer_plantilla_institucional()
    rota = BeautifulSoup(valida, 'html.parser')
    render._bloques(rota)['sesiones'].find('thead').unwrap()
    mock = MockCanvas(plantilla_body=valida)
    mock.paginas['momento-1-2']['body'] = str(rota)
    s = servicio.analizar('documento.pdf', 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                          transport=httpx.MockTransport(mock.handler))
    assert s['plantilla_origen'][1] == 'institucional'
    for n in (2, 3, 4):
        assert s['plantilla_origen'][n] == 'la página actual del curso'
        assert s['plantillas'][n] == valida
    servicio.generar(s)
    assert s['listo']
    assert all(c['ok'] for items in s['control'].values() for c in items if c['bloquea'])
    assert mock.puts == []
    assert servicio.publicar(s, [1], confirmado=True)[1]['ok']
    assert mock.puts == ['momento-1-2']
    assert s['respaldos'][1] == str(rota)
    for n in (2, 3, 4):
        assert mock.paginas[f'momento-{n}']['body'] == valida


def test_falta_columna_enlaces_se_nombra_en_el_aviso(documento, monkeypatch):
    monkeypatch.setattr(silabo, 'leer', lambda _: copy.deepcopy(documento))
    soup = BeautifulSoup(render.leer_plantilla_institucional(), 'html.parser')
    for tr in render._bloques(soup)['sesiones'].find_all('tr'):
        celdas = tr.find_all(['th', 'td'], recursive=False)
        if len(celdas) > 1:
            celdas[-1].decompose()
    assert 'sesiones: falta la columna "Enlaces"' in render.analizar_plantilla(str(soup))['faltan']
    mock = MockCanvas(plantilla_body=str(soup))
    s = servicio.analizar('documento.pdf', 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                          transport=httpx.MockTransport(mock.handler))
    assert any('falta la columna "Enlaces"' in a['texto'] for a in s['advertencias'])
    servicio.generar(s)
    for h in s['paginas'].values():
        assert '>Enlaces</th>' in h and render.MARCA_ENLACE in h


def test_enlaces_del_docente_se_conservan_al_volver_a_publicar(documento):
    from core import propuestas
    sil = copy.deepcopy(documento)
    curso = dict(host='indoamerica.instructure.com', id='36254', slug='inicio')
    prop = propuestas.proponer(sil)
    n = sil['momentos'][0]['n']
    h1 = render.render(sil, n, render.leer_plantilla_institucional(), curso, prop['propositos'][n], prop['complementaria'][n])
    soup = BeautifulSoup(h1, 'html.parser')
    filas = render._bloques(soup)['sesiones'].find('tbody').find_all('tr', recursive=False)
    filas[0].find_all(['th', 'td'], recursive=False)[-1].string = ''
    filas[0].find_all(['th', 'td'], recursive=False)[-1].append(
        BeautifulSoup('<a href="https://zoom.us/j/123">Clase 1</a>', 'html.parser'))
    h2 = render.render(sil, n, str(soup), curso, prop['propositos'][n], prop['complementaria'][n])
    filas2 = render._bloques(BeautifulSoup(h2, 'html.parser'))['sesiones'].find('tbody').find_all('tr', recursive=False)
    assert filas2[0].find('a', href='https://zoom.us/j/123') is not None
    if len(filas2) > 1:
        assert filas2[1].find_all(['th', 'td'], recursive=False)[-1].get_text(strip=True) == render.MARCA_ENLACE
