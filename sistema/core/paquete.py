# -*- coding: utf-8 -*-
"""Arma la carpeta ZIP que se entrega al docente: HTML por momento + informe + LEEME."""
import html as htmlmod
import io
import re
import unicodedata
import zipfile
from datetime import datetime


def nombre_carpeta(ficha):
    base = f'{ficha.get("periodo", "")}_{ficha.get("proyecto", "curso")}'.strip('_')
    base = ''.join(c for c in unicodedata.normalize('NFD', base) if unicodedata.category(c) != 'Mn')
    base = re.sub(r'[^\w]+', '_', base.title()).strip('_')
    return base or 'Aula_virtual'


def _e(s):
    return htmlmod.escape(str(s))


def informe(sesion):
    sil, curso, adv = sesion['silabo'], sesion['curso'], sesion['advertencias']
    fi = sil['ficha']
    filas = ''.join(
        f'<tr><td>{m["n"]}</td><td>{_e(m["titulo"])}</td><td>{m["inicio"]} – {m["fin"]}</td>'
        f'<td>{", ".join(m["ra"])}</td><td>{len(m["sesiones"])}</td><td>{" / ".join(m["totales"])}</td>'
        f'<td>{len(m["rubrica"])} × 5</td></tr>' for m in sil['momentos'])
    advs = ''.join(f'<li><b>{_e(a["tipo"])}:</b> {_e(a["texto"])}</li>' for a in adv) or '<li>Sin advertencias.</li>'
    obras = {o['clave']: o['texto'] for o in sil['bibliografia']['complementaria']}
    props = ''.join(
        f'<h3>Momento {m["n"]}</h3><p><b>Propósito (PROPUESTO):</b> {_e(sesion["propositos"][m["n"]])}</p>'
        f'<p><b>Bibliografía complementaria asignada:</b></p><ul>'
        + ''.join(f'<li>{_e(obras.get(u, u))}</li>' for u in sesion['complementaria'][m['n']]) + '</ul>'
        f'<p><b>Recursos para el aprendizaje:</b> {_e(m["recursos"])}</p>'
        f'<p><b>Política de IA:</b> {_e(m["politica_ia"])}</p>' for m in sil['momentos'])
    destinos = ''.join(
        f'<tr><td>{n}</td><td>{_e(d["titulo"])}</td><td><a href="{_e(d["url"])}">{_e(d["url"])}</a></td>'
        f'<td>{_e(d["fuente"])}</td><td>{_e(sesion["plantilla_origen"].get(n, ""))}</td>'
        f'<td>{_e(sesion.get("publicacion", {}).get(n, {}).get("mensaje", "No publicada"))}</td></tr>'
        for n, d in sesion.get('destinos', {}).items())
    propuestas_url = [o for lista in sil['bibliografia'].values() for o in lista if not o['url'] and o.get('url_doc')]
    if propuestas_url:
        props += '<h3>Enlaces agregados por el docente (PROPUESTO: no están en el sílabo)</h3><ul>' + ''.join(
            f'<li>{_e(o["texto"])} → <a href="{_e(o["url_doc"])}">{_e(o["url_doc"])}</a></li>' for o in propuestas_url) + '</ul>'
    control = ''
    for n, items in sesion['control'].items():
        ok = sum(i['ok'] for i in items)
        control += f'<h3>momento-{n}.html · {ok}/{len(items)}</h3><ul>' + ''.join(
            f'<li>{"✔" if i["ok"] else "✘"} {_e(i["nombre"])}{(" — " + _e(i["detalle"])) if i["detalle"] else ""}</li>'
            for i in items) + '</ul>'
    return f'''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Informe · {_e(fi.get("proyecto",""))}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:960px;margin:24px auto;color:#2d3748;line-height:1.5;padding:0 16px}}
h1{{color:#230C3E;border-bottom:4px solid #F37121;padding-bottom:6px}}h2{{color:#3A1467;margin-top:28px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border:1px solid #E2DCEB;padding:6px 8px;text-align:left}}
th{{background:#F7F3FB;color:#3A1467}}</style></head><body>
<h1>Informe de generación · {_e(fi.get("proyecto",""))}</h1>
<p>Código {_e(fi.get("codigo",""))} · Periodo {_e(fi.get("periodo",""))} ({_e(fi.get("inicio",""))} a {_e(fi.get("fin",""))}) ·
Docente {_e(fi.get("docente",""))} · Curso Canvas <b>{_e(curso["id"])}</b> {_e(curso.get("nombre",""))} ({_e(curso["url"])}) ·
Generado el {datetime.now():%d/%m/%Y %H:%M}</p>
<h2>Páginas de Canvas</h2><table><tr><th>#</th><th>Página</th><th>URL</th><th>Encontrada por</th><th>Plantilla</th><th>Publicación</th></tr>{destinos}</table>
<h2>Momentos</h2><table><tr><th>#</th><th>Título</th><th>Fechas</th><th>RA</th><th>Sesiones</th><th>Horas D/PE/A</th><th>Rúbrica</th></tr>{filas}</table>
<h2>Advertencias del sílabo</h2><p>No se corrigieron: revísalas con la coordinación si corresponde.</p><ul>{advs}</ul>
<h2>Textos propuestos y contenido para otras páginas del aula</h2>{props}
<h2>Lista de control</h2>{control}
</body></html>'''


LEEME = '''PÁGINAS "MOMENTO N" DEL CURSO
=============================

Curso: {curso}

Si ya publicaste desde el sistema, estos archivos son tu copia. La carpeta "respaldo"
tiene el HTML que había antes en cada página.

Para cargarlas a mano, con cada archivo momento-N.html:
  1. En Canvas abre Páginas -> Momento N -> Editar.
  2. Haz clic en el botón </> (editor HTML).
  3. Copia el HTML actual y guárdalo en un archivo, por si necesitas volver atrás
     (Canvas también guarda el historial de la página).
  4. Selecciona todo, pega el contenido de momento-N.html y guarda.
  5. Completa la columna "Enlaces" donde dice "(Pegar enlace)".

Revisa informe.html: tiene las advertencias del sílabo, los textos propuestos
y el contenido (recursos, política de IA) para otras páginas del aula.
'''


def zip_bytes(sesion):
    carpeta = nombre_carpeta(sesion['silabo']['ficha'])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, h in sesion['paginas'].items():
            z.writestr(f'{carpeta}/momento-{n}.html', h)
        for n, h in sesion.get('respaldos', {}).items():
            z.writestr(f'{carpeta}/respaldo/momento-{n}-anterior.html', h)
        z.writestr(f'{carpeta}/informe.html', informe(sesion))
        z.writestr(f'{carpeta}/LEEME.txt', LEEME.format(curso=sesion['curso']['url']))
    return carpeta, buf.getvalue()
