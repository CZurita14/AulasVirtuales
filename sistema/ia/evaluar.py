# -*- coding: utf-8 -*-
"""Evalúa si Qwen reproduce la misma aula virtual que la lectura por reglas.

    python -m ia.evaluar ../silabos_prueba/silabo.pdf [más PDF…] [--repeticiones 3] [--salida reportes/]
"""
import argparse
import json
import os
import time

from core import silabo
from . import comparar, documento, extractor, vectores

CURSO = dict(host='indoamerica.instructure.com', id='36732', slug='inicio')


def evaluar_pdf(alm, pdf, rep=1):
    ref = silabo.leer(pdf)
    sid = alm.id_silabo(pdf)
    frs = documento.fragmentos(pdf)
    alm.indexar(sid, frs)
    corridas = []
    for i in range(rep):
        ia, met = extractor.extraer(alm, sid, ficha=ref['ficha'], pdf_path=pdf)
        cmp_ = comparar.comparar(ref, ia)
        pag = comparar.paginas(ref, ia, CURSO)
        corridas.append(dict(corrida=i + 1, metricas={k: v for k, v in met.items() if k != 'metricas'},
                             tareas=met['metricas'], comparacion=cmp_,
                             paginas={n: {k: v for k, v in p.items() if k != 'html'} for n, p in pag.items()},
                             html={n: p['html'] for n, p in pag.items()}))
    return dict(pdf=os.path.basename(pdf), fragmentos=len(frs), proyecto=ref['ficha'].get('proyecto'), corridas=corridas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdfs', nargs='+')
    ap.add_argument('--repeticiones', type=int, default=1)
    ap.add_argument('--salida', default=os.path.join(os.path.dirname(__file__), '..', '..', 'reportes_ia'))
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    alm = vectores.Almacen()
    todo = []
    for pdf in a.pdfs:
        print(f'== {os.path.basename(pdf)}', flush=True)
        r = evaluar_pdf(alm, pdf, a.repeticiones)
        for c in r['corridas']:
            t = c['comparacion']['total']
            pg = c['paginas']
            print(f"  corrida {c['corrida']}: {c['metricas']['segundos_total']} s · exactitud campos {t['exactitud']}% "
                  f"({t['exactos']}/{t['campos']}) · páginas idénticas {sum(p['identica'] for p in pg.values())}/{len(pg)} · "
                  f"errores {len(c['metricas']['errores'])}", flush=True)
            for cat, v in c['comparacion']['categorias'].items():
                print(f"     {cat:20} exactos {v['exactitud']:5}%  similitud {v['similitud']:5}%")
            base = os.path.join(a.salida, f"{os.path.splitext(r['pdf'])[0]}_c{c['corrida']}")
            for n, h in c['html'].items():
                with open(f'{base}_momento-{n}.html', 'w', encoding='utf-8') as f:
                    f.write(h)
        for c in r['corridas']:
            c.pop('html')
        todo.append(r)
    with open(os.path.join(a.salida, f'evaluacion_{time.strftime("%Y%m%d_%H%M%S")}.json'), 'w', encoding='utf-8') as f:
        json.dump(todo, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
