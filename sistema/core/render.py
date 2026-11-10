# -*- coding: utf-8 -*-
"""Renderizador: llena la plantilla HTML del docente (o la institucional) con los datos de un momento.

Trabaja sobre el árbol HTML (BeautifulSoup), nunca con reemplazos de texto sobre el HTML: conserva
todos los estilos, clona filas de sesión e indicadores, y solo cambia contenido y enlaces del curso.
"""
import copy
import html as htmlmod
import os
import re

from bs4 import BeautifulSoup, NavigableString, Tag

PLANTILLA_INSTITUCIONAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plantillas',
                                       'momento_institucional.html')
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre']

# estilos por defecto (de la plantilla institucional) para piezas que una plantilla vacía no trae
ST_HORAS = 'display: block; margin-top: 6px; color: #4a5568; font-size: clamp(10px, 2vw, 12px);'
ST_FECHA = 'display: block; margin-top: 4px; color: #4a5568; font-size: clamp(10px, 2vw, 13px); line-height: 1.5;'
ST_OTRAS = 'margin: 10px 0 0 0;'
ST_RUB = 'display: block; margin-top: 4px; color: #4a5568; font-size: clamp(9.5px, 1.9vw, 11.5px); line-height: 1.45;'


class PlantillaInvalida(ValueError):
    pass


def leer_plantilla_institucional():
    with open(PLANTILLA_INSTITUCIONAL, encoding='utf-8') as f:
        return f.read()


def enlace(o):
    """URL de la obra: la del sílabo o, si no trae, la que agregó el docente (PROPUESTO)."""
    return o.get('url') or o.get('url_doc') or ''


def fecha_sesion(s):
    """'Fecha: 08/12/2026 al 14/12/2026' o, si la sesión es de un día, 'Fecha: 06/10/2026'."""
    return f'Fecha: {s["desde"]} al {s["hasta"]}' if s.get('hasta') else f'Fecha: {s["desde"]}'


def fecha_larga(ddmmyyyy):
    d, m, y = ddmmyyyy.split('/')
    return f'{int(d)} de {MESES[int(m) - 1]} de {y}'


def curso_desde_url(url):
    m = re.match(r'^\s*https?://([^/\s]+)/courses/(\d+)/pages/([\w\-%.]+)\s*$', url or '')
    if not m:
        return None
    return dict(host=m.group(1), id=m.group(2), slug=m.group(3),
                url=f'https://{m.group(1)}/courses/{m.group(2)}/pages/{m.group(3)}')


# ---------------- localizar bloques ----------------
def _bloques(soup):
    b = dict(boton=None, encabezado=None, sesiones=None, rubrica=None, pis=None, biblio=None)
    for el in soup.find_all(['table', 'details'], recursive=False):
        txt = el.get_text(' ', strip=True)
        cab = el.find('th')
        rotulo = cab.get_text(' ', strip=True) if cab is not None else ''
        if el.name == 'details':
            b['rubrica'] = b['rubrica'] or el
        elif rotulo.startswith('Bibliograf'):
            b['biblio'] = b['biblio'] or el
        elif el.find('a') and 'Inicio' in txt and len(txt) < 60:
            b['boton'] = b['boton'] or el
        elif re.search(r'Fecha Inicio|TÍTULO DEL MOMENTO', txt):
            b['encabezado'] = b['encabezado'] or el
        elif el.find(['th'], string=re.compile(r'^\s*Sesi[óo]n\s*$')) or 'Evidencias de desempe' in txt:
            b['sesiones'] = b['sesiones'] or el
        elif 'Interdisciplinario' in txt or '(PIS)' in txt:
            b['pis'] = b['pis'] or el
        elif 'Bibliograf' in txt:
            b['biblio'] = b['biblio'] or el
    return b


