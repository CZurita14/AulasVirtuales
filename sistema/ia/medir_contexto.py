# -*- coding: utf-8 -*-
"""Mide cuánto de la ventana del modelo local (8192 tokens ENTRADA + SALIDA) ocupa cada llamada del sistema.

No genera texto: arma exactamente los mismos mensajes que enviaría el sistema y los cuenta con el tokenizador del
propio servidor (/tokenize con la plantilla de chat). La salida se proyecta con la relación salida/entrada más alta
observada en las corridas reales (reportes_ia/evaluacion_*.json); en las llamadas con tope fijo se usa ese tope.

    cd sistema
    python -m ia.medir_contexto "C:/…/SILABOS B26/**/*.pdf" --guia tests/fixtures/guia_pe_n3.pdf --silabo-guia ../B26_…pdf
    python -m ia.medir_contexto … --vivo     # además, 1 adaptación real de rúbrica (4 llamadas) para medir la salida
"""
import argparse
import glob
import json
import os
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from core import guia, pae, propuestas, silabo
from . import documento, extractor, qwen, vectores

RAIZ = os.path.join(os.path.dirname(__file__), '..', '..')
RIESGO = 0.75            # más del 75 % de la ventana = riesgo (sílabos más largos que los de prueba)


def tokens_chat(sistema, usuario):
    """Tokens exactos de la petición (con plantilla de chat y sin razonamiento), según el servidor."""
    base = qwen.url().rsplit('/v1', 1)[0]
    cuerpo = {'model': qwen.modelo(), 'messages': [{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}],
              'chat_template_kwargs': {'enable_thinking': False}}
    req = urllib.request.Request(base + '/tokenize', method='POST', headers={'Content-Type': 'application/json'},
                                 data=json.dumps(cuerpo).encode('utf-8'))
    with urllib.request.urlopen(req, timeout=15) as r:
        return int(json.load(r)['count'])


def relaciones_reales():
    """{tarea: (max salida/entrada, n)} de las evaluaciones reales guardadas."""
    rel = {}
    for f in glob.glob(os.path.join(RAIZ, 'reportes_ia', 'evaluacion_*.json')):
        for s in json.load(open(f, encoding='utf-8')):
            for c in s['corridas']:
                for t in c.get('tareas', []):
                    if t.get('entrada'):
                        rel.setdefault(t['tarea'], []).append(t['salida'] / t['entrada'])
    return {k: (max(v), len(v)) for k, v in rel.items()}


class Captura:
    """Reemplaza qwen.json_con_esquema: guarda lo que se enviaría y devuelve un JSON vacío."""
    def __init__(self):
        self.llamadas = []

    def __call__(self, sistema, usuario, esquema, nombre='salida', max_tokens=None, **k):
        self.llamadas.append(dict(tarea=nombre, sistema=sistema, usuario=usuario, max_tokens=max_tokens,
                                  caracteres=len(sistema) + len(usuario)))
        return {}, dict(segundos=0, entrada=0, salida=0, fin='stop')


def capturar_silabo(alm, pdf):
    ref = silabo.leer(pdf)
    sid = alm.id_silabo(pdf)
    alm.indexar(sid, documento.fragmentos(pdf))
    cap = Captura()
    original = qwen.json_con_esquema
    qwen.json_con_esquema = cap
    try:
        extractor.extraer(alm, sid, ficha=ref['ficha'], paralelo=1, pdf_path=pdf)
        for m in ref['momentos']:
            propuestas.proposito_ia(m)
    finally:
        qwen.json_con_esquema = original
        alm.borrar(sid)
    return ref, cap.llamadas


def capturar_guia(pdf_silabo, pdf_guia):
    sil = silabo.leer(pdf_silabo)
    cap = Captura()
    original = qwen.json_con_esquema
    qwen.json_con_esquema = cap
    try:
        for g in guia.leer(pdf_guia):
            mom, _, _ = pae.emparejar(g, sil['momentos'])
            if mom:
                pae.adaptar_ia(g, mom, pae.rubrica_base(mom))
    finally:
        qwen.json_con_esquema = original
    for c in cap.llamadas:
        c['tarea'] = 'guia_' + c['tarea']
    return cap.llamadas


def medir(llamadas, rel, ventana):
    with ThreadPoolExecutor(max_workers=4) as ex:
        cuentas = list(ex.map(lambda c: tokens_chat(c['sistema'], c['usuario']), llamadas))
    filas = []
    for c, n in zip(llamadas, cuentas):
        if c['max_tokens']:                       # tope fijo: el peor caso es usarlo entero
            salida, fuente = c['max_tokens'], 'tope'
        else:
            r = rel.get(c['tarea'], (1.0, 0))[0]
            salida, fuente = int(n * r), 'relación real' if c['tarea'] in rel else 'supuesta 1:1'
        filas.append(dict(tarea=c['tarea'], entrada=n, aprox_local=qwen.tokens_aprox(c['sistema'] + c['usuario']),
                          salida_proy=salida, fuente=fuente, total=n + salida, uso=round((n + salida) / ventana, 3)))
    return filas


