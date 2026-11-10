# -*- coding: utf-8 -*-
"""Prueba de estrés del servidor Qwen con una tarea real (extraer la rúbrica de un momento).

    python -m ia.estres --niveles 1 4 16 [--pdf ruta.pdf] [--salida ../reportes_ia]

Por nivel de concurrencia: correctas, JSON válidos, p50/p95/máx, tokens/s agregados. En paralelo
muestrea /metrics de vLLM (peticiones en curso/en cola, uso de KV-cache, preempciones).
"""
import argparse
import glob
import json
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import documento, extractor, qwen

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _una(texto):
    t = time.time()
    try:
        _, d, m = extractor._tarea('rubrica', texto, extractor.ESQ_RUB, 1)
        ok = bool(d.get('indicadores')) and all(i['cocreativo'] for i in d['indicadores'])
        return dict(ok=True, json_ok=ok, seg=time.time() - t, salida=m['salida'], entrada=m['entrada'])
    except Exception as e:
        return dict(ok=False, json_ok=False, seg=time.time() - t, salida=0, entrada=0, err=type(e).__name__)


def _nivel(c, texto):
    n = max(2, c)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=c) as ex:
        rs = list(ex.map(lambda _: _una(texto), range(n)))
    dur = time.time() - t0
    lat = sorted(r['seg'] for r in rs if r['ok'])
    p = lambda q: round(lat[min(len(lat) - 1, int(q * len(lat)))], 1) if lat else None
    return dict(concurrencia=c, peticiones=n, ok=sum(r['ok'] for r in rs), json_validos=sum(r['json_ok'] for r in rs),
                errores=sorted({r['err'] for r in rs if not r['ok']}), duracion=round(dur, 1), p50=p(.5), p95=p(.95),
                max=round(max(lat), 1) if lat else None, tok_s=round(sum(r['salida'] for r in rs) / dur, 1))


def _monitor(muestras, alto):
    base = re.sub(r'/v1$', '', qwen.url())
    while not alto.is_set():
        try:
            t = urllib.request.urlopen(base + '/metrics', timeout=5).read().decode()
            g = lambda k: float((re.search(rf'^vllm:{k}\{{[^}}]*\}} ([\d.e+-]+)', t, re.M) or [0, 0])[1])
            muestras.append(dict(corriendo=g('num_requests_running'), esperando=g('num_requests_waiting'),
                                 kv=round(100 * g('kv_cache_usage_perc'), 1), preempciones=g('num_preemptions_total')))
        except Exception:
            pass
        alto.wait(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--niveles', nargs='+', type=int, default=[1, 2, 4, 8, 16])
    ap.add_argument('--pdf', default=(glob.glob(os.path.join(ROOT, 'silabos_prueba', '*.pdf')) or glob.glob(os.path.join(ROOT, '*.pdf')))[0])
    ap.add_argument('--salida', default=os.path.join(ROOT, 'reportes_ia'))
    a = ap.parse_args()
    if not qwen.disponible():
        raise SystemExit(f'El servidor Qwen no responde ({qwen.url()}).')
    texto = '\n'.join(f['texto'] for f in documento.fragmentos(a.pdf) if f['bloque'] == 'rubrica' and f['momento'] == 1)
    muestras, alto = [], threading.Event()
    hilo = threading.Thread(target=_monitor, args=(muestras, alto), daemon=True)
    hilo.start()
    filas = []
    for c in a.niveles:
        filas.append(_nivel(c, texto))
        print(json.dumps(filas[-1], ensure_ascii=False), flush=True)
    alto.set(); hilo.join(5)
    servidor = dict(max_corriendo=max((m['corriendo'] for m in muestras), default=None),
                    max_esperando=max((m['esperando'] for m in muestras), default=None),
                    max_kv=max((m['kv'] for m in muestras), default=None),
                    preempciones=(muestras[-1]['preempciones'] - muestras[0]['preempciones']) if muestras else None)
    print(json.dumps(dict(servidor=servidor), ensure_ascii=False))
    os.makedirs(a.salida, exist_ok=True)
    with open(os.path.join(a.salida, f'estres_{time.strftime("%Y%m%d_%H%M%S")}.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(niveles=filas, servidor=servidor, pdf=os.path.basename(a.pdf)), f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