def _errores_estructura(b):
    """Validar las piezas que el renderizador necesita, además de los rótulos visibles."""
    errores = [k for k in ('encabezado', 'sesiones', 'rubrica', 'pis', 'biblio') if b[k] is None]
    for nombre in ('encabezado', 'sesiones', 'biblio'):
        tabla = b[nombre]
        if tabla is not None and tabla.find('tbody') is None:
            errores.append(f'{nombre}: falta cuerpo de tabla')
    enc = b['encabezado']
    if enc is not None and enc.select_one('thead th') is None:
        errores.append('encabezado: falta cabecera')
    ses = b['sesiones']
    if ses is not None:
        cab = ses.find('thead')
        filas = cab.find_all('tr') if cab is not None else []
        if len(filas) < 2 or filas[0].find('th') is None:
            errores.append('sesiones: cabecera incompleta')
        cuerpo = ses.find('tbody')
        if cuerpo is not None and not cuerpo.find_all('tr', recursive=False):
            errores.append('sesiones: faltan filas modelo')
    rub = b['rubrica']
    if rub is not None:
        tabla = rub.find('table')
        filas = tabla.find_all('tr') if tabla is not None else []
        indicador = next((i for i, f in enumerate(filas) if f.find(['th', 'td']) is not None
                          and f.find(['th', 'td']).get_text(strip=True) == 'Indicador'), None)
        if indicador is None or indicador + 1 >= len(filas):
            errores.append('rubrica: falta tabla de indicadores o filas modelo')
    if b['pis'] is not None and b['pis'].select_one('tbody td') is None:
        errores.append('pis: falta celda de contenido')
    return errores


def analizar_plantilla(html):
    """Describe la plantilla: variante, IDs de curso y si viene vacía."""
    soup = BeautifulSoup(html, 'html.parser')
    b = _bloques(soup)
    faltan = _errores_estructura(b)
    txt = soup.get_text(' ')
    cols = []
    if b['sesiones'] is not None:
        filas = b['sesiones'].find('thead').find_all('tr') if b['sesiones'].find('thead') else []
        if len(filas) > 1:
            cols = [c.get_text(' ', strip=True) for c in filas[1].find_all(['th', 'td'])]
    return dict(
        valida=not faltan, faltan=faltan,
        vacia='Copiar y pegar' in txt or '[Día' in txt or 'TÍTULO DEL MOMENTO' in txt,
        proposito='Propósito del momento' in txt,
        enlaces=any(c.startswith('Enlace') for c in cols),
        columnas=cols,
        ids=sorted(set(re.findall(r'/courses/(\d+)', html))),
        boton=b['boton'] is not None,
    )


# ---------------- utilidades de árbol ----------------
def _set_text(tag, texto):
    tag.clear()
    tag.append(NavigableString(texto))


def _span_mas_profundo(tag):
    spans = tag.find_all('span')
    hoja = [s for s in spans if not s.find('span')]
    return hoja[-1] if hoja else None


def _rellenar_celda(celda, texto):
    """Conserva la cadena de estilos del contenido y elimina texto residual de la celda."""
    hoja = _span_mas_profundo(celda)
    if hoja is None:
        _set_text(celda, texto)
        return
    _set_text(hoja, texto)
    rama = hoja
    while rama is not celda:
        padre = rama.parent
        for hermano in list(padre.contents):
            if hermano is not rama:
                hermano.extract()
        rama = padre


def _nuevo(soup, nombre, style=None, texto=None):
    t = soup.new_tag(nombre)
    if style:
        t['style'] = style
    if texto is not None:
        t.append(NavigableString(texto))
    return t


def _primer_estilo(tag, nombre, defecto):
    t = tag.find(nombre) if tag is not None else None
    return t.get('style', defecto) if t is not None else defecto


# ---------------- bibliografía APA ----------------
def cita_html(texto):
    """Devuelve (html, es_articulo). Libro: título en cursiva. Artículo: revista y volumen en cursiva,
    número entre paréntesis sin cursiva y SIN editorial (APA 7)."""
    m = re.match(r'^(.*?\(\d{4}[a-z]?\)\.)\s*(.*)$', texto.strip())
    if not m:
        return htmlmod.escape(texto), False
    autores, resto = m.group(1), m.group(2)
    seg = re.split(r'\.\s+(?=[A-ZÁÉÍÓÚ0-9])', resto.rstrip('.'))
    esc = lambda s: htmlmod.escape(s, quote=False)
    if len(seg) >= 2:
        rev = re.match(r'^(.+?), (\d+)(\(\d+\))?, (\S+)$', seg[1]) or re.match(r'^(.+?), ()()(\d+[-–]\d+)$', seg[1])
        if rev and len(seg) >= 3:
            revista, vol, num, pags = rev.groups()
            em = esc(revista) + (f', {vol}' if vol else '')
            return f'{esc(autores)} {esc(seg[0])}. <em>{em}</em>{esc(num or "")}, {esc(pags)}.', True
        titulo = '. '.join(seg[:-1])          # título (y subtítulo) en cursiva; el último segmento es la editorial
        ed = re.match(r'^(.*?)\s*(\([^)]*ed\.\))$', titulo)
        t_html = f'<em>{esc(ed.group(1))}</em> {esc(ed.group(2))}' if ed else f'<em>{esc(titulo)}</em>'
        return f'{esc(autores)} {t_html}. {esc(seg[-1])}.', False
    return f'{esc(autores)} <em>{esc(resto.rstrip("."))}</em>.', False


