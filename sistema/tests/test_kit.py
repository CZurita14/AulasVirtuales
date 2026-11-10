# -*- coding: utf-8 -*-
"""El kit para docentes (prompt maestro + publicar_canvas.ps1) es coherente con el sistema."""
import glob
import os
import re
import shutil
import subprocess
import sys
import threading

import pytest
from bs4 import BeautifulSoup

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import calidad, canvas, propuestas, render, silabo  # noqa: E402
from mock_canvas import CURSO, TOKEN, MockCanvas, servir  # noqa: E402

PROMPT = os.path.join(ROOT, 'PROMPT_MAESTRO_Silabo_a_Canvas.md')
SCRIPT = os.path.join(ROOT, 'publicar_canvas.ps1')
PDF = glob.glob(os.path.join(ROOT, '*.pdf'))[0]


def anexo():
    md = open(PROMPT, encoding='utf-8').read()
    return re.search(r'## ANEXO A.*?```html\n(.*?)\n```', md, re.S).group(1)


def test_prompt_no_pide_token_ni_html():
    md = open(PROMPT, encoding='utf-8').read()
    cuerpo = md.split('## ANEXO A')[0]
    assert 'Nunca pegues tu token en el chat' in cuerpo
    assert 'HTML de la página "Momento 1" de TU curso' not in cuerpo
    assert 'publicar_canvas.ps1' in cuerpo


def test_anexo_es_plantilla_valida_y_genera_html_correcto():
    tpl = anexo()
    info = render.analizar_plantilla(tpl)
    assert info['valida'] and info['vacia'] and info['proposito'] and info['enlaces']
    assert 'HOST' in tpl and 'ID_CURSO' in tpl and not re.search(r'/courses/\d+', tpl)
    sil = silabo.leer(PDF)
    prop = propuestas.proponer(sil)
    curso = dict(host='indoamerica.instructure.com', id='777', slug='inicio')
    for m in sil['momentos']:
        h = render.render(sil, m['n'], tpl, curso, prop['propositos'][m['n']], prop['complementaria'][m['n']])
        res = calidad.controlar(h, m, sil, curso, tpl, prop['complementaria'][m['n']], prop['propositos'][m['n']])
        assert all(r['ok'] for r in res), (m['n'], [r for r in res if not r['ok']])
        for marca in ('Copiar y pegar', 'X.X h', 'dd/mm/aaaa', '[Autor', 'URL_O_DOI', 'HOST', 'ID_CURSO'):
            assert marca not in h, (m['n'], marca)


@pytest.mark.skipif(not shutil.which('powershell'), reason='requiere Windows PowerShell')
def test_script_publica_y_restaura_en_canvas_simulado(tmp_path):
    mock = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    srv, _ = servir(0, mock)
    puerto = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        for f in glob.glob(os.path.join(ROOT, 'html', 'momento-*.html')):
            shutil.copy(f, tmp_path)
        env = dict(os.environ, CANVAS_TOKEN=TOKEN)
        base = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', SCRIPT,
                '-Curso', f'https://indoamerica.instructure.com/courses/{CURSO}', '-Carpeta', str(tmp_path),
                '-ApiBase', f'http://127.0.0.1:{puerto}']
        r = subprocess.run(base + ['-SoloRevisar'], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0 and mock.puts == [], r.stdout + r.stderr
        r = subprocess.run(base + ['-Confirmar'], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0, r.stdout + r.stderr
        assert mock.puts == ['momento-1-2', 'momento-2', 'momento-3', 'momento-4']
        cuerpo = mock.paginas['momento-2']['body']
        assert set(re.findall(r'/courses/(\d+)', cuerpo)) == {CURSO}
        assert 'Planeación y diseño' in BeautifulSoup(cuerpo, 'html.parser').get_text()
        resp = next(p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith('respaldo_'))
        r = subprocess.run(base + ['-Restaurar', str(resp)], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0 and mock.paginas['momento-2']['body'] == render.leer_plantilla_institucional()
        r = subprocess.run(base + ['-SoloRevisar'], env=dict(env, CANVAS_TOKEN='token-malo-123456789'),
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 1 and 'token' in r.stdout.lower()
    finally:
        srv.shutdown()
