# -*- coding: utf-8 -*-
"""Pruebas de los HTML "Momento N" contra el sílabo, según las reglas de PROMPT_MAESTRO_Silabo_a_Canvas.md.

Ejecutar desde la carpeta del proyecto:
    python -m pytest tests -v
Variables opcionales:
    SILABO_PDF   ruta del sílabo (por defecto el único .pdf de la carpeta)
    CURSO_URL    URL de la página Inicio del curso (por defecto el curso 36283)
    HTML_DIR     carpeta de los HTML (por defecto html/)
"""
import glob
import html as htmlmod
import os
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import pytest
from bs4 import BeautifulSoup, NavigableString

import silabo_parser as sp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.environ.get('SILABO_PDF') or glob.glob(os.path.join(ROOT, '*.pdf'))[0]
CURSO_URL = os.environ.get('CURSO_URL', 'https://indoamerica.instructure.com/courses/36283/pages/inicio')
HTML_DIR = os.environ.get('HTML_DIR', os.path.join(ROOT, 'html'))
FIXTURE = os.path.join(ROOT, 'tests', 'fixtures', 'momento1_aprobado.html')

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']
ALLOWED = {'table', 'thead', 'tbody', 'tr', 'th', 'td', 'details', 'summary', 'p', 'span', 'strong', 'em', 'a', 'br'}
MARCADORES = ['(Copiar y pegar', '[Día, Mes, Año]', 'TÍTULO DEL MOMENTO', '[Apellido']

SILABO = sp.parse(PDF)
MOMENTOS = {m['n']: m for m in SILABO['momentos']}
NS = sorted(MOMENTOS)


def norm(s):
    return re.sub(r'\s+', ' ', htmlmod.unescape(s).replace('\xa0', ' ')).strip()


def larga(ddmmyyyy):
    d, m, y = ddmmyyyy.split('/')
    return f'{int(d)} de {MESES[int(m) - 1]} de {y}'


def own_text(tag):
    return norm(''.join(str(s) for s in tag.contents if isinstance(s, NavigableString)))


def style_set(soup):
    return {re.sub(r'\s+', ' ', t['style'].lower()).strip().rstrip(';') for t in soup.find_all(style=True)}


@pytest.fixture(scope='module', params=NS, ids=[f'momento-{n}' for n in NS])
def page(request):
    n = request.param
    path = os.path.join(HTML_DIR, f'momento-{n}.html')
    assert os.path.exists(path), f'Falta {path}'
    raw = open(path, encoding='utf-8').read()
    soup = BeautifulSoup(raw, 'html.parser')
    tables = soup.find_all('table', recursive=False)
    return dict(n=n, raw=raw, soup=soup, exp=MOMENTOS[n],
                header=tables[1], sesiones=tables[2], details=soup.find('details'),
                pis=tables[3], biblio=tables[4], top=tables)


# ---------------- 1. Estructura y seguridad del HTML ----------------
def test_bloques_en_orden(page):
    top = [t.name for t in page['soup'].find_all(recursive=False)]
    assert top == ['table', 'table', 'table', 'details', 'table', 'table'], top


def test_solo_etiquetas_permitidas(page):
    tags = {t.name for t in page['soup'].find_all(True)}
    assert tags <= ALLOWED, tags - ALLOWED
    assert not page['soup'].find_all(attrs={'class': True}) and not page['soup'].find_all(attrs={'id': True})


def test_etiquetas_balanceadas(page):
    class P(HTMLParser):
        def __init__(s):
            super().__init__(); s.st = []; s.err = []
        def handle_starttag(s, t, a):
            if t != 'br': s.st.append(t)
        def handle_endtag(s, t):
            if s.st and s.st[-1] == t: s.st.pop()
            else: s.err.append(t)
    p = P(); p.feed(page['raw'])
    assert not p.err and not p.st, (p.err, p.st)


def test_ampersands_escapados(page):
    assert not re.findall(r'&(?![a-zA-Z]+;|#\d+;)', page['raw'])


def test_sin_marcadores(page):
    txt = htmlmod.unescape(page['raw'])
    assert [m for m in MARCADORES if m in txt] == []
    assert 'PROPUESTO' not in txt and 'dashed' not in txt  # sin marcas de mockup


# ---------------- 2. Enlaces del curso ----------------
def test_boton_inicio_apunta_al_curso(page):
    u = urlparse(CURSO_URL)
    cid = re.search(r'/courses/(\d+)', u.path).group(1)
    slug = u.path.rsplit('/pages/', 1)[1]
    a = page['top'][0].find('a')
    assert a.get_text(strip=True) == 'Inicio del curso'
    assert a['href'] == f'https://{u.netloc}/courses/{cid}/pages/{slug}'
    assert a['data-api-endpoint'] == f'https://{u.netloc}/api/v1/courses/{cid}/pages/{slug}'


def test_enlaces_internos_mismo_curso(page):
    cid = re.search(r'/courses/(\d+)', CURSO_URL).group(1)
    ids = set(re.findall(r'/courses/(\d+)', page['raw']))
    assert ids == {cid}, ids