# ---------------- render ----------------
def cita_obra(o):
    """Sin URL de origen, los estilos nunca deben modificar la referencia del sílabo."""
    formato, _ = cita_html(o['texto'])
    if not o.get('url') and BeautifulSoup(formato, 'html.parser').get_text() != o['texto']:
        return htmlmod.escape(o['texto'])
    return formato


def render(sil, n, plantilla_html, curso, proposito, complementaria_urls):
    m = next(x for x in sil['momentos'] if x['n'] == n)
    soup = BeautifulSoup(plantilla_html, 'html.parser')
    b = _bloques(soup)
    faltan = _errores_estructura(b)
    if faltan:
        raise PlantillaInvalida('A la plantilla le faltan bloques: ' + ', '.join(faltan))

    # Se conserva la composición reconocida; notas y bloques ajenos de páginas anteriores no se copian.
    bloques = {id(t) for t in b.values() if t is not None}
    for nodo in list(soup.contents):
        if id(nodo) not in bloques and (isinstance(nodo, Tag) or str(nodo).strip()):
            nodo.extract()

    # 1. botón Inicio (si no existe, se toma el de la plantilla institucional)
    if b['boton'] is None:
        inst = _bloques(BeautifulSoup(leer_plantilla_institucional(), 'html.parser'))['boton']
        b['encabezado'].insert_before(copy.copy(inst))
    for a in soup.find_all('a'):
        if a.get_text(strip=True) == 'Inicio del curso':
            a['href'] = f'https://{curso["host"]}/courses/{curso["id"]}/pages/{curso["slug"]}'
            a['data-api-endpoint'] = f'https://{curso["host"]}/api/v1/courses/{curso["id"]}/pages/{curso["slug"]}'
    for t in soup.find_all(True):
        for attr in ('href', 'data-api-endpoint', 'src'):
            if t.get(attr) and '/courses/' in t[attr]:
                t[attr] = re.sub(r'/courses/\d+', f'/courses/{curso["id"]}', t[attr])

    _encabezado(soup, b['encabezado'], m, sil, proposito)
    _sesiones(soup, b['sesiones'], m)
    _rubrica(soup, b['rubrica'], m)
    _pis(soup, b['pis'], sil)
    _biblio(soup, b['biblio'], sil, complementaria_urls)
    return soup.decode(formatter='html')


def _encabezado(soup, tabla, m, sil, proposito):
    th = tabla.find('thead').find('th') if tabla.find('thead') else tabla.find('th')
    titulo = f'Momento {m["n"]}: {m["titulo"]}'
    # Reconstruir el contenido evita heredar fechas duplicadas, párrafos o títulos anteriores.
    referencia = _bloques(BeautifulSoup(leer_plantilla_institucional(), 'html.parser'))['encabezado']
    st_fecha = _primer_estilo(th, 'span', referencia.find('span').get('style'))
    st_fin = next((sp.get('style', st_fecha) for sp in th.find_all('span')
                   if 'Fecha Fin:' in sp.get_text()), st_fecha)
    _set_text(th, titulo)
    inicio = _nuevo(soup, 'span', st_fecha, f'Fecha Inicio: {fecha_larga(m["inicio"])}\xa0')
    inicio.append(_nuevo(soup, 'span', st_fin, f'Fecha Fin: {fecha_larga(m["fin"])}'))
    th.append(inicio)
    filas = tabla.find('tbody').find_all('tr', recursive=False)
    for i, tr in enumerate(filas[:-1]):
        etq = tr.get_text(' ', strip=True)
        td = filas[i + 1].find('td')
        if td is None:
            continue
        if etq.startswith('Resultado(s) de aprendizaje'):
            p_st = _primer_estilo(td, 'p', None)
            td.clear()
            for code in m['ra']:
                p = _nuevo(soup, 'p', p_st, f'{code}: {sil["ra"].get(code, "").rstrip(".")}.')
                td.append(NavigableString('\n                ')); td.append(p)
            td.append(NavigableString('\n            '))
        elif etq.startswith('Propósito del momento'):
            p_st = _primer_estilo(td, 'p', None)
            td.clear()
            td.append(NavigableString('\n                '))
            td.append(_nuevo(soup, 'p', p_st, proposito))
            td.append(NavigableString('\n            '))


