# -*- coding: utf-8 -*-
"""Pruebas de extremo a extremo del sistema contra un Canvas SIMULADO (nunca un Canvas real).

    python -m pytest sistema/tests -v
"""
import glob
import io
import json
import os
import re
import sys
import zipfile

import httpx
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod  # noqa: E402
from core import canvas, render, servicio  # noqa: E402
from mock_canvas import CURSO, TOKEN, MockCanvas  # noqa: E402

PDF = glob.glob(os.path.join(ROOT, '*.pdf'))[0]
URL = f'https://indoamerica.instructure.com/courses/{CURSO}'
client = TestClient(appmod.app)


@pytest.fixture
def mock(monkeypatch):
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    monkeypatch.setattr(appmod, 'TRANSPORT', httpx.MockTransport(m.handler))
    return m


def usar(monkeypatch, m):
    monkeypatch.setattr(appmod, 'TRANSPORT', httpx.MockTransport(m.handler))
    return m


def analizar(url=URL, token=TOKEN, data=None):
    return client.post('/api/analizar', data={'url': url, 'token': token},
                       files={'pdf': ('silabo.pdf', data if data is not None else open(PDF, 'rb').read(), 'application/pdf')})


def generar(sid, **kw):
    return client.post('/api/generar', json={'sid': sid, **kw}).json()


def publicar(sid, momentos=(1, 2, 3, 4), confirmado=True):
    return client.post('/api/publicar', json={'sid': sid, 'momentos': list(momentos), 'confirmado': confirmado})


def pdf_minimo(texto='Hola'):
    objs = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
            None, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    stream = f'BT /F1 12 Tf 20 200 Td ({texto}) Tj ET'
    objs[3] = f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream'
    out, offs = b'%PDF-1.4\n', []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += f'{i} 0 obj\n{o}\nendobj\n'.encode()
    x = len(out)
    out += f'xref\n0 {len(objs)+1}\n0000000000 65535 f \n'.encode() + b''.join(f'{o:010d} 00000 n \n'.encode() for o in offs)
    out += f'trailer << /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF'.encode()
    return out


def plantilla_vacia(sin_proposito=False, curso='11111'):
    """Página Momento de un aula nueva: misma plantilla con marcadores y botón de otro curso."""
    soup = BeautifulSoup(render.leer_plantilla_institucional(), 'html.parser')
    for a in soup.find_all('a'):
        for k in ('href', 'data-api-endpoint'):
            if a.get(k):
                a[k] = re.sub(r'/courses/\d+', f'/courses/{curso}', a[k])
    enc = soup.find_all(['table', 'details'], recursive=False)[1]
    th = enc.find('thead').find('th')
    th.contents[0].replace_with('TÍTULO DEL MOMENTO')
    for sp in th.find_all('span'):
        for c in sp.contents:
            if isinstance(c, str) and 'Fecha' in c:
                c.replace_with(c.split(':')[0] + ': [Día, Mes, Año]')
    for td in soup.find_all('td'):
        if td.find('span') is None and td.find('p') is None and td.find('a') is None:
            td.string = '(Copiar y pegar del sílabo)'
    for p in soup.find_all('p'):
        if p.find('a') is None and p.find('span') is None:
            p.string = '(Copiar y pegar del sílabo)'
    if sin_proposito:
        filas = enc.find('tbody').find_all('tr', recursive=False)
        filas[2].decompose(); filas[3].decompose()
    return str(soup)


# ---------------- flujo completo ----------------
def test_flujo_completo_publica_verifica_y_restaura(mock):
    r = analizar(); assert r.status_code == 200, r.text
    j = r.json()
    assert TOKEN not in json.dumps(j), 'el token nunca vuelve al navegador'
    assert j['curso']['id'] == CURSO and j['curso']['url_inicio'].endswith(f'/courses/{CURSO}/pages/inicio')
    assert {int(k): v['fuente'] for k, v in j['destinos'].items()} == {n: 'página de inicio' for n in (1, 2, 3, 4)}
    assert any(a['tipo'] == 'Curso' and a['grave'] for a in j['advertencias'])  # sílabo de otro PF que el curso
    g = generar(j['sid']); assert g['listo'], g['control']
    p = publicar(j['sid']).json()['resultados']
    assert all(v['ok'] for v in p.values()), p
    assert mock.puts == ['momento-1-2', 'momento-2', 'momento-3', 'momento-4']
    assert mock.paginas['recursos-1']['body'] == '<p>r</p>'  # nada más se toca
    cuerpo = mock.paginas['momento-3']['body']
    assert 'Momento 3:' in BeautifulSoup(cuerpo, 'html.parser').get_text()
    assert f'/courses/{CURSO}/pages/inicio' in cuerpo and '36283' not in cuerpo
    # restaurar
    rr = client.post('/api/restaurar', json={'sid': j['sid'], 'momento': 2}).json()
    assert rr['restaurada'] and mock.paginas['momento-2']['body'] == render.leer_plantilla_institucional()
    # ZIP con respaldo e informe
    z = zipfile.ZipFile(io.BytesIO(client.get(f'/api/descargar/{j["sid"]}').content))
    assert 'B26_Programacion_Estructurada/respaldo/momento-1-anterior.html' in z.namelist()
    assert 'Publicada y verificada' in z.read('B26_Programacion_Estructurada/informe.html').decode()
    # terminar borra la sesión y el token
    sid = j['sid']
    assert client.post(f'/api/terminar/{sid}').json()['ok']
    assert sid not in appmod._sesiones and client.post('/api/generar', json={'sid': sid}).status_code == 404