# ---------------- 3. Encabezado ----------------
def test_titulo(page):
    th = page['header'].find('thead').find('th')
    assert own_text(th) == f"Momento {page['n']}: {page['exp']['titulo']}"


def test_fechas_formato_largo(page):
    spans = page['header'].find('thead').find_all('span')
    assert norm(spans[0].contents[0]) == f"Fecha Inicio: {larga(page['exp']['inicio'])}"
    assert norm(spans[1].get_text()) == f"Fecha Fin: {larga(page['exp']['fin'])}"


def test_ra_texto_completo(page):
    exp = page['exp']
    td = page['header'].find('tbody').find_all('tr')[1].find('td')
    got = [norm(p.get_text()) for p in td.find_all('p')]
    want = [f"{c}: {exp['ra_textos'][c].rstrip('.')}." for c in exp['ra']]
    assert got == want


def test_proposito_propuesto(page):
    rows = page['header'].find('tbody').find_all('tr')
    assert norm(rows[2].get_text()) == 'Propósito del momento'
    prop = norm(rows[3].get_text())
    assert prop.endswith('.') and prop.count('. ') == 0, 'debe ser una sola oración'
    assert re.match(r'^\w+(ar|er|ir)\b', prop.split()[0].rstrip(',')), 'debe empezar con verbo en infinitivo'
    assert len(prop.split()) <= 45, len(prop.split())
    assert norm(page['exp']['evidencia']) not in prop


# ---------------- 4. Tabla de sesiones ----------------
def test_evidencia_en_encabezado_y_rubrica(page):
    ev = norm(page['exp']['evidencia'])
    th = page['sesiones'].find('thead').find('th')
    assert norm(th.find_all('span')[-1].get_text()) == ev
    assert norm(page['details'].find('table').find_all('tr')[1].get_text()) == ev


def test_columnas_en_orden_de_plantilla(page):
    heads = [norm(th.get_text()) for th in page['sesiones'].find('thead').find_all('tr')[1].find_all('th')]
    assert heads == ['Sesión', 'Actividades en contacto con el docente', 'Actividades de trabajo autónomo',
                     'Actividades práctico-experimentales', 'Contenidos', 'Enlaces']


def test_numero_de_sesiones(page):
    rows = page['sesiones'].find('tbody').find_all('tr', recursive=False)
    assert len(rows) == len(page['exp']['sesiones'])


def test_sesiones_contenido_literal_y_mapeo_por_significado(page):
    rows = page['sesiones'].find('tbody').find_all('tr', recursive=False)
    for tr, s in zip(rows, page['exp']['sesiones']):
        th, doc, aut, pe, cont, enl = tr.find_all(['th', 'td'], recursive=False)
        span = th.find('span')
        assert own_text(th.find('p')) == str(s['n'])
        assert norm(span.get_text()) == f"Fecha: {s['desde']} al {s['hasta']}"
        # docente
        assert own_text(doc) == s['doc'], f"S{s['n']} docente"
        assert norm(doc.find('span').get_text()) == f"({s['hd']} h)"
        otras = doc.find('p')
        assert norm(otras.find('strong').get_text()) == f"Otras actividades con el docente ({s['otras_h']} h):"
        assert own_text(otras) == s['otras'], f"S{s['n']} otras"
        # autónomo (3.ª columna de la plantilla) y práctico-experimental (4.ª)
        assert own_text(aut) == s['aut'], f"S{s['n']} autónomo"
        assert norm(aut.find('span').get_text()) == f"({s['ha']} h)"
        assert own_text(pe) == s['pe'], f"S{s['n']} práctico-experimental"
        assert norm(pe.find('span').get_text()) == f"({s['hpe']} h)"
        assert norm(cont.get_text()) == f"• {s['cont']}"
        assert norm(enl.get_text()) == '(Pegar enlace)'


def test_horas_suman_totales(page):
    rows = page['sesiones'].find('tbody').find_all('tr', recursive=False)
    tot = [0.0, 0.0, 0.0]
    for tr in rows:
        _, doc, aut, pe, _, _ = tr.find_all(['th', 'td'], recursive=False)
        for i, cell in enumerate((doc, pe, aut)):
            tot[i] += float(re.search(r'\(([\d.]+) h\)', cell.find('span').get_text()).group(1))
    assert tot == [float(x) for x in page['exp']['totales']]


def test_estilo_filas_intermedias_y_ultima(page):
    rows = page['sesiones'].find('tbody').find_all('tr', recursive=False)
    for i, tr in enumerate(rows):
        cells = tr.find_all(['th', 'td'], recursive=False)
        last = i == len(rows) - 1
        for c in cells:
            st = c['style']
            if last:
                assert 'border-bottom' not in st
            else:
                assert 'border-bottom: 1px solid #e2e8f0' in st and 'border-radius' not in st
        if last:
            assert 'border-radius: 0px 0px 0px 10px' in cells[0]['style']
            assert 'border-radius: 0px 0px 10px' in cells[-1]['style']
            assert all('#fcfafe' in c['style'] for c in cells[1:])


