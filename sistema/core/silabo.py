# -*- coding: utf-8 -*-
"""Lector del sílabo institucional (PDF) → diccionario con todo lo que necesitan las páginas Momento.

Lee las tablas con pdfplumber (no texto plano, porque las columnas se mezclan), une las celdas
que se cortan entre páginas y las URL partidas de la bibliografía.
"""
import re

import pdfplumber

NIVELES = ['Receptivo', 'Resolutivo', 'Reflexivo', 'Crítico', 'Cocreativo']


class FormatoNoReconocido(ValueError):
    """El PDF no tiene la estructura del sílabo institucional."""


def _clean(c):
    return re.sub(r'\s+', ' ', (c or '').replace('\n', ' ')).strip()


def _join(a, b):
    return b if not a else a if not b else a + ' ' + b


def _split_otras(doc):
    m = re.search(r'\s*Otras actividades con el docente \((\d+(?:\.\d+)?) h\):\s*', doc)
    if not m:
        return doc.strip(), None, None
    return doc[:m.start()].strip(), m.group(1), doc[m.end():].strip()


def leer(origen):
    """`origen`: ruta o archivo binario del PDF."""
    try:
        with pdfplumber.open(origen) as pdf:
            rows = [[_clean(c) for c in r] for p in pdf.pages for t in p.extract_tables() for r in t]
            textos = [p.extract_text() or '' for p in pdf.pages]
            paginas = len(pdf.pages)
    except Exception as e:  # PDF dañado o no es PDF
        raise FormatoNoReconocido(f'No se pudo abrir el PDF: {e}') from e

    texto = '\n'.join(textos)
    if 'MOMENTOS DEL PROYECTO FORMATIVO' not in texto.upper():
        raise FormatoNoReconocido('No reconozco la sección "IV. MOMENTOS DEL PROYECTO FORMATIVO". '
                                  '¿Es el sílabo generado por el sistema académico?')

    d = dict(paginas=paginas, ficha=_ficha(textos[0], rows), momentos=[], pis={},
             presentacion={}, ra={})
    _momentos(rows, d)
    if not d['momentos']:
        raise FormatoNoReconocido('No encontré ningún "Momento N" con su tabla de sesiones.')
    d['bibliografia'] = _biblio(texto)
    for tipo, lista in d['bibliografia'].items():   # clave estable aunque la obra no tenga URL
        for i, o in enumerate(lista, 1):
            o['clave'] = o['url'] or f'{tipo}-{i}'
    for m in d['momentos']:            # respaldo: el RA citado en cada rúbrica
        d['ra'].update(m['ra_textos'])
    d['ra'].update(d.pop('ra_tabla', {}))  # fuente principal: tabla de RA de la sección III
    return d


def _ficha(p1, rows):
    def tras(etq):
        m = re.search(re.escape(etq) + r'\s*\n(.+)', p1)
        return m.group(1).strip() if m else ''
    f = dict(facultad=tras('Facultad:'), carrera=tras('Carrera:'), periodo=tras('Periodo académico:'),
             proyecto=tras('Proyecto formativo:'), docente=tras('Docente:'))
    m = re.search(r'Proyecto formativo:\s*\n.+\n(\S+)', p1)
    f['codigo'] = m.group(1) if m else ''
    for k in ('Inicio', 'Fin'):
        m = re.search(k + r':\s*(\d{4}-\d{2}-\d{2})', p1)
        f[k.lower()] = m.group(1) if m else ''
    for i, r in enumerate(rows):
        if r[0] == 'Créditos' and i + 1 < len(rows):
            vals = [c for c in rows[i + 1] if c]
            heads = [c for c in r if c]
            f.update({h.lower(): v for h, v in zip(heads, vals)})
            break
    return f