def test_ediciones_del_docente_se_publican(mock):
    j = analizar().json()
    obras = [o['url'] for o in j['obras']]
    prop = 'Aplicar la recursividad a los datos del caso mediante ejercicios guiados.'
    g = generar(j['sid'], propositos={'1': prop}, complementaria={'1': [obras[0], obras[5]]})
    assert g['listo']
    publicar(j['sid'], [1])
    s = BeautifulSoup(mock.paginas['momento-1-2']['body'], 'html.parser')
    assert prop in s.get_text()
    td = s.find_all('table', recursive=False)[4].find('tbody').find_all('td')[1]
    assert [a['href'] for a in td.find_all('a')] == [obras[0], obras[5]]
    assert mock.puts == ['momento-1-2']


def test_salida_igual_a_la_validada_en_html(monkeypatch):
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    s = servicio.analizar(PDF, URL, TOKEN, transport=httpx.MockTransport(m.handler))
    prop, comp = {}, {}
    for n in (1, 2, 3, 4):
        t = BeautifulSoup(open(os.path.join(ROOT, 'html', f'momento-{n}.html'), encoding='utf-8').read(),
                          'html.parser').find_all('table', recursive=False)
        prop[str(n)] = t[1].find('tbody').find_all('tr')[3].get_text(' ', strip=True)
        comp[str(n)] = [a['href'] for a in t[4].find('tbody').find_all('td')[1].find_all('a')]
    servicio.generar(s, prop, comp)
    norm = lambda h: re.sub(r'\s+', ' ', BeautifulSoup(h, 'html.parser').get_text(' ')).strip()
    for n in (1, 2, 3, 4):
        ref = open(os.path.join(ROOT, 'html', f'momento-{n}.html'), encoding='utf-8').read()
        assert norm(s['paginas'][n]) == norm(ref), n


# ---------------- seguridad y aprobación ----------------
def test_sin_confirmacion_no_se_publica(mock):
    j = analizar().json(); generar(j['sid'])
    r = publicar(j['sid'], confirmado=False)
    assert r.status_code == 409 and mock.puts == []


def test_cliente_rechaza_escritura_sin_aprobacion(mock):
    cv = canvas.Canvas(canvas.curso_desde_url(URL), TOKEN, httpx.MockTransport(mock.handler))
    with pytest.raises(PermissionError):
        cv.actualizar_cuerpo('momento-2', '<p>x</p>')
    assert mock.puts == []


def test_fallo_de_control_informa_pero_permite_publicar_con_confirmacion(mock, monkeypatch):
    j = analizar().json()
    original = render.render

    def roto(*a, **k):  # intercambia columnas → la lista de control debe fallar
        h = original(*a, **k)
        return h.replace('Actividades de trabajo aut&oacute;nomo', '@@').replace(
            'Actividades pr&aacute;ctico-experimentales', 'Actividades de trabajo aut&oacute;nomo').replace(
            '@@', 'Actividades pr&aacute;ctico-experimentales')
    monkeypatch.setattr(render, 'render', roto)
    g = generar(j['sid'])
    assert any(not i['ok'] and i['bloquea'] for items in g['control'].values() for i in items)
    assert g['listo'] is True
    assert publicar(j['sid'], confirmado=False).status_code == 409 and mock.puts == []
    assert publicar(j['sid']).status_code == 200 and len(mock.puts) == 4
    assert client.get(f'/api/descargar/{j["sid"]}').status_code == 200


def test_html_no_generado_sigue_sin_publicarse(mock, monkeypatch):
    j = analizar().json()

    def no_generar(*a, **k):
        raise ValueError('No se pudo generar la página')

    monkeypatch.setattr(render, 'render', no_generar)
    assert generar(j['sid'])['listo'] is False
    assert publicar(j['sid']).status_code == 409 and mock.puts == []


