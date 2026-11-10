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
                       'cuerpo_bibliografia', 'tabla_rubrica', 'celda_pis', 'sesiones_vacias'])
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
