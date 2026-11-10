# -*- coding: utf-8 -*-
"""Lista de control que corre sobre cada HTML antes de habilitar la descarga.

Mismas reglas que tests/test_momentos.py (prompt maestro), en forma de función para el sistema.
"""
import html as htmlmod
import re
from html.parser import HTMLParser

from bs4 import BeautifulSoup, NavigableString

from .render import fecha_larga, fecha_sesion, _bloques, cita_obra, enlace

PERMITIDAS = {'table', 'thead', 'tbody', 'tr', 'th', 'td', 'details', 'summary', 'p', 'span', 'strong', 'em', 'a', 'br'}
MARCADORES = ['(Copiar y pegar', '[Día, Mes, Año]', 'TÍTULO DEL MOMENTO', '[Apellido']
NIVELES = ['Receptivo', 'Resolutivo', 'Reflexivo', 'Crítico', 'Cocreativo']


def _n(s):
    return re.sub(r'\s+', ' ', htmlmod.unescape(s).replace('\xa0', ' ')).strip()


def _own(tag):
    return _n(''.join(str(s) for s in tag.contents if isinstance(s, NavigableString)))


def _styles(soup):
    return {re.sub(r'\s+', ' ', t['style'].lower()).strip().rstrip(';') for t in soup.find_all(style=True)}


def _balanceado(raw):
    class P(HTMLParser):
        def __init__(s):
            super().__init__(); s.st = []; s.err = 0
        def handle_starttag(s, t, a):
            if t != 'br': s.st.append(t)
        def handle_endtag(s, t):
            if s.st and s.st[-1] == t: s.st.pop()
            else: s.err += 1
    p = P(); p.feed(raw)
    return not p.err and not p.st