def resumen(filas, ventana):
    por = {}
    for f in filas:
        por.setdefault(f['tarea'], []).append(f)
    out = {}
    for t, l in sorted(por.items()):
        e = [x['entrada'] for x in l]
        out[t] = dict(llamadas=len(l), entrada_max=max(e), entrada_prom=round(statistics.mean(e)),
                      total_max=max(x['total'] for x in l), uso_max=max(x['uso'] for x in l),
                      en_riesgo=sum(x['uso'] > RIESGO for x in l), no_caben=sum(x['total'] > ventana for x in l),
                      fuente_salida=l[0]['fuente'])
    return out


def vivo(pdf_silabo, pdf_guia):
    """Una adaptación real (4 llamadas) para medir salida y tiempo de la llamada nueva de guías."""
    sil = silabo.leer(pdf_silabo)
    g = guia.leer(pdf_guia)[0]
    mom, _, _ = pae.emparejar(g, sil['momentos'])
    mets, original = [], qwen.json_con_esquema

    def espia(*a, **k):
        d, m = original(*a, **k)
        mets.append(m)
        return d, m
    qwen.json_con_esquema = espia
    try:
        t0 = time.time()
        _, cambiadas, err = pae.adaptar_ia(g, mom, pae.rubrica_base(mom))
    finally:
        qwen.json_con_esquema = original
    return dict(segundos=round(time.time() - t0, 1), cambiadas=cambiadas, error=err, llamadas=mets)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdfs', nargs='*')
    ap.add_argument('--guia'); ap.add_argument('--silabo-guia')
    ap.add_argument('--vivo', action='store_true')
    ap.add_argument('--salida', default=os.path.join(RAIZ, 'reportes_ia'))
    a = ap.parse_args()
    ventana = qwen.contexto()
    rel = relaciones_reales()
    pdfs = sorted({p for patron in a.pdfs for p in glob.glob(patron, recursive=True)})
    alm = vectores.Almacen(url='')
    todas, por_silabo, rechazados = [], [], []
    for pdf in pdfs:
        nombre = os.path.relpath(pdf, os.path.dirname(os.path.dirname(pdf)))
        try:
            ref, llamadas = capturar_silabo(alm, pdf)
        except silabo.FormatoNoReconocido as e:
            rechazados.append(dict(pdf=nombre, motivo=str(e)[:120])); print('  ✘', nombre, '(formato no reconocido)'); continue
        filas = medir(llamadas, rel, ventana)
        for f in filas:
            f['pdf'] = nombre
        todas += filas
        peor = max(filas, key=lambda f: f['uso'])
        por_silabo.append(dict(pdf=nombre, momentos=len(ref['momentos']), sesiones=sum(len(m['sesiones']) for m in ref['momentos']),
                               llamadas=len(filas), tokens_entrada=sum(f['entrada'] for f in filas),
                               tokens_salida_proy=sum(f['salida_proy'] for f in filas),
                               peor=dict(tarea=peor['tarea'], total=peor['total'], uso=peor['uso'])))
        print(f'  ✔ {nombre}: {len(filas)} llamadas, peor {peor["tarea"]} {peor["total"]} tok ({peor["uso"]:.0%})', flush=True)
    guia_filas = []
    if a.guia and a.silabo_guia:
        guia_filas = medir(capturar_guia(a.silabo_guia, a.guia), rel, ventana)
        todas += guia_filas
    rep = dict(fecha=time.strftime('%Y-%m-%d %H:%M'), ventana=ventana, umbral_riesgo=RIESGO, relaciones_reales=rel,
               por_tarea=resumen(todas, ventana), por_silabo=por_silabo, rechazados=rechazados,
               aprox_local=dict(  # qué tan bien estima la cuenta local (len/2.5) frente al tokenizador real
                   razon_min=round(min(f['aprox_local'] / f['entrada'] for f in todas), 2),
                   razon_max=round(max(f['aprox_local'] / f['entrada'] for f in todas), 2)) if todas else {},
               llamadas=todas)
    if a.vivo and a.guia and a.silabo_guia:
        rep['vivo_guia'] = vivo(a.silabo_guia, a.guia)
    os.makedirs(a.salida, exist_ok=True)
    ruta = os.path.join(a.salida, f'contexto_{time.strftime("%Y%m%d_%H%M%S")}.json')
    json.dump(rep, open(ruta, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print('\nPor tipo de llamada (ventana', ventana, '):')
    for t, r in rep['por_tarea'].items():
        print(f'  {t:20s} n={r["llamadas"]:4d}  entrada máx {r["entrada_max"]:5d} (prom {r["entrada_prom"]:4d})  '
              f'total máx {r["total_max"]:5d} = {r["uso_max"]:.0%}  riesgo {r["en_riesgo"]}  no caben {r["no_caben"]}  [{r["fuente_salida"]}]')
    print('Informe:', ruta)


if __name__ == '__main__':
    main()
