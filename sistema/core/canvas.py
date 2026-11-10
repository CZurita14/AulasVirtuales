# -*- coding: utf-8 -*-
"""Cliente mínimo de la API de Canvas con el token del docente.

- Solo lectura por defecto. Escribir (PUT del cuerpo de una página) exige `aprobado=True`.
- El token vive solo en este objeto (memoria); nunca se escribe en registros ni se devuelve al navegador.
- Solo habla con el servidor del curso (*.instructure.com o los de CANVAS_HOSTS).
"""
import os
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

TIMEOUT = 30
# para pruebas locales: CANVAS_API_OVERRIDE=http://127.0.0.1:8771 redirige las llamadas a un Canvas simulado
OVERRIDE = os.environ.get('CANVAS_API_OVERRIDE', '').rstrip('/')
HOSTS_EXTRA = {h.strip().lower() for h in os.environ.get('CANVAS_HOSTS', '').split(',') if h.strip()}


class ErrorCanvas(Exception):
    """Error que se muestra al docente."""


_HOST_CANVAS = re.compile(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.instructure\.com$')


def curso_desde_url(url):
    """'https://x.instructure.com/courses/36254[/...]' → dict(host, id, url).

    El host se valida carácter por carácter (solo letras, números y guiones antes de .instructure.com,
    sin usuario, contraseña ni puerto): el token del docente solo puede viajar a ese servidor."""
    m = re.match(r'^\s*https://([A-Za-z0-9.-]+)/courses/(\d+)(?:[/?#][^\s]*)?\s*$', url or '')
    if not m:
        return None
    host = m.group(1).lower()
    if not (_HOST_CANVAS.match(host) or host in HOSTS_EXTRA):
        return None
    return dict(host=host, id=m.group(2), url=f'https://{host}/courses/{m.group(2)}')


def es_titulo_momento(texto, n):
    return bool(re.search(rf'\bMomento\s*0?{n}(?!\d)', texto or '', re.I))


class Canvas:
    def __init__(self, curso, token, transport=None):
        if not token or len(token.strip()) < 10:
            raise ErrorCanvas('Falta el token de acceso de Canvas.')
        self.curso = curso
        base = OVERRIDE or f'https://{curso["host"]}'
        self._c = httpx.Client(base_url=base + '/api/v1', timeout=TIMEOUT, transport=transport,
                               headers={'Authorization': f'Bearer {token.strip()}', 'Accept': 'application/json'})

    def cerrar(self):
        self._c.close()

    # ---------------- HTTP ----------------
    def _req(self, metodo, ruta, **kw):
        try:
            r = self._c.request(metodo, ruta, **kw)
        except httpx.HTTPError as e:
            raise ErrorCanvas(f'No se pudo conectar con Canvas ({type(e).__name__}).') from None
        if r.status_code == 401:
            raise ErrorCanvas('Canvas rechazó el token: está vencido, fue eliminado o está mal copiado.')
        if r.status_code == 403:
            raise ErrorCanvas('Tu usuario no tiene permiso para esta acción en el curso (¿eres docente del curso?).')
        if r.status_code == 404:
            raise ErrorCanvas('Canvas no encontró el recurso (revisa la URL del curso).')
        if r.status_code >= 400:
            raise ErrorCanvas(f'Canvas respondió con error {r.status_code}.')
        return r

    def _get_todo(self, ruta, params=None):
        """GET con paginación (cabecera Link rel=next)."""
        params = dict(params or {}, per_page=100)
        out, url = [], ruta
        for _ in range(50):
            r = self._req('GET', url, params=params)
            out.extend(r.json())
            sig = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get('link', ''))
            if not sig:
                break
            url, params = sig.group(1), None
            if url.startswith('http'):
                url = re.sub(r'^https?://[^/]+/api/v1', '', url)
        return out

    # ---------------- lectura ----------------
    def info_curso(self):
        return self._req('GET', f'/courses/{self.curso["id"]}').json()

    def pagina_inicio(self):
        try:
            return self._req('GET', f'/courses/{self.curso["id"]}/front_page').json()
        except ErrorCanvas:
            return None

    def modulos(self):
        return self._get_todo(f'/courses/{self.curso["id"]}/modules', {'include[]': 'items'})

    def buscar_paginas(self, termino):
        return self._get_todo(f'/courses/{self.curso["id"]}/pages', {'search_term': termino})

    def pagina(self, slug):
        return self._req('GET', f'/courses/{self.curso["id"]}/pages/{slug}').json()

    # ---------------- escritura (requiere aprobación) ----------------
    def actualizar_cuerpo(self, slug, body, aprobado=False):
        if aprobado is not True:
            raise PermissionError('Escritura en Canvas sin aprobación del docente.')
        return self._req('PUT', f'/courses/{self.curso["id"]}/pages/{slug}',
                         json={'wiki_page': {'body': body}}).json()