def _momentos(rows, d):
    cur, mode, ses, ind, pis_next, cols = None, None, None, None, None, None
    d['pis'] = dict(titulo='', aporte='')
    for i, r in enumerate(rows):
        r0 = r[0]
        # Presentación: horas por tipo de aprendizaje (por encabezado, no por posición)
        if r0 == 'Aprendizaje en contacto con el docente' and i + 1 < len(rows):
            heads, vals = [c for c in r if c], [c for c in rows[i + 1] if c]
            d['presentacion'] = dict(zip(heads, vals))
            continue
        # Tabla "Resultados de aprendizaje y evidencias" (III): RA | texto | evidencia
        if cur is None and re.fullmatch(r'RA\d+', r0) and len(r) > 1 and r[1]:
            d['ra_tabla'] = d.get('ra_tabla', {})
            d['ra_tabla'][r0] = r[1]
            continue
        # PIS: la fila siguiente al rótulo es el valor, aunque venga vacía
        if r0 == 'Proyecto interdisciplinario socioformativo':
            pis_next = 'titulo'; continue
        if r0.startswith('Aporte del proyecto formativo al proyecto'):
            pis_next = 'aporte'; continue
        if pis_next:
            d['pis'][pis_next] = r0; pis_next = None; continue
        m = re.fullmatch(r'Momento (\d+)', r0)
        if m:
            cur = dict(n=int(m.group(1)), titulo=' '.join(c for c in r[1:] if c), sesiones=[], rubrica=[],
                       rubrica_ev='', ra_textos={}, ra=[], recursos='', politica_ia='')
            d['momentos'].append(cur); mode = 'head'; continue
        if r0.startswith('Rúbrica de la evidencia del desempeño central'):
            mode = 'final'; cur = None; continue
        if cur is None:
            continue
        if mode == 'head':
            valor = ' '.join(c for c in r[1:] if c)
            if r0 == 'Fecha':
                fechas = re.findall(r'\d\d/\d\d/\d{4}', valor)
                cur['inicio'], cur['fin'] = (fechas + ['', ''])[:2]
            elif r0 == 'Resultados de aprendizaje':
                cur['ra'] = re.findall(r'RA\d+', valor)
            elif r0.startswith('Evidencia de desempeño (producto esperado)'):
                cur['evidencia'] = valor
        if r0.startswith('Sesión - fecha'):
            cols = _columnas(r); mode = 'ses'; continue
        if mode in ('ses', 'post'):
            if r0.startswith('Recursos para'):
                cur['recursos'] = next((c for c in r[1:] if c), ''); mode = 'post'; continue
            if r0.startswith('Política de'):
                cur['politica_ia'] = next((c for c in r[1:] if c), ''); mode = 'post'; continue
        if mode == 'ses':
            v = _valores(r, cols)
            if r0 == 'Total':
                cur['totales'] = (v['hd'], v['hpe'], v['ha']); continue
            if r0.startswith('Sesión '):
                ses = dict(cab=r0, **v)
                cur['sesiones'].append(ses); continue
            if ses is None:
                continue
            # fila de continuación (celda cortada entre páginas)
            ses['cab'] = _join(ses['cab'], r0)
            for k in ('doc', 'pe', 'aut', 'cont'):
                ses[k] = _join(ses[k], v[k])
            for k in ('hd', 'hpe', 'ha'):
                ses[k] = ses[k] or v[k]
            continue
        if r0.startswith('Evidencia de desempeño del momento'):
            mode = 'rub_ev'; continue
        if mode == 'rub_ev':
            if r0 == 'Indicador':
                mode = 'rub'; continue
            for c in (c for c in r if c):
                if re.match(r'RA\d+:', c):
                    for code, txt in re.findall(r'(RA\d+): (.*?)(?= RA\d+:|$)', c):
                        cur['ra_textos'][code] = txt.strip()
                else:
                    cur['rubrica_ev'] = _join(cur['rubrica_ev'], c)
            continue
        if mode == 'rub':
            if r0 == 'Indicador':
                continue
            rr = r[:3] + r[4:] if len(r) == 7 and r[3] == '' else r
            if r0:
                ind = [r0, list(rr[1:6])]; cur['rubrica'].append(ind)
            elif ind:
                ind[1] = [_join(a, b) for a, b in zip(ind[1], rr[1:6])]

    for mo in d['momentos']:
        mo.setdefault('totales', ('', '', ''))
        mo.setdefault('evidencia', '')
        for s in mo['sesiones']:
            # "Sesión 1 08/12/2026 al 14/12/2026" o solo "Sesión 1 06/10/2026"
            m = re.match(r'Sesión (\d+)\s+(\d\d/\d\d/\d{4})(?:\s*al\s*(\d\d/\d\d/\d{4}))?', s['cab'])
            if m:
                s['n'], s['desde'], s['hasta'] = int(m.group(1)), m.group(2), m.group(3) or ''
            else:
                n = re.match(r'Sesión (\d+)', s['cab'])
                s['n'], s['desde'], s['hasta'] = (int(n.group(1)) if n else 0), '', ''
            s['doc'], s['otras_h'], s['otras'] = _split_otras(s['doc'])
            s['cont'] = s['cont'].lstrip('• ').strip()


