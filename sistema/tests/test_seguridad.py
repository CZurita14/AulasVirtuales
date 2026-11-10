# -*- coding: utf-8 -*-
"""El token del docente solo puede viajar a un servidor *.instructure.com legítimo."""
import os
import re
import shutil
import subprocess
import sys

import pytest

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)

from core import canvas  # noqa: E402

MALICIOSAS = [
    'https://evil.com?.instructure.com/courses/1',
    'https://evil.com#.instructure.com/courses/1',
    'https://x.instructure.com@evil.com/courses/1',
    'https://evil.com\\@x.instructure.com/courses/1',
    'https://user@x.instructure.com/courses/1',
    'https://user:pass@x.instructure.com/courses/1',
    'https://x.instructure.com:8443/courses/1',
    'https://evil.com%2F.instructure.com/courses/1',
    'https://evil.com/.instructure.com/courses/1',
    'https://instructure.com/courses/1',
    'https://a.b.instructure.com.evil.com/courses/1',
]


@pytest.mark.parametrize('url', MALICIOSAS)
def test_url_maliciosa_rechazada(url):
    assert canvas.curso_desde_url(url) is None


@pytest.mark.parametrize('url,host,cid', [
    ('https://indoamerica.instructure.com/courses/36254', 'indoamerica.instructure.com', '36254'),
    ('https://Indoamerica.Instructure.com/courses/36254/pages/inicio', 'indoamerica.instructure.com', '36254'),
    ('  https://uti-test.instructure.com/courses/7?x=1  ', 'uti-test.instructure.com', '7'),
])
def test_url_valida(url, host, cid):
    c = canvas.curso_desde_url(url)
    assert c['host'] == host and c['id'] == cid and c['url'] == f'https://{host}/courses/{cid}'


@pytest.mark.skipif(not shutil.which('powershell'), reason='requiere Windows PowerShell')
@pytest.mark.parametrize('url', ['https://evil.com?.instructure.com/courses/1', 'https://x.instructure.com@evil.com/courses/1',
                                 'https://user@x.instructure.com/courses/1'])
def test_script_rechaza_url_maliciosa_antes_de_usar_el_token(url, tmp_path):
    r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', os.path.join(ROOT, 'publicar_canvas.ps1'),
                        '-Curso', url, '-Carpeta', str(tmp_path), '-SoloRevisar'],
                       env=dict(os.environ, CANVAS_TOKEN='token-que-no-debe-salir-123'), capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=60)
    assert r.returncode == 1
    assert re.search(r'URL del curso|no es de Canvas', r.stdout), r.stdout + r.stderr


def test_vista_previa_aislada():
    html = open(os.path.join(SIS, 'static', 'index.html'), encoding='utf-8').read()
    m = re.search(r'<iframe id="frame"[^>]*>', html)
    assert m and 'sandbox=""' in m.group(0), 'la vista previa debe ir en un iframe sandbox sin scripts'


def test_compose_publica_solo_en_localhost():
    """Sin HTTPS el token viajaría en claro: el puerto solo se publica en 127.0.0.1 (para la red, un proxy TLS delante)."""
    compose = open(os.path.join(ROOT, 'docker-compose.yml'), encoding='utf-8').read()
    puertos = re.findall(r'^\s*-\s*"([^"]+)"', compose, re.M)
    assert puertos and all(p.startswith('127.0.0.1:') for p in puertos), puertos