def controlar(raw, m, sil, curso, plantilla_html, comp_urls, proposito):
    res = []

    def chk(nombre, fn, bloquea=True):
        try:
            ok, det = fn()
        except Exception as e:  # cualquier estructura inesperada cuenta como fallo
            ok, det = False, f'no se pudo verificar ({type(e).__name__}: {e})'
        res.append(dict(nombre=nombre, ok=bool(ok), detalle='' if ok else (det or ''), bloquea=bloquea))

    soup = BeautifulSoup(raw, 'html.parser')
    b = _bloques(soup)
    plantilla = BeautifulSoup(plantilla_html, 'html.parser')
    pb = _bloques(plantilla)

    hay_pis = bool(sil['pis'].get('titulo') or sil['pis'].get('aporte'))
    requeridos = ('boton', 'encabezado', 'sesiones', 'rubrica', 'biblio') + (('pis',) if hay_pis else ())
    chk('Bloques en el orden de la plantilla', lambda: (
        [k for k in requeridos if b[k] is None] == [] and (hay_pis or b['pis'] is None),
        'faltan: ' + ', '.join(k for k in requeridos if b[k] is None)))
    chk('Solo etiquetas permitidas por Canvas', lambda: (
        {t.name for t in soup.find_all(True)} <= PERMITIDAS and not soup.find_all(attrs={'class': True}),
        ', '.join(sorted({t.name for t in soup.find_all(True)} - PERMITIDAS))))
    chk('Etiquetas bien cerradas y texto escapado', lambda: (
        _balanceado(raw) and not re.findall(r'&(?![a-zA-Z]+;|#\d+;)', raw), ''))
    chk('Sin marcadores "(Copiar y pegar…)"', lambda: (
        not [x for x in MARCADORES if x in htmlmod.unescape(raw)],
        ', '.join(x for x in MARCADORES if x in htmlmod.unescape(raw))))

    def boton():
        a = next(x for x in soup.find_all('a') if x.get_text(strip=True) == 'Inicio del curso')
        esperado = f'https://{curso["host"]}/courses/{curso["id"]}/pages/{curso["slug"]}'
        ids = set(re.findall(r'/courses/(\d+)', raw))
        return a['href'] == esperado and ids == {curso['id']}, f'href={a["href"]} ids={sorted(ids)}'
    chk('Botón Inicio → curso del docente', boton)

    enc = b['encabezado']
    chk('Título "Momento N: …"', lambda: (
        _own(enc.find('thead').find('th')) == f'Momento {m["n"]}: {m["titulo"]}', _own(enc.find('thead').find('th'))))

    def fechas():
        sp = enc.find('thead').find_all('span')
        ok = _n(sp[0].contents[0]) == f'Fecha Inicio: {fecha_larga(m["inicio"])}' and \
            _n(sp[1].get_text()) == f'Fecha Fin: {fecha_larga(m["fin"])}'
        ok &= len(sp) == 2 and enc.find('thead').get_text().count('Fecha Inicio:') == 1
        ok &= enc.find('thead').get_text().count('Fecha Fin:') == 1
        return ok, ''
    chk('Fechas en formato largo', fechas)

    def ra():
        filas = enc.find('tbody').find_all('tr', recursive=False)
        td = filas[1].find('td')
        got = [_n(p.get_text()) for p in td.find_all('p')]
        want = [f'{c}: {sil["ra"].get(c, "").rstrip(".")}.' for c in m['ra']]
        return got == want and all(sil['ra'].get(c) for c in m['ra']), ''
    chk('RA con texto completo', ra)

    if 'Propósito del momento' in plantilla.get_text():
        def prop():
            filas = enc.find('tbody').find_all('tr', recursive=False)
            txt = next(_n(filas[i + 1].get_text()) for i, f in enumerate(filas[:-1])
                       if _n(f.get_text()) == 'Propósito del momento')
            pal = txt.split()
            ok = txt == _n(proposito) and txt.endswith('.') and txt.count('. ') == 0 and \
                re.match(r'^\w+(ar|er|ir)\b', pal[0].rstrip(',')) and len(pal) <= 45
            return ok, 'recomendado: 1 oración que empiece con verbo en infinitivo (≤45 palabras)'
        chk('Propósito: 1 oración en infinitivo', prop, bloquea=False)

    ses_t = b['sesiones']

    def evid():
        th = ses_t.find('thead').find('th')
        sp = [s for s in th.find_all('span') if not s.find('span')]
        r_tr = b['rubrica'].find('table').find_all('tr')
        ok = _n((sp[-1] if sp else th).get_text()).endswith(_n(m['evidencia'])) and \
            any(_n(t.get_text()) == _n(m['evidencia']) for t in r_tr)
        return ok, ''
    chk('Evidencia igual en tabla y rúbrica', evid)

    filas = ses_t.find('tbody').find_all('tr', recursive=False)
    cab = [_n(c.get_text()) for c in ses_t.find('thead').find_all('tr')[1].find_all(['th', 'td'])]
    idx = {k: next((i for i, c in enumerate(cab) if pat in c.lower()), None)
           for k, pat in (('doc', 'docente'), ('aut', 'autónomo'), ('pe', 'práctico'), ('cont', 'contenido'))}
    chk('Sesiones = sílabo', lambda: (len(filas) == len(m['sesiones']), f'{len(filas)} filas, sílabo {len(m["sesiones"])}'))

    def literal():
        malos = []
        for tr, s in zip(filas, m['sesiones']):
            c = tr.find_all(['th', 'td'], recursive=False)
            if _n(c[0].get_text()) != f'{s["n"]}{fecha_sesion(s)}':
                malos.append(f'S{s["n"]} fecha')
            if _own(c[idx['doc']]) != s['doc']:
                malos.append(f'S{s["n"]} docente')
            if s['otras'] and _own(c[idx['doc']].find('p')) != s['otras']:
                malos.append(f'S{s["n"]} otras actividades')
            if idx['cont'] is not None and _n(c[idx['cont']].get_text()) != _n(f'• {s["cont"]}'):
                malos.append(f'S{s["n"]} contenidos')
        return not malos, ', '.join(malos)
    chk('Texto literal del sílabo', literal)

    def mapeo():
        malos = []
        for tr, s in zip(filas, m['sesiones']):
            c = tr.find_all(['th', 'td'], recursive=False)
            if _own(c[idx['aut']]) != s['aut'] or _n(c[idx['aut']].find('span').get_text()) != f'({s["ha"]} h)':
                malos.append(f'S{s["n"]} autónomo')
            if _own(c[idx['pe']]) != s['pe'] or _n(c[idx['pe']].find('span').get_text()) != f'({s["hpe"]} h)':
                malos.append(f'S{s["n"]} práctico-exp.')
        return not malos, ', '.join(malos)
    chk('Autónomo / Práctico-exp. por significado', mapeo)

    def horas():
        tot = [0.0, 0.0, 0.0]
        for tr in filas:
            c = tr.find_all(['th', 'td'], recursive=False)
            for j, k in enumerate(('doc', 'pe', 'aut')):
                tot[j] += float(re.search(r'\(([\d.]+) h\)', c[idx[k]].find('span').get_text()).group(1))
        want = [float(x) for x in m['totales']]
        return tot == want, f'HTML {tot} · sílabo {want}'
    chk('Horas suman los totales', horas)

    def ultima():
        ok = True
        for i, tr in enumerate(filas):
            for c in tr.find_all(['th', 'td'], recursive=False):
                if i == len(filas) - 1:
                    ok &= 'border-bottom' not in c.get('style', '')
                else:
                    ok &= 'border-radius' not in c.get('style', '')
        return ok, ''
    chk('Estilo de última fila (bordes redondeados)', ultima)

    def rubrica():
        trs = b['rubrica'].find('table').find_all('tr')
        i = next(i for i, t in enumerate(trs) if _n(t.find(['th', 'td']).get_text()) == 'Indicador')
        head = [_n(t.get_text()) for t in trs[i].find_all(['th', 'td'])]
        got = [[_n(c.get_text()) for c in t.find_all(['th', 'td'])] for t in trs[i + 1:]]
        want = [[nom] + niv for nom, niv in m['rubrica']]
        return head == ['Indicador'] + NIVELES and got == want, f'{len(got)} indicadores, sílabo {len(want)}'
    chk('Rúbrica: indicadores × 5 niveles', rubrica)

    def pis():
        if not hay_pis:
            return b['pis'] is None, 'el sílabo no tiene PIS y la página no debe mostrarlo'
        td = b['pis'].find('tbody').find('td')
        ps = td.find_all('p')
        return _n(ps[0].get_text()) == sil['pis'].get('titulo') and _n(ps[1].get_text()) == sil['pis'].get('aporte'), ''
    chk('PIS literal', pis)

    def bib(tipo):
        filas_b = b['biblio'].find('tbody').find_all('tr', recursive=False)
        for i, f in enumerate(filas_b[:-1]):
            if _n(f.get_text()).startswith(tipo):
                return filas_b[i + 1].find('td')

    def basica():
        td = bib('Bibliografía básica')
        obras = sil['bibliografia']['basica']
        hrefs = [a['href'] for a in td.find_all('a')]
        ok = len(td.find_all('p')) == len(obras) and hrefs == [enlace(o) for o in obras if enlace(o)]
        for i, (p, o) in enumerate(zip(td.find_all('p'), obras), 1):
            texto = ''.join(p.strings).strip()
            esperado = BeautifulSoup(cita_obra(o), 'html.parser').get_text()
            ok &= texto == f'{i}. {esperado}' + (' Acceder' if enlace(o) else '')
        return ok, f'{len(td.find_all("p"))} obras en la página, {len(obras)} en el sílabo'
    chk('Bibliografía básica completa', basica)

    def comp():
        td = bib('Bibliografía complementaria')
        por_clave = {o['clave']: o for o in sil['bibliografia']['complementaria']}
        if not comp_urls:
            return td is None, 'no hay obras complementarias asignadas'
        obras = [por_clave[c] for c in comp_urls if c in por_clave]
        ps = td.find_all('p')
        ok = len(obras) == len(comp_urls) == len(ps)
        ok &= [a['href'] for a in td.find_all('a')] == [enlace(o) for o in obras if enlace(o)]
        for i, (p, o) in enumerate(zip(ps, obras), 1):
            esperado = BeautifulSoup(cita_obra(o), 'html.parser').get_text()
            ok &= p.get_text().strip() == f'{i}. {esperado}' + (' Acceder' if enlace(o) else '')
            if o.get('url'):
                ok &= p.find('em') is not None
        return ok, ''
    chk('Complementarias, APA sin editorial', comp)

    def acceder():
        ok = True
        for a in b['biblio'].find_all('a'):
            ok &= a.get_text() == 'Acceder' and bool(re.match(r'^https?://\S+\.\S+$', a['href'])) and a.get('target') == '_blank'
        return ok, ''
    chk('Enlaces "Acceder" válidos', acceder)

    # ---- avisos del sílabo (no bloquean): muestran lo que falta para que el docente lo complete ----
    chk('Sílabo: PIS registrado', lambda: (
        hay_pis, 'el sílabo no registra Proyecto Interdisciplinario Socioformativo; la página va sin esa sección'),
        bloquea=False)

    def con_enlace():
        en_pagina = sil['bibliografia']['basica'] + [o for o in sil['bibliografia']['complementaria']
                                                     if o['clave'] in comp_urls]
        faltan = [o['texto'].split(').')[0] + ')' for o in en_pagina if not enlace(o)]
        return not faltan, 'sin enlace "Acceder": ' + '; '.join(faltan)
    chk('Sílabo: todas las obras con enlace', con_enlace, bloquea=False)

    chk('Estilos idénticos a la plantilla', lambda: (
        _styles(soup) <= _styles(plantilla) | _styles(BeautifulSoup(_defaults(), 'html.parser')),
        ', '.join(sorted(_styles(soup) - _styles(plantilla)))[:200]))
    return res


def _defaults():
    from .render import ST_HORAS, ST_FECHA, ST_OTRAS, ST_RUB, leer_plantilla_institucional
    return leer_plantilla_institucional() + ''.join(f'<span style="{s}"></span>' for s in (ST_HORAS, ST_FECHA, ST_OTRAS, ST_RUB))
