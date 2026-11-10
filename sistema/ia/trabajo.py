# -*- coding: utf-8 -*-
"""Segunda lectura del sílabo con la IA, en segundo plano.

- No bloquea: el docente sigue con la lectura por reglas mientras Qwen trabaja (~70–90 s).
- Solo informa diferencias (concordancia); lo publicado sale de las reglas.
- Excepción: si las reglas dejaron un bloque VACÍO (momento sin sesiones o sin rúbrica, RA sin texto),
  se completa con la lectura de la IA y se avisa "Leído por IA, revisar".
"""
import copy
import logging
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from core import propuestas

from . import concordancia, documento, extractor, qwen, vectores

_alm = {}
_lock = threading.Lock()
log = logging.getLogger('silabo.ia')


def _almacen():
    url = os.environ.get('QDRANT_URL', '')
    with _lock:
        if url not in _alm:
            _alm[url] = vectores.Almacen(url)
        return _alm[url]


_TAREAS_SESIONES = {'sesion', 'sesiones', 'pie'}


def fusionar(ref, ia, errores=()):
    """Copia de `ref` con los bloques vacíos completados desde `ia`. Devuelve (sil, ['M3.rubrica', …]).
    Un bloque no se completa si alguna tarea de la IA que lo alimenta falló (resultado parcial)."""
    fallidas = {(x.get('tarea'), x.get('momento')) for x in errores}
    falla = lambda tareas, n: any((t, n) in fallidas for t in tareas)
    sil = copy.deepcopy(ref)
    bloques = []
    por_n = {m['n']: m for m in ia.get('momentos', [])}
    for m in sil['momentos']:
        x = por_n.get(m['n'])
        if not x:
            continue
        if not m['sesiones'] and x.get('sesiones') and not falla(_TAREAS_SESIONES, m['n']):
            m['sesiones'], m['totales'] = copy.deepcopy(x['sesiones']), tuple(x.get('totales', ('', '', '')))
            bloques.append(f'M{m["n"]}.sesiones')
        if not m['rubrica'] and x.get('rubrica') and not falla({'rubrica'}, m['n']):
            m['rubrica'] = copy.deepcopy(x['rubrica'])
            m['rubrica_ev'] = m.get('rubrica_ev') or x.get('rubrica_ev', '')
            bloques.append(f'M{m["n"]}.rubrica')
    if not falla({'ra'}, None):
        for code in sorted({c for m in sil['momentos'] for c in m['ra']}):
            if not sil['ra'].get(code) and ia.get('ra', {}).get(code):
                sil['ra'][code] = ia['ra'][code]
                bloques.append(code)
    return sil, bloques


def revalidar(sesion, sil, bloques):
    """Tras completar bloques con la IA: datos nuevos, advertencias recalculadas (quita las viejas y vuelve a
    controlar horas y fechas) y la vista previa anterior deja de servir para publicar."""
    from core import validador
    conservadas = [a for a in sesion.get('advertencias', []) if a.get('tipo') in ('Canvas', 'Curso')]
    sesion['silabo'] = sil
    sesion['advertencias'] = validador.validar(sil, sesion.get('curso'), None) + conservadas + [dict(
        tipo='Leído por IA', grave=True, texto=(
            'Estos bloques no se pudieron leer por reglas y se completaron con la IA: ' + ', '.join(bloques) +
            '. Genera la vista previa de nuevo y revísalos antes de publicar.'))]
    sesion['version_datos'] = sesion.get('version_datos', 0) + 1
    sesion['listo'] = False


def estado_publico(sesion):
    e = sesion.get('ia') or dict(estado='desactivada')
    return {k: e.get(k) for k in ('estado', 'avance', 'segundos', 'discrepancias', 'resumen', 'bloques_ia', 'propositos', 'error')}


def desactivar(sesion):
    sesion['ia'] = dict(estado='desactivada', avance=0.0, segundos=0, discrepancias=[], resumen=None, bloques_ia=[], propositos={}, error=None)


def iniciar(sesion, pdf_bytes):
    sesion['ia'] = dict(estado='pendiente', avance=0.0, segundos=0, discrepancias=[], resumen=None, bloques_ia=[], propositos={}, error=None)
    if not qwen.disponible():
        sesion['ia']['estado'] = 'no_disponible'
        return
    threading.Thread(target=_correr, args=(sesion, pdf_bytes), daemon=True).start()


def _correr(sesion, pdf_bytes):
    e = sesion['ia']
    e['estado'] = 'en_curso'
    t0 = time.time()
    fd, ruta = tempfile.mkstemp(suffix='.pdf')
    alm, sid = None, None
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(pdf_bytes)
        alm = _almacen()
        sid = f'{alm.id_silabo(ruta)}-{uuid.uuid4().hex[:8]}'   # identificador propio de esta lectura
        alm.indexar(sid, documento.fragmentos(ruta))

        def avance(hechas, total):
            e['avance'] = round(hechas / max(1, total), 2)

        ia, met = extractor.extraer(alm, sid, ficha=sesion['silabo'].get('ficha'),
                                    paralelo=int(os.environ.get('IA_PARALELO', '6')), pdf_path=ruta, al_avanzar=avance)
        errores = met.get('errores', [])
        e['errores_tareas'] = errores
        if errores and len(errores) * 2 >= max(1, met.get('tareas', 0)):
            raise RuntimeError(f'{len(errores)} de {met.get("tareas")} tareas de la IA fallaron')
        ref = sesion['silabo']
        e['discrepancias'] = concordancia.discrepancias(ref, ia)
        e['resumen'] = concordancia.resumen(e['discrepancias'])
        sil, bloques = fusionar(ref, ia, errores)
        if bloques:
            revalidar(sesion, sil, bloques)
        e['bloques_ia'] = bloques
        with ThreadPoolExecutor(max_workers=4) as ex:   # redacción de la IA como sugerencia (PROPUESTO)
            sugeridos = list(ex.map(propuestas.proposito_ia, sesion['silabo']['momentos']))
        e['propositos'] = {str(m['n']): p for m, p in zip(sesion['silabo']['momentos'], sugeridos) if p}
        e['avance'] = 1.0
        e['estado'] = 'listo'
    except qwen.QwenNoDisponible:
        e['estado'], e['error'] = 'no_disponible', 'El servidor de IA de la universidad no respondió a tiempo.'
    except Exception:  # la IA nunca rompe el flujo del docente; el detalle solo va al registro del servidor
        log.exception('Fallo en la segunda lectura con IA')
        e['estado'] = 'error'
        e['error'] = 'La revisión con IA no se pudo completar. Puedes continuar: la lectura por reglas no se ve afectada.'
    finally:
        e['segundos'] = round(time.time() - t0, 1)
        if alm is not None and sid:      # la BD vectorial no conserva el sílabo (tiene datos del docente)
            try:
                alm.borrar(sid)
            except Exception:
                log.exception('No se pudieron borrar los fragmentos del sílabo')
        try:
            os.remove(ruta)
        except OSError:
            pass
