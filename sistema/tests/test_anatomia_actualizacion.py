"""Regresiones del sílabo de Anatomía y de páginas de Canvas ya completadas."""
import sys
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import render, servicio, silabo
from mock_canvas import MockCanvas, TOKEN

PDF = Path(__file__).parent / 'fixtures' / 'anatomia_general_b26.pdf'
URL = 'https://indoamerica.instructure.com/courses/36254'


def sesion(plantilla):
    mock = MockCanvas(plantilla_body=plantilla)
    return servicio.analizar(str(PDF), URL, TOKEN, transport=httpx.MockTransport(mock.handler)), mock


def test_anatomia_incluye_cinco_complementarias_por_momento():
    s, mock = sesion(render.leer_plantilla_institucional())
    assert len(s['silabo']['bibliografia']['basica']) == 2
    assert len(s['silabo']['bibliografia']['complementaria']) == 5
    servicio.generar(s)
    for n, html in s['paginas'].items():
        tabla = render._bloques(BeautifulSoup(html, 'html.parser'))['biblio']
        ps = tabla.find('tbody').find_all('td')[1].find_all('p')
        assert len(ps) == 5
        assert [p.find('a')['href'] for p in ps] == [
            'https://cienciasbasicas.lwwhealthlibrary.com/book.aspx?bookid=3079',
            'https://cienciasbasicas.lwwhealthlibrary.com/book.aspx?bookid=3226',
            'https://elibro.net/es/ereader/utiec/125453?page=101',
            'https://elibro.net/es/ereader/utiec/125884?page=39',
            'https://cienciasbasicas.lwwhealthlibrary.com/book.aspx?bookid=2890',
        ]
        assert all(c['ok'] for c in s['control'][n] if c['bloquea'])
    assert servicio.publicar(s, [1, 2], confirmado=True)[1]['ok']
    assert len(mock.puts) == 2


def test_anatomia_fecha_consulta_no_forma_parte_de_url():
    obra = silabo.leer(str(PDF))['bibliografia']['complementaria'][3]
    assert obra['url'] == 'https://elibro.net/es/ereader/utiec/125884?page=39'
    assert 'Consultado en: 25 Sep 2025' in obra['texto']


@pytest.mark.parametrize('variante', ['duplicadas', 'parrafos'])
def test_republicar_momentos_1_y_2_elimina_fechas_anteriores(variante):
    tpl = BeautifulSoup(render.leer_plantilla_institucional(), 'html.parser')
    cab = render._bloques(tpl)['encabezado'].find('thead').find('th')
    if variante == 'duplicadas':
        cab.append(BeautifulSoup('<span>Fecha Inicio: 1 de enero de 2001</span><span>Fecha Fin: 2 de enero de 2001</span>', 'html.parser'))
    else:
        cab.clear()
        cab.append(BeautifulSoup('Momento 1: ANTERIOR<p>Fecha Inicio: 1 de enero de 2001<br>Fecha Fin: 2 de enero de 2001</p>', 'html.parser'))
    primera = render._bloques(tpl)['sesiones'].find('tbody').find('th')
    primera.append(BeautifulSoup('<span>Fecha: 01/01/2001 al 02/01/2001</span>', 'html.parser'))
    s, mock = sesion(str(tpl))
    servicio.generar(s)
    for n in (1, 2):
        html = s['paginas'][n]
        assert '2001' not in BeautifulSoup(html, 'html.parser').get_text()
        cab = render._bloques(BeautifulSoup(html, 'html.parser'))['encabezado'].find('thead')
        assert cab.get_text().count('Fecha Inicio:') == 1
        assert cab.get_text().count('Fecha Fin:') == 1
        assert all(c['ok'] for c in s['control'][n] if c['bloquea'])
    resultado = servicio.publicar(s, [1, 2], confirmado=True)
    assert all(r['ok'] for r in resultado.values())
    for n in (1, 2):
        body = mock.paginas[s['destinos'][n]['slug']]['body']
        assert '2001' not in BeautifulSoup(body, 'html.parser').get_text()
    assert '2001' in s['respaldos'][1]
    assert servicio.restaurar(s, 1)['restaurada']
    assert '2001' in mock.paginas[s['destinos'][1]['slug']]['body']