def _clasificar(cab):
    c = cab.lower()
    for k, pat in (('ses', 'sesi'), ('doc', 'docente'), ('aut', 'autónomo'), ('pe', 'práctico'),
                   ('cont', 'contenido'), ('enl', 'enlace')):
        if pat in c:
            return k
    return None


def _celda_actividad(soup, celda, texto, horas, otras=None):
    sp_st = _primer_estilo(celda, 'span', ST_HORAS)
    p = celda.find('p')
    p_st = p.get('style', ST_OTRAS) if p is not None else ST_OTRAS
    celda.clear()
    celda.append(NavigableString(texto))
    celda.append(_nuevo(soup, 'span', sp_st, f'({horas} h)'))
    if otras and otras[1]:
        celda.append(NavigableString('\n                '))
        pn = _nuevo(soup, 'p', p_st)
        pn.append(_nuevo(soup, 'strong', None, f'Otras actividades con el docente ({otras[0]} h):'))
        pn.append(NavigableString(' ' + otras[1]))
        celda.append(pn)
        celda.append(NavigableString('\n            '))


def _sesiones(soup, tabla, m):
    thead = tabla.find('thead')
    filas_h = thead.find_all('tr')
    sp = _span_mas_profundo(filas_h[0].find('th'))
    if sp is not None:
        _set_text(sp, m['evidencia'])
    else:
        th = filas_h[0].find('th')
        _set_text(th, f'Evidencias de desempeño (producto esperado): {m["evidencia"]}')
    cols = [_clasificar(c.get_text(' ', strip=True)) for c in filas_h[1].find_all(['th', 'td'])]
    tbody = tabla.find('tbody')
    filas = tbody.find_all('tr', recursive=False)
    if not filas:
        raise PlantillaInvalida('La tabla de sesiones no tiene filas modelo.')
    modelo_mid, modelo_ult = filas[0], filas[-1]
    for f in filas:
        f.extract()
    tbody.clear()
    ses = m['sesiones']
    for i, s in enumerate(ses):
        tr = copy.copy(modelo_ult if i == len(ses) - 1 else modelo_mid)
        celdas = tr.find_all(['th', 'td'], recursive=False)
        for k, celda in zip(cols, celdas):
            if k == 'ses':
                p = celda.find('p')
                cont = p if p is not None else celda
                st = _primer_estilo(cont, 'span', ST_FECHA)
                if p is not None:
                    p.extract()
                    celda.clear()
                    celda.append(p)
                cont.clear()
                cont.append(NavigableString(str(s['n'])))
                cont.append(_nuevo(soup, 'span', st, fecha_sesion(s)))
            elif k == 'doc':
                _celda_actividad(soup, celda, s['doc'], s['hd'], (s['otras_h'], s['otras']))
            elif k == 'aut':
                _celda_actividad(soup, celda, s['aut'], s['ha'])
            elif k == 'pe':
                _celda_actividad(soup, celda, s['pe'], s['hpe'])
            elif k == 'cont':
                _set_text(celda, '• ' + s['cont'])
            elif k == 'enl':
                _set_text(celda, '(Pegar enlace)')
        tbody.append(NavigableString('\n        '))
        tbody.append(tr)
    tbody.append(NavigableString('\n    '))


def _rubrica(soup, details, m):
    tabla = details.find('table')
    filas = tabla.find_all('tr')
    i_ind = next(i for i, f in enumerate(filas) if f.find(['th', 'td']) and
                 f.find(['th', 'td']).get_text(strip=True) == 'Indicador')
    for i, f in enumerate(filas[:i_ind]):
        if 'Evidencia de desempe' in f.get_text() and i + 1 < i_ind:
            td = filas[i + 1].find(['td', 'th'])
            _rellenar_celda(td, m['evidencia'])
    modelos = filas[i_ind + 1:]
    if not modelos:
        raise PlantillaInvalida('La rúbrica no tiene filas de indicador modelo.')
    modelo = modelos[-1]
    padre = modelo.parent
    for f in modelos:
        f.extract()
    for nombre, niveles in m['rubrica']:
        tr = copy.copy(modelo)
        for celda, texto in zip(tr.find_all(['th', 'td'], recursive=False), [nombre] + list(niveles)):
            sp = _span_mas_profundo(celda)
            if sp is not None:
                _rellenar_celda(celda, texto)
            else:
                _set_text(celda, '')
                celda.append(_nuevo(soup, 'span', ST_RUB, texto))
        padre.append(NavigableString('\n            '))
        padre.append(tr)
    padre.append(NavigableString('\n        '))


