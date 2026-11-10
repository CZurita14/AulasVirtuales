# -*- coding: utf-8 -*-
"""Extracción INDEPENDIENTE del sílabo (PDF) para las pruebas.

No reutiliza los datos del generador: lee las tablas del PDF con pdfplumber, une las celdas
que se cortan entre páginas y devuelve lo que cada página "Momento N" debería contener.
"""
import re
import pdfplumber

LEVELS = ['Receptivo', 'Resolutivo', 'Reflexivo', 'Crítico', 'Cocreativo']


def _clean(c):
    return re.sub(r'\s+', ' ', (c or '').replace('\n', ' ')).strip()


def _join(a, b):
    if not a:
        return b
    if not b:
        return a
    return a + ' ' + b


def _rows(pdf):
    out = []
    for page in pdf.pages:
        for t in page.extract_tables():
            for r in t:
                out.append([_clean(c) for c in r])
    return out


def _split_otras(doc):
    m = re.search(r'\s*Otras actividades con el docente \((\d+(?:\.\d+)?) h\):\s*', doc)
    if not m:
        return doc.strip(), None, None
    return doc[:m.start()].strip(), m.group(1), doc[m.end():].strip()


def parse(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        rows = _rows(pdf)
        text = '\n'.join(p.extract_text() or '' for p in pdf.pages)

    momentos, cur, mode, ses, ind = [], None, None, None, None
    pis = {}
    pis_next = None
    for r in rows:
        r0 = r[0]
        # ---- PIS
        if r0 == 'Proyecto interdisciplinario socioformativo':
            pis_next = 'titulo'; continue
        if r0.startswith('Aporte del proyecto formativo al proyecto'):
            pis_next = 'aporte'; continue
        if pis_next and r0:
            pis[pis_next] = r0; pis_next = None; continue
        # ---- Momento
        m = re.fullmatch(r'Momento (\d+)', r0)
        if m:
            cur = dict(n=int(m.group(1)), titulo=r[2], sesiones=[], rubrica=[], rubrica_ev='', ra_textos={})
            momentos.append(cur); mode = 'head'; continue
        if r0.startswith('Rúbrica de la evidencia del desempeño central'):
            mode = 'final'; cur = None; continue
        if cur is None:
            continue
        if mode == 'head':
            if r0 == 'Fecha':
                a, b = re.findall(r'\d\d/\d\d/\d{4}', r[2]); cur['inicio'], cur['fin'] = a, b
            elif r0 == 'Resultados de aprendizaje':
                cur['ra'] = re.findall(r'RA\d+', r[2])
            elif r0.startswith('Evidencia de desempeño (producto esperado)'):
                cur['evidencia'] = r[2]
        if r0.startswith('Sesión - fecha'):
            mode = 'ses'; continue
        if mode == 'ses':
            rr = r[:2] + r[3:] if len(r) == 9 and r[2] == '' else r
            if r0 == 'Total':
                cur['totales'] = (rr[2], rr[4], rr[6]); continue
            if r0.startswith('Recursos para') or r0.startswith('Política de'):
                mode = 'post'; continue
            if r0.startswith('Sesión '):
                ses = dict(cab=r0, doc=rr[1], hd=rr[2], pe=rr[3], hpe=rr[4], aut=rr[5], ha=rr[6], cont=rr[7])
                cur['sesiones'].append(ses); continue
            # fila de continuación (celda cortada entre páginas)
            ses['cab'] = _join(ses['cab'], r0)
            for k, i in (('doc', 1), ('pe', 3), ('aut', 5), ('cont', 7)):
                ses[k] = _join(ses[k], rr[i])
            for k, i in (('hd', 2), ('hpe', 4), ('ha', 6)):
                ses[k] = ses[k] or rr[i]
            continue
        if r0.startswith('Evidencia de desempeño del momento'):
            mode = 'rub_ev'; continue
        if mode == 'rub_ev':
            if r0 == 'Indicador':
                mode = 'rub'; continue
            cells = [c for c in r if c]
            for c in cells:
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
            else:
                ind[1] = [_join(a, b) for a, b in zip(ind[1], rr[1:6])]

    for mo in momentos:
        for s in mo['sesiones']:
            m = re.match(r'Sesión (\d+) (\d\d/\d\d/\d{4}) al (\d\d/\d\d/\d{4})', s['cab'])
            s['n'], s['desde'], s['hasta'] = int(m.group(1)), m.group(2), m.group(3)
            s['doc'], s['otras_h'], s['otras'] = _split_otras(s['doc'])
            s['cont'] = s['cont'].lstrip('• ').strip()

    return dict(momentos=momentos, pis=pis, bibliografia=_biblio(text))


def _biblio(text):
    lines = [l for l in text.split('\n')
             if not re.match(r'^Sílabo .* Página \d+ de \d+', l) and not re.fullmatch(r'\d\d:\d\d', l.strip())]
    t = '\n'.join(lines)
    bas = t.split('Bibliografía básica', 1)[1].split('Bibliografía complementaria', 1)[0]
    com = t.split('Bibliografía complementaria', 1)[1].split('VII.', 1)[0]

    def entries(block):
        out, curr = [], ''
        for l in block.strip().split('\n'):
            if re.match(r'^[A-ZÁÉÍÓÚÑ][\w\-áéíóúäöñ]+, [A-Z]\.', l) and curr:
                out.append(curr); curr = l
            else:
                curr = (curr + ' ' + l).strip() if curr else l
        if curr:
            out.append(curr)
        res = []
        for e in out:
            i = e.index('https')
            res.append(dict(texto=e[:i].strip(), url=re.sub(r'\s+', '', e[i:])))
        return res

    return dict(basica=entries(bas), complementaria=entries(com))