_ENCABEZADOS = (('doc', 'Actividades con el docente'), ('pe', 'Actividades práctico'),
                ('aut', 'Actividades de trabajo autónomo'), ('cont', 'Contenidos'))


def _columnas(cab):
    """Mapa de columnas a partir del encabezado de la tabla de sesiones (las tablas pueden traer
    columnas vacías extra según el sílabo). Cada actividad abarca hasta la siguiente columna 'Horas'."""
    pos = {}
    for k, etq in _ENCABEZADOS:
        pos[k] = next((i for i, c in enumerate(cab) if c.startswith(etq)), None)
    horas = [i for i, c in enumerate(cab) if re.fullmatch(r'Hora\s*s?', c)]
    res = {}
    for k, kh in (('doc', 'hd'), ('pe', 'hpe'), ('aut', 'ha')):
        ini = pos[k]
        h = next((j for j in horas if ini is not None and j > ini), None)
        res[k] = (ini, h)          # texto en [ini, h)
        res[kh] = h
    res['cont'] = pos['cont']
    return res


def _valores(r, cols):
    if not cols:
        return dict(doc='', hd='', pe='', hpe='', aut='', ha='', cont='')
    celda = lambda j: r[j] if j is not None and j < len(r) else ''
    v = {}
    for k in ('doc', 'pe', 'aut'):
        ini, fin = cols[k]
        v[k] = ' '.join(c for c in (r[ini:fin] if ini is not None and fin is not None else [celda(ini)]) if c).strip()
    for k in ('hd', 'hpe', 'ha'):
        v[k] = celda(cols[k])
    v['cont'] = celda(cols['cont'])
    return v


def _biblio(text):
    lines = [l for l in text.split('\n')
             if not re.match(r'^Sílabo .* Página \d+ de \d+', l) and not re.fullmatch(r'\d\d:\d\d', l.strip())]
    t = '\n'.join(lines)
    # Las menciones a bibliografía dentro de Recursos no delimitan la sección VI.
    secciones = list(re.finditer(r'(?im)^[ \t]*VI\.[ \t]*BIBLIOGRAF[ÍI]A[ \t]*$', t))
    if secciones:
        t = t[secciones[-1].end():]  # el índice también enumera VI y VII
    t = re.split(r'(?im)^[ \t]*VII\.[^\n]*$', t, maxsplit=1)[0]
    inicio = re.search(r'(?im)^[ \t]*Bibliografía básica[ \t]*$', t)
    if not inicio:
        return dict(basica=[], complementaria=[])
    resto = t[inicio.end():]
    comp = re.search(r'(?im)^[ \t]*Bibliografía complementaria[ \t]*$', resto)
    bas, com = (resto[:comp.start()], resto[comp.end():]) if comp else (resto, '')

    def entries(block):
        out, curr = [], ''
        for l in block.strip().split('\n'):
            if not l.strip():
                continue
            # inicio de obra: "Apellido(s), N. … (Año)." (admite apellidos compuestos y varios autores)
            if curr and re.match(r'^[A-ZÁÉÍÓÚÑÜ][^()\n]{0,200}?(?:\([^()\n]*\)\.\s*)?\(\d{4}[a-z]?\)\.', l):
                out.append(curr); curr = l
            else:
                curr = (curr + ' ' + l).strip() if curr else l
        if curr:
            out.append(curr)
        res = []
        for e in out:
            i = e.find('https')
            texto, url = e.strip(), ''
            if i >= 0:
                texto, resto = e[:i].strip(), e[i:]
                nota = re.search(r'\s+Consultado\s+en\s*:', resto, re.I)
                if nota:
                    texto += ' ' + resto[nota.start():].strip()
                    resto = resto[:nota.start()].rstrip().rstrip('.')
                url = re.sub(r'\s+', '', resto)
            res.append(dict(texto=texto, url=url))
        return res

    return dict(basica=entries(bas), complementaria=entries(com))
