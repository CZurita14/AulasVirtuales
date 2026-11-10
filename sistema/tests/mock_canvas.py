# -*- coding: utf-8 -*-
"""Canvas simulado (solo lo que usa el sistema) para pruebas sin tocar un Canvas real.

Uso en pruebas:   httpx.MockTransport(MockCanvas().handler)
Como servidor:    python sistema/tests/mock_canvas.py 8771   (token de prueba: TOKEN_PRUEBA)
"""
import copy
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

TOKEN = 'TOKEN_PRUEBA_0123456789'
CURSO = '36254'
HOST = 'indoamerica.instructure.com'


def _tile(slug, n):
    return (f'<a title="Momento" href="https://{HOST}/courses/{CURSO}/pages/{slug}">'
            f'<img src="x.png" alt="Momento 0{n}"></a>')


class MockCanvas:
    def __init__(self, plantilla_body='<p>(Copiar y pegar del sílabo)</p>', slugs=None, sin=()):
        slugs = slugs or {1: 'momento-1-2', 2: 'momento-2', 3: 'momento-3', 4: 'momento-4'}
        self.paginas = {'inicio': dict(url='inicio', title='Inicio', published=True,
                                       body='<p>Bienvenidos</p>' + ''.join(_tile(s, n) for n, s in slugs.items() if n not in sin))}
        for n, s in slugs.items():
            if n in sin:
                continue
            self.paginas[s] = dict(url=s, title=f'Momento {n}', published=True, body=plantilla_body)
        self.paginas['recursos-1'] = dict(url='recursos-1', title='Recursos de Aprendizaje 1', published=True, body='<p>r</p>')
        self.modulos = [dict(id=10 + n, name=f'Momento {n}', items=[
            dict(type='Page', title='Recursos de Aprendizaje 1', page_url='recursos-1'),
            dict(type='Page', title=f'Momento {n}', page_url=slugs[n])]) for n in slugs if n not in sin]
        self.puts = []
        self.fallar_put = set()

    def handler(self, req: httpx.Request) -> httpx.Response:
        if req.headers.get('authorization') != f'Bearer {TOKEN}':
            return httpx.Response(401, json={'errors': [{'message': 'Invalid access token.'}]})
        path = req.url.path
        m = re.match(r'^/api/v1/courses/(\d+)(/.*)?$', path)
        if not m or m.group(1) != CURSO:
            return httpx.Response(404, json={'errors': [{'message': 'not found'}]})
        sub = m.group(2) or ''
        q = parse_qs(urlparse(str(req.url)).query)
        if req.method == 'GET':
            if sub == '':
                return httpx.Response(200, json={'id': int(CURSO), 'name': 'EB26-SOFT-2-ELECTIVA II PARALELO 01'})
            if sub == '/front_page':
                return httpx.Response(200, json=self.paginas['inicio'])
            if sub == '/modules':
                return httpx.Response(200, json=self.modulos)
            if sub == '/pages':
                t = (q.get('search_term') or [''])[0].lower()
                return httpx.Response(200, json=[{k: v for k, v in p.items() if k != 'body'}
                                                 for p in self.paginas.values() if t in p['title'].lower()])
            pm = re.match(r'^/pages/([^/]+)$', sub)
            if pm and pm.group(1) in self.paginas:
                return httpx.Response(200, json=self.paginas[pm.group(1)])
        if req.method == 'PUT':
            pm = re.match(r'^/pages/([^/]+)$', sub)
            if pm and pm.group(1) in self.paginas:
                slug = pm.group(1)
                if slug in self.fallar_put:
                    return httpx.Response(500, json={'errors': [{'message': 'boom'}]})
                ctype = req.headers.get('content-type', '')
                if 'json' in ctype:
                    body = json.loads(req.content.decode('utf-8'))['wiki_page']['body']
                else:
                    body = parse_qs(req.content.decode('utf-8'))['wiki_page[body]'][0]
                self.paginas[slug]['body'] = body
                self.puts.append(slug)
                return httpx.Response(200, json=self.paginas[slug])
        return httpx.Response(404, json={'errors': [{'message': 'not found'}]})


def servir(puerto, mock=None):
    mock = mock or MockCanvas()

    class H(BaseHTTPRequestHandler):
        def _go(self):
            n = int(self.headers.get('content-length') or 0)
            req = httpx.Request(self.command, f'http://localhost{self.path}', headers=dict(self.headers),
                                content=self.rfile.read(n) if n else b'')
            r = mock.handler(req)
            self.send_response(r.status_code)
            self.send_header('content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(r.content)
        do_GET = do_PUT = _go

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(('127.0.0.1', puerto), H)
    return srv, mock


if __name__ == '__main__':
    sys.path.insert(0, __file__.rsplit('tests', 1)[0])
    from core.render import leer_plantilla_institucional
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8771
    srv, _ = servir(puerto, MockCanvas(plantilla_body=leer_plantilla_institucional()))
    print(f'Canvas simulado en http://127.0.0.1:{puerto} · curso {CURSO} · token {TOKEN}')
    srv.serve_forever()