def _pis(soup, tabla, sil):
    if not sil['pis'].get('titulo') and not sil['pis'].get('aporte'):
        tabla.extract()          # el sílabo no registra PIS: no se inventa la sección
        return
    td = tabla.find('tbody').find('td')
    ps = td.find_all('p')
    st1 = ps[0].get('style', 'margin: 0 0 8px 0;') if ps else 'margin: 0 0 8px 0;'
    st_strong = _primer_estilo(td, 'strong', 'color: #3a1467;')
    st2 = ps[1].get('style', 'margin: 0;') if len(ps) > 1 else 'margin: 0;'
    td.clear()
    p1 = _nuevo(soup, 'p', st1)
    p1.append(_nuevo(soup, 'strong', st_strong, sil['pis'].get('titulo', '')))
    td.append(NavigableString('\n                ')); td.append(p1)
    td.append(NavigableString('\n                ')); td.append(_nuevo(soup, 'p', st2, sil['pis'].get('aporte', '')))
    td.append(NavigableString('\n            '))


def _llenar_biblio(soup, td, obras, color_def):
    ps = td.find_all('p')
    st_mid = ps[0].get('style', 'margin: 0 0 10px 0;') if ps else 'margin: 0 0 10px 0;'
    st_last = ps[-1].get('style', 'margin: 0;') if ps else 'margin: 0;'
    if len(ps) == 1:
        st_mid, st_last = 'margin: 0 0 10px 0;', 'margin: 0;'
    st_strong = _primer_estilo(td, 'strong', f'color: {color_def};')
    a0 = td.find('a')
    a_attrs = {k: v for k, v in (a0.attrs.items() if a0 is not None else {}) if k not in ('href',)}
    a_attrs.setdefault('target', '_blank')
    a_attrs.setdefault('rel', 'noopener')
    td.clear()
    for i, o in enumerate(obras, 1):
        p = _nuevo(soup, 'p', st_last if i == len(obras) else st_mid)
        p.append(_nuevo(soup, 'strong', st_strong, f'{i}.'))
        frag = BeautifulSoup(' ' + cita_obra(o) + (' ' if enlace(o) else ''), 'html.parser')
        for c in list(frag.contents):
            p.append(c)
        if not enlace(o):          # libro sin URL/DOI: se cita sin enlace "Acceder"
            td.append(NavigableString('\n                ')); td.append(p)
            continue
        a = soup.new_tag('a')
        a['href'] = enlace(o)
        for k, v in a_attrs.items():
            a[k] = v
        a.append(NavigableString('Acceder'))
        p.append(a)
        td.append(NavigableString('\n                ')); td.append(p)
    td.append(NavigableString('\n            '))


def _biblio(soup, tabla, sil, urls_comp):
    filas = tabla.find('tbody').find_all('tr', recursive=False)
    comp = [o for o in sil['bibliografia']['complementaria'] if o['clave'] in urls_comp]
    comp.sort(key=lambda o: urls_comp.index(o['clave']))
    for i, tr in enumerate(filas[:-1]):
        etq = tr.get_text(' ', strip=True)
        td = filas[i + 1].find('td')
        if td is None:
            continue
        if etq.startswith('Bibliografía básica'):
            _llenar_biblio(soup, td, sil['bibliografia']['basica'], '#3a1467')
        elif etq.startswith('Bibliografía complementaria'):
            if comp:
                _llenar_biblio(soup, td, comp, '#a6480c')
            else:                 # sin obras complementarias: se quita el bloque y la fila anterior cierra la tabla
                previo = filas[i - 1].find('td') if i > 0 else None
                if previo is not None and td.get('style'):
                    previo['style'] = td['style']
                tr.extract(); filas[i + 1].extract()