# ---------------- 5. Rúbrica ----------------
def test_rubrica_niveles_e_indicadores(page):
    trs = page['details'].find('table').find_all('tr')
    assert [norm(t.get_text()) for t in trs[2].find_all('th')] == ['Indicador'] + sp.LEVELS
    filas = trs[3:]
    exp = page['exp']['rubrica']
    assert len(filas) == len(exp)
    for tr, (nombre, niveles) in zip(filas, exp):
        celdas = [norm(c.get_text()) for c in tr.find_all(['th', 'td'])]
        assert celdas == [nombre] + niveles, nombre


def test_rubrica_evidencia_del_silabo_coincide(page):
    assert norm(page['exp']['rubrica_ev']) == norm(page['exp']['evidencia'])


# ---------------- 6. PIS ----------------
def test_pis(page):
    td = page['pis'].find('tbody').find('td')
    ps = td.find_all('p')
    assert norm(ps[0].find('strong').get_text()) == SILABO['pis']['titulo']
    assert norm(ps[1].get_text()) == SILABO['pis']['aporte']


# ---------------- 7. Bibliografía ----------------
def _bib_items(td):
    out = []
    for p in td.find_all('p'):
        a = p.find('a')
        strong = p.find('strong')
        texto = norm(p.get_text()).split(' ', 1)[1].rsplit(' Acceder', 1)[0]
        out.append(dict(p=p, a=a, strong=strong, texto=texto))
    return out


def _mismo_texto(gen, src):
    return re.sub(r'[\s.]', '', gen) == re.sub(r'[\s.]', '', src)


def test_bibliografia_basica_completa(page):
    tds = page['biblio'].find('tbody').find_all('td')
    items = _bib_items(tds[0])
    exp = SILABO['bibliografia']['basica']
    assert len(items) == len(exp)
    for it, e in zip(items, exp):
        assert it['a']['href'] == e['url']
        assert _mismo_texto(it['texto'], e['texto']), it['texto']
        assert it['p'].find('em') is not None, 'título en cursiva'


def test_bibliografia_complementaria(page):
    tds = page['biblio'].find('tbody').find_all('td')
    items = _bib_items(tds[1])
    por_url = {e['url']: e for e in SILABO['bibliografia']['complementaria']}
    assert len(items) == 2, 'regla: 2 obras por momento'
    for it in items:
        e = por_url.get(it['a']['href'])
        assert e, f"URL no está en el sílabo: {it['a']['href']}"
        editorial = e['texto'].rstrip('.').rsplit('. ', 1)[1]
        sin_editorial = e['texto'].rstrip('.')[: -len(editorial)]
        assert _mismo_texto(it['texto'], sin_editorial), f'APA 7: en artículos se omite la editorial ({editorial})'
        assert it['p'].find('em') is not None


def test_bibliografia_formato(page):
    tds = page['biblio'].find('tbody').find_all('td')
    for td, color in ((tds[0], '#3a1467'), (tds[1], '#a6480c')):
        items = _bib_items(td)
        for i, it in enumerate(items, 1):
            assert norm(it['strong'].get_text()) == f'{i}.'
            assert f'color: {color}' in it['strong']['style']
            assert it['a'].get_text() == 'Acceder' and it['a']['target'] == '_blank' and it['a']['rel'] == ['noopener']
            margin = 'margin: 0;' if i == len(items) else 'margin: 0 0 10px 0;'
            assert it['p']['style'] == margin


def test_reparto_complementaria_cubre_todas():
    usadas = set()
    for n in NS:
        soup = BeautifulSoup(open(os.path.join(HTML_DIR, f'momento-{n}.html'), encoding='utf-8').read(), 'html.parser')
        td = soup.find_all('table', recursive=False)[4].find('tbody').find_all('td')[1]
        usadas |= {a['href'] for a in td.find_all('a')}
    todas = {e['url'] for e in SILABO['bibliografia']['complementaria']}
    assert todas <= usadas, f'obras sin asignar: {todas - usadas}'


# ---------------- 8. Fidelidad a la plantilla ----------------
def test_estilos_son_los_de_la_plantilla(page):
    plantilla = style_set(BeautifulSoup(open(FIXTURE, encoding='utf-8').read(), 'html.parser'))
    extra = style_set(page['soup']) - plantilla
    assert not extra, f'estilos que no existen en la plantilla: {extra}'


def test_momento1_igual_al_aprobado():
    gen = BeautifulSoup(open(os.path.join(HTML_DIR, 'momento-1.html'), encoding='utf-8').read(), 'html.parser')
    ref = BeautifulSoup(open(FIXTURE, encoding='utf-8').read(), 'html.parser')
    assert norm(gen.get_text(' ')) == norm(ref.get_text(' '))
    tags = lambda s: [t.name for t in s.find_all(True)]
    assert tags(gen) == tags(ref)


# ---------------- 9. Validaciones globales del sílabo ----------------
def test_sesiones_en_html_existen_para_cada_momento():
    assert sorted(int(re.search(r'(\d+)', os.path.basename(f)).group(1))
                  for f in glob.glob(os.path.join(HTML_DIR, 'momento-*.html'))) == NS