# ---------------- localizar las páginas "Momento N" ----------------
class _Enlaces(HTMLParser):
    """Enlaces a páginas del curso con su texto, title y alt de imágenes internas."""
    def __init__(self):
        super().__init__(); self.enlaces = []; self._a = None

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == 'a':
            self._a = dict(href=a.get('href', '') or '', txt=[a.get('title', '') or '', a.get('aria-label', '') or ''])
        elif tag == 'img' and self._a is not None:
            self._a['txt'] += [a.get('alt', '') or '', a.get('title', '') or '']

    def handle_data(self, d):
        if self._a is not None:
            self._a['txt'].append(d)

    def handle_endtag(self, tag):
        if tag == 'a' and self._a is not None:
            self.enlaces.append(self._a); self._a = None


def _slug(href, curso_id):
    m = re.search(rf'/courses/{curso_id}/pages/([^/?#"\s]+)', href or '')
    return m.group(1) if m else None


def localizar_momentos(cv, numeros):
    """Devuelve {n: dict(slug, titulo, fuente)} y avisos. Fuentes: inicio > módulo > búsqueda."""
    cid = cv.curso['id']
    cand = {n: [] for n in numeros}
    avisos = []

    inicio = cv.pagina_inicio()
    if inicio and inicio.get('body'):
        p = _Enlaces(); p.feed(inicio['body'])
        for e in p.enlaces:
            s = _slug(e['href'], cid)
            texto = ' '.join(e['txt'])
            for n in numeros:
                if s and (es_titulo_momento(texto, n) or re.fullmatch(rf'momento-?0?{n}(-\d+)?', s)):
                    cand[n].append((s, 'página de inicio'))

    for mod in cv.modulos():
        paginas = [it for it in (mod.get('items') or []) if it.get('type') == 'Page' and it.get('page_url')]
        for n in numeros:
            por_titulo = [it for it in paginas if es_titulo_momento(it.get('title', ''), n)]
            if por_titulo:
                cand[n] += [(it['page_url'], 'módulo') for it in por_titulo]
            elif paginas and es_titulo_momento(mod.get('name', ''), n):
                cand[n].append((paginas[0]['page_url'], 'módulo (primera página)'))

    for pg in cv.buscar_paginas('momento'):
        for n in numeros:
            if es_titulo_momento(pg.get('title', ''), n):
                cand[n].append((pg['url'], 'búsqueda'))

    res = {}
    for n in numeros:
        if not cand[n]:
            avisos.append(f'Momento {n}: no se encontró su página en el curso; no se publicará.')
            continue
        slugs = list(dict.fromkeys(s for s, _ in cand[n]))
        elegido, fuente = cand[n][0]
        if len(slugs) > 1:
            # preferir una página cuyo título diga "Momento N"
            for s in slugs:
                try:
                    if es_titulo_momento(cv.pagina(s).get('title', ''), n):
                        elegido, fuente = s, next(f for x, f in cand[n] if x == s)
                        break
                except ErrorCanvas:
                    continue
            avisos.append(f'Momento {n}: hay varias páginas candidatas ({", ".join(slugs)}); se usará "{elegido}".')
        try:
            pg = cv.pagina(elegido)
        except ErrorCanvas as e:
            avisos.append(f'Momento {n}: no se pudo leer la página "{elegido}" ({e}).')
            continue
        res[n] = dict(slug=pg.get('url', elegido), titulo=pg.get('title', ''), fuente=fuente,
                      publicada=pg.get('published'), cuerpo=pg.get('body') or '',
                      url=f'https://{cv.curso["host"]}/courses/{cid}/pages/{pg.get("url", elegido)}')
    return res, avisos
