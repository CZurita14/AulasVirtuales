# -*- coding: utf-8 -*-
"""Genera reportes_ia/visor.html: comparación visual Qwen vs referencia (lectura por reglas).

    python -m ia.visor      (usa la última evaluación de cada sílabo en reportes_ia/)
"""
import glob
import html
import json
import os

from core import propuestas, render, silabo

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REP = os.path.join(ROOT, 'reportes_ia')
CURSO = dict(host='indoamerica.instructure.com', id='36732', slug='inicio')
PDFS = {os.path.basename(p): p for p in glob.glob(os.path.join(ROOT, '*.pdf')) + glob.glob(os.path.join(ROOT, 'silabos_prueba', '*.pdf'))}

# última corrida registrada de cada sílabo
datos = {}
for f in sorted(glob.glob(os.path.join(REP, 'evaluacion_*.json'))):
    for r in json.load(open(f, encoding='utf-8')):
        datos[r['pdf']] = r
e = html.escape
secciones, menu = [], []
for pdf, r in datos.items():
    ref = silabo.leer(PDFS[pdf])
    prop = propuestas.proponer(ref)
    tpl = render.leer_plantilla_institucional()
    base = os.path.splitext(pdf)[0]
    nombre = r['proyecto'].title()
    for c in r['corridas']:
        t, met = c['comparacion']['total'], c['metricas']
        cid = f'{base}_c{c["corrida"]}'
        menu.append(f'<a href="#{e(cid)}">{e(nombre)} · corrida {c["corrida"]}: {t["exactitud"]}%</a>')
        cats = ''.join(f'<tr><td>{e(k)}</td><td>{v["exactos"]}/{v["campos"]}</td><td class="{"ok" if v["exactitud"]==100 else "bad"}">{v["exactitud"]}%</td><td>{v["similitud"]}%</td></tr>'
                       for k, v in c['comparacion']['categorias'].items())
        difs = ''.join(f'<tr><td>{e(x["campo"])}</td><td>{e(x["referencia"])}</td><td class="bad">{e(x["ia"])}</td></tr>'
                       for x in c['comparacion']['filas'] if not x['exacto'])
        pags = ''
        for m in ref['momentos']:
            n = m['n']
            h_ref = render.render(ref, n, tpl, CURSO, prop['propositos'][n], prop['complementaria'][n])
            fq = os.path.join(REP, f'{cid}_momento-{n}.html')
            h_ia = open(fq, encoding='utf-8').read() if os.path.exists(fq) else ''
            p = c['paginas'][str(n)]
            estado = (f'<span class="chip ok">idéntica</span>' if p['identica'] else f'<span class="chip bad">distinta · {p["similitud"]}% similar</span>')
            ctrl = f'checklist {p["control_ok"]}/{p["control_total"]}' + (f' · falla: {e(", ".join(p["fallos"]))}' if p['fallos'] else ' ✔')
            pags += f'''<h3>Momento {n} {estado} <small>{ctrl}</small></h3>
<div class="lado"><div><div class="tit">Generada con datos de <b>Qwen</b></div><iframe srcdoc="{e('<meta charset=utf-8><body style=margin:8px>' + h_ia)}"></iframe></div>
<div><div class="tit">Referencia (la que publicaste)</div><iframe srcdoc="{e('<meta charset=utf-8><body style=margin:8px>' + h_ref)}"></iframe></div></div>'''
        lenta = met['tarea_mas_lenta']
        secciones.append(f'''<section id="{e(cid)}"><h2>{e(nombre)} — corrida {c["corrida"]}</h2>
<p class="kpi"><b>{t["exactitud"]}%</b> de campos idénticos ({t["exactos"]}/{t["campos"]}) · {met["segundos_total"]} s · {met["tareas"]} tareas a Qwen en paralelo ·
tokens {met["tokens_entrada"]} entrada / {met["tokens_salida"]} salida · tarea más lenta: {e(lenta["tarea"])} M{lenta["momento"]} ({lenta["segundos"]} s) · errores: {len(met["errores"])}</p>
<div class="g2"><table><tr><th>Categoría</th><th>Idénticos</th><th>Exactitud</th><th>Similitud</th></tr>{cats}</table>
<div><b>Campos donde Qwen difiere ({sum(1 for x in c["comparacion"]["filas"] if not x["exacto"])})</b><div class="scroll"><table><tr><th>Campo</th><th>Sílabo (referencia)</th><th>Qwen</th></tr>{difs or '<tr><td colspan=3>Ninguno ✔</td></tr>'}</table></div></div></div>
{pags}</section>''')

out = f'''<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Pruebas Qwen · aula virtual</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f6f4f9;color:#2d3748}}header{{background:linear-gradient(135deg,#3A1467,#230C3E);color:#fff;padding:16px 24px;border-bottom:4px solid #F37121}}
nav{{padding:10px 24px;background:#fff;border-bottom:1px solid #e2dceb;display:flex;gap:16px;flex-wrap:wrap}}nav a{{color:#3A1467;font-size:14px}}
section{{background:#fff;margin:16px 24px;padding:18px;border-radius:10px;border:1px solid #e2dceb}}h2{{color:#230C3E;margin:0 0 6px}}h3{{margin:22px 0 8px;color:#3A1467}}h3 small{{font-weight:400;color:#6b6480;font-size:13px}}
.kpi{{font-size:14px}}.g2{{display:grid;grid-template-columns:360px 1fr;gap:16px}}table{{border-collapse:collapse;font-size:12.5px;width:100%}}td,th{{border:1px solid #e2dceb;padding:4px 6px;text-align:left;vertical-align:top}}th{{background:#f7f3fb}}
.scroll{{max-height:260px;overflow:auto}}.ok{{color:#1e7b4f;font-weight:600}}.bad{{color:#b42318}}.chip{{font-size:12px;padding:2px 8px;border-radius:12px}}.chip.ok{{background:#e7f5ee}}.chip.bad{{background:#fde8e6}}
.lado{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.tit{{font-size:13px;margin-bottom:4px}}iframe{{width:100%;height:520px;border:1px solid #cbd5e0;border-radius:8px;background:#fff}}</style></head>
<body><header><b>Pruebas con el modelo local de la universidad</b> · Qwen3-8B-AWQ (vLLM, 172.16.8.69) · BD vectorial Qdrant · mismo renderizador y misma plantilla</header>
<nav>{"".join(menu)}</nav>{"".join(secciones)}</body></html>'''
open(os.path.join(REP, 'visor.html'), 'w', encoding='utf-8').write(out)
print('ok', os.path.join(REP, 'visor.html'))