def test_error_de_canvas_en_una_pagina_no_detiene_las_demas(mock):
    mock.fallar_put.add('momento-3')
    j = analizar().json(); generar(j['sid'])
    p = publicar(j['sid']).json()['resultados']
    assert p['3']['ok'] is False and 'No se publicó' in p['3']['mensaje']
    assert all(p[k]['ok'] for k in ('1', '2', '4'))


# ---------------- errores de entrada ----------------
@pytest.mark.parametrize('url', ['', 'https://indoamerica.instructure.com/courses/abc',
                                 'https://google.com/courses/1', 'http://indoamerica.instructure.com/courses/1',
                                 'https://evil.com/courses/36254'])
def test_url_invalida(mock, url):
    r = analizar(url=url)
    assert r.status_code == 422 and 'URL' in r.json()['detail']


def test_token_invalido(mock):
    r = analizar(token='token-equivocado-123456789')
    assert r.status_code == 422 and 'token' in r.json()['detail'].lower()


def test_sin_token(mock):
    r = analizar(token='')
    assert r.status_code == 422 and 'token' in r.json()['detail'].lower()


def test_curso_inexistente(mock):
    r = analizar(url='https://indoamerica.instructure.com/courses/99999')
    assert r.status_code == 422 and 'URL del curso' in r.json()['detail']


def test_archivo_que_no_es_pdf(mock):
    r = analizar(data=b'hola, no soy un pdf')
    assert r.status_code == 422 and 'PDF' in r.json()['detail']


def test_pdf_que_no_es_silabo(mock):
    r = analizar(data=pdf_minimo())
    assert r.status_code == 422 and 'MOMENTOS' in r.json()['detail']


# ---------------- variantes del curso ----------------
def test_paginas_vacias_del_aula_usan_su_propia_plantilla(monkeypatch):
    m = usar(monkeypatch, MockCanvas(plantilla_body=plantilla_vacia()))
    j = analizar().json()
    assert all(d['plantilla'] == 'la página actual del curso' for d in j['destinos'].values())
    g = generar(j['sid']); assert g['listo'], {k: [i for i in v if not i['ok']] for k, v in g['control'].items()}
    publicar(j['sid'])
    for slug in ('momento-1-2', 'momento-2', 'momento-3', 'momento-4'):
        b = m.paginas[slug]['body']
        assert 'Copiar y pegar' not in b and '[Día' not in b and '11111' not in b and f'/courses/{CURSO}/' in b


def test_pagina_sin_proposito_se_respeta(monkeypatch):
    m = usar(monkeypatch, MockCanvas(plantilla_body=plantilla_vacia(sin_proposito=True)))
    j = analizar().json()
    assert all(not mm['proposito'] for mm in j['momentos'])
    g = generar(j['sid']); assert g['listo']
    assert all('Propósito del momento' not in BeautifulSoup(h, 'html.parser').get_text() for h in g['paginas'].values())


def test_pagina_con_otra_estructura_usa_la_institucional(monkeypatch):
    usar(monkeypatch, MockCanvas(plantilla_body='<p>Página en construcción</p>'))
    j = analizar().json()
    assert all(d['plantilla'] == 'institucional' for d in j['destinos'].values())
    assert any('plantilla institucional' in a['texto'] for a in j['advertencias'])
    assert generar(j['sid'])['listo']


def test_momento_sin_pagina_no_se_publica(monkeypatch):
    m = usar(monkeypatch, MockCanvas(plantilla_body=render.leer_plantilla_institucional(), sin=(3,)))
    j = analizar().json()
    assert '3' not in j['destinos']
    assert any(a['tipo'] == 'Canvas' and 'Momento 3' in a['texto'] for a in j['advertencias'])
    generar(j['sid'])
    p = publicar(j['sid'], [1, 2, 3, 4]).json()['resultados']
    assert p['3']['ok'] is False and 'momento-3' not in m.puts and len(m.puts) == 3


def test_localiza_por_modulo_si_el_inicio_no_enlaza(monkeypatch):
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    m.paginas['inicio']['body'] = '<p>Sin mosaicos</p>'
    usar(monkeypatch, m)
    j = analizar().json()
    assert {int(k): (v['fuente'], v['titulo']) for k, v in j['destinos'].items()} == \
        {n: ('módulo', f'Momento {n}') for n in (1, 2, 3, 4)}


def test_pagina_principal():
    r = client.get('/')
    assert r.status_code == 200 and 'Token de acceso de Canvas' in r.text
    for texto in ('Revisar también con la IA de la universidad', 'Segunda lectura (IA)', 'Volver al inicio', 'Cargar otro curso'):
        assert texto in r.text, texto
