# -*- coding: utf-8 -*-
"""Sílabo → Aula virtual · servidor web (FastAPI).

Ejecutar:  python -m uvicorn app:app --host 127.0.0.1 --port 8770   (desde la carpeta sistema/)
El token del docente solo vive en memoria durante la sesión: no se guarda, no se registra y no vuelve
al navegador. Si se publica en red, debe ir detrás de HTTPS.
"""
import io
import os
import secrets
import threading
import time

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from core import historial, paquete, servicio

BASE = os.path.dirname(os.path.abspath(__file__))
MAX_PDF = 15 * 1024 * 1024
TTL = 3600
TRANSPORT = None  # las pruebas inyectan aquí un Canvas simulado (httpx.MockTransport)

app = FastAPI(title='Sílabo → Aula virtual', docs_url=None, redoc_url=None)
_sesiones = {}
_lock = threading.Lock()


@app.middleware('http')
async def sin_cache_documental(request, call_next):
    respuesta = await call_next(request)
    respuesta.headers['Cache-Control'] = 'no-store'
    return respuesta


def _hist(tipo, accion, resultado, s=None, archivos=None, detalle='', enlaces=(), curso=None):
    """Anota en el historial; nunca interrumpe el flujo del docente."""
    try:
        if curso is None and s:
            c = s.get('curso') or {}
            curso = dict(id=c.get('id', ''), nombre=c.get('nombre', ''))
        historial.registrar(tipo, accion, resultado,
                            archivos=archivos if archivos is not None else (s or {}).get('_archivos', []),
                            curso=curso, detalle=detalle, enlaces=enlaces)
    except Exception:  # noqa: BLE001
        pass


def _curso_url(url):
    from core import canvas
    c = canvas.curso_desde_url(url) or {}
    return dict(id=c.get('id', ''), nombre='')


@app.on_event('startup')
def _sembrar_historial():
    try:
        historial.sembrar()
    except Exception:  # noqa: BLE001
        pass


def _limpiar():
    ahora = time.time()
    with _lock:
        vencidas = [k for k, v in _sesiones.items() if ahora - v['_t'] > TTL]
        for k in vencidas:
            servicio.cerrar(_sesiones.pop(k))


def _sesion(sid):
    _limpiar()
    s = _sesiones.get(sid)
    if not s:
        raise HTTPException(404, 'La sesión expiró o ya terminó. Vuelve a cargar el sílabo.')
    s['_t'] = time.time()
    return s


@app.get('/')
def menu():
    return FileResponse(os.path.join(BASE, 'static', 'menu.html'))


@app.get('/silabos')
def inicio():
    return FileResponse(os.path.join(BASE, 'static', 'index.html'))


@app.get('/guias')
def guias_pagina():
    return FileResponse(os.path.join(BASE, 'static', 'guias.html'))


@app.get('/api/salud')
def salud():
    from ia import salud as _salud
    return _salud.estado()


@app.post('/api/analizar')
async def analizar(pdf: UploadFile = File(...), url: str = Form(''), token: str = Form(''), usar_ia: str = Form('0')):
    datos = await pdf.read()
    if len(datos) > MAX_PDF:
        raise HTTPException(413, 'El PDF supera 15 MB.')
    if not datos.startswith(b'%PDF'):
        raise HTTPException(422, 'El archivo no es un PDF.')
    if not token.strip():
        raise HTTPException(422, 'Falta el token de acceso de Canvas.')
    nombre = os.path.basename(pdf.filename or 'silabo.pdf')
    try:
        s = servicio.analizar(io.BytesIO(datos), url, token, transport=TRANSPORT)
    except servicio.ErrorEntrada as e:
        _hist('silabos', 'Analizar', 'error', archivos=[nombre], detalle=str(e), curso=_curso_url(url))
        raise HTTPException(422, str(e))
    finally:
        token = None  # noqa: F841  (no conservar el token fuera de la sesión)
    s['_archivos'] = [nombre]
    graves = sum(1 for a in s['advertencias'] if a.get('grave'))
    _hist('silabos', 'Analizado', 'avisos' if graves else 'ok', s,
          detalle=f'{len(s["silabo"]["momentos"])} momentos' + (f'; {graves} avisos importantes' if graves else ''))
    sid = secrets.token_urlsafe(16)
    s['_t'] = time.time()
    _limpiar()
    with _lock:
        _sesiones[sid] = s
    from ia import trabajo
    if usar_ia == '1' and os.environ.get('IA_ACTIVA', '1') == '1':
        trabajo.iniciar(s, datos)       # segunda lectura en segundo plano; no bloquea
    else:
        trabajo.desactivar(s)
    return dict(sid=sid, ia=trabajo.estado_publico(s), **servicio.resumen(s))


@app.get('/api/ia/{sid}')
def estado_ia(sid: str):
    from ia import trabajo
    return trabajo.estado_publico(_sesion(sid))


class Edicion(BaseModel):
    sid: str
    propositos: dict[str, str] = {}
    complementaria: dict[str, list[str]] = {}
    urls: dict[str, str] | None = None


@app.post('/api/generar')
def generar(e: Edicion):
    s = _sesion(e.sid)
    servicio.generar(s, e.propositos, e.complementaria, e.urls)
    return dict(paginas=s['paginas'], control=s['control'], listo=s['listo'])


class Publicacion(BaseModel):
    sid: str
    momentos: list[int]
    confirmado: bool = False


@app.post('/api/publicar')
def publicar(p: Publicacion):
    s = _sesion(p.sid)
    lista = ', '.join(str(n) for n in sorted(p.momentos))
    try:
        res = servicio.publicar(s, p.momentos, p.confirmado)
    except servicio.ErrorEntrada as e:
        _hist('silabos', f'Publicar Momentos {lista}', 'error', s, detalle=str(e))
        raise HTTPException(409, str(e))
    oks = [n for n, r in res.items() if r.get('ok')]
    _hist('silabos', f'Publicado Momentos {lista}' if oks else f'Publicar Momentos {lista}',
          'ok' if len(oks) == len(res) else ('avisos' if oks else 'error'), s,
          detalle='; '.join(f'Momento {n}: {r.get("mensaje", "")}' for n, r in sorted(res.items()) if not r.get('ok')),
          enlaces=[dict(texto=f'Momento {n}', url=r['url']) for n, r in sorted(res.items()) if r.get('url')])
    return dict(resultados=res)


class Restauracion(BaseModel):
    sid: str
    momento: int


@app.post('/api/restaurar')
def restaurar(r: Restauracion):
    s = _sesion(r.sid)
    try:
        res = servicio.restaurar(s, r.momento)
    except servicio.ErrorEntrada as e:
        _hist('silabos', f'Restaurar Momento {r.momento}', 'error', s, detalle=str(e))
        raise HTTPException(409, str(e))
    _hist('silabos', f'Restaurado Momento {r.momento}', 'ok', s, detalle=res.get('mensaje', ''),
          enlaces=[dict(texto=f'Momento {r.momento}', url=res['url'])] if res.get('url') else ())
    return res


@app.get('/api/descargar/{sid}')
def descargar(sid: str):
    s = _sesion(sid)
    if not s.get('listo'):
        raise HTTPException(409, 'Falta generar una vista previa completa y actualizada antes de descargar.')
    carpeta, data = paquete.zip_bytes(s)
    return StreamingResponse(io.BytesIO(data), media_type='application/zip',
                             headers={'Content-Disposition': f'attachment; filename="{carpeta}.zip"'})


@app.post('/api/terminar/{sid}')
def terminar(sid: str):
    with _lock:
        s = _sesiones.pop(sid, None)
    if s:
        servicio.cerrar(s)
    return dict(ok=True)


# ======================= Guías prácticas → tareas PAE + rúbricas =======================
def _pdf_ok(datos, nombre):
    if len(datos) > MAX_PDF:
        raise HTTPException(413, f'{nombre}: el PDF supera 15 MB.')
    if not datos.startswith(b'%PDF'):
        raise HTTPException(422, f'{nombre}: el archivo no es un PDF.')


def _pae(it):
    return it['nombre'].split('-', 1)[0]


def _hist_pae(s, nuevos):
    """Una fila por pulsación de "Crear en Canvas" con lo que se creó de verdad (no repite lo ya creado)."""
    if not nuevos:
        return
    items = s['items']
    oks = [i for i, r in nuevos.items() if r.get('ok')]
    enl = []
    for i in oks:
        for clave, nombre in (('url_tarea', 'Tarea'), ('url_rubrica', 'Rúbrica')):
            if nuevos[i].get(clave):
                enl.append(dict(texto=f'{nombre} {_pae(items[i])}', url=nuevos[i][clave]))
    verificados = all(nuevos[i].get('verificado', True) for i in oks)
    _hist('guias', ('PAE creadas: ' if oks else 'Crear PAE: ') + ', '.join(_pae(items[i]) for i in (oks or nuevos)),
          'ok' if len(oks) == len(nuevos) and verificados else ('avisos' if oks else 'error'), s,
          archivos=[items[i]['guia'].get('archivo', '') for i in nuevos],
          detalle='; '.join(f'{_pae(items[i])}: {r.get("mensaje", "")}' for i, r in nuevos.items()
                            if not r.get('ok') or not r.get('verificado', True)),
          enlaces=enl)


def _sesion_guias(sid):
    s = _sesion(sid)
    if s.get('tipo') != 'guias':
        raise HTTPException(404, 'La sesión no es de guías prácticas.')
    return s


@app.post('/api/guias/analizar')
async def guias_analizar(silabo: UploadFile = File(...), guias: list[UploadFile] = File(...),
                         url: str = Form(''), token: str = Form('')):
    from core import servicio_guias
    if len(guias) > 20:
        raise HTTPException(422, 'Carga como máximo 20 guías a la vez.')
    sil = await silabo.read()
    _pdf_ok(sil, 'Sílabo')
    archivos = []
    for g in guias:
        d = await g.read()
        _pdf_ok(d, g.filename or 'Guía')
        archivos.append((os.path.basename(g.filename or 'guia.pdf'), io.BytesIO(d)))
    if not token.strip():
        raise HTTPException(422, 'Falta el token de acceso de Canvas.')
    nombre_sil = os.path.basename(silabo.filename or 'silabo.pdf')
    nombres = [n for n, _ in archivos]
    try:
        s = servicio_guias.analizar(io.BytesIO(sil), archivos, url, token, transport=TRANSPORT)
    except servicio.ErrorEntrada as e:
        _hist('guias', 'Analizar', 'error', archivos=nombres, detalle=f'Sílabo: {nombre_sil}. {e}', curso=_curso_url(url))
        raise HTTPException(422, str(e))
    finally:
        token = None  # noqa: F841
    s['_archivos'] = nombres
    _hist('guias', 'Analizado', 'ok', s,
          detalle=f'Sílabo: {nombre_sil}. Guías: ' + ', '.join(_pae(it) for it in s['items']))
    sid = secrets.token_urlsafe(16)
    s['_t'] = time.time()
    _limpiar()
    with _lock:
        _sesiones[sid] = s
    from ia import qwen
    ia = os.environ.get('IA_ACTIVA', '1') == '1' and qwen.disponible()
    return dict(sid=sid, ia=ia, **servicio_guias.resumen(s))


@app.post('/api/guias/adaptar/{sid}/{i}')
def guias_adaptar(sid: str, i: int):
    from core import servicio_guias
    s = _sesion_guias(sid)
    if not 0 <= i < len(s['items']):
        raise HTTPException(404, 'Guía no encontrada.')
    try:
        return servicio_guias.adaptar(s, i)
    except servicio.ErrorEntrada as e:
        raise HTTPException(409, str(e))


class EdicionGuias(BaseModel):
    sid: str
    grupo_id: int | None = None
    items: list[dict] = []


@app.post('/api/guias/generar')
def guias_generar(e: EdicionGuias):
    from core import servicio_guias
    s = _sesion_guias(e.sid)
    try:
        return servicio_guias.generar(s, dict(grupo_id=e.grupo_id, items=e.items))
    except (servicio.ErrorEntrada, IndexError, KeyError, ValueError) as ex:
        raise HTTPException(422, str(ex) if isinstance(ex, servicio.ErrorEntrada) else 'Datos de edición no válidos.')


class SoloSesion(BaseModel):
    sid: str


@app.post('/api/guias/estado')
def guias_estado(e: SoloSesion):
    from core import servicio_guias
    return servicio_guias.resumen(_sesion_guias(e.sid))


class PublicacionGuias(BaseModel):
    sid: str
    indices: list[int]
    confirmado: bool = False


@app.post('/api/guias/publicar')
def guias_publicar(p: PublicacionGuias):
    from core import servicio_guias
    s = _sesion_guias(p.sid)
    if any(not 0 <= i < len(s['items']) for i in p.indices):
        raise HTTPException(404, 'Guía no encontrada.')
    previos = {i for i in p.indices if s['items'][i].get('creado')}
    try:
        res = servicio_guias.publicar(s, p.indices, p.confirmado)
    except servicio.ErrorEntrada as e:
        _hist('guias', 'Crear PAE', 'error', s, detalle=str(e))
        raise HTTPException(409, str(e))
    _hist_pae(s, {i: r for i, r in res.items() if i not in previos and r.get('mensaje') != 'No marcada para publicar.'})
    return dict(resultados=res)


class DeshacerGuia(BaseModel):
    sid: str
    i: int


@app.post('/api/guias/deshacer')
def guias_deshacer(d: DeshacerGuia):
    from core import servicio_guias
    s = _sesion_guias(d.sid)
    if not 0 <= d.i < len(s['items']):
        raise HTTPException(404, 'Guía no encontrada.')
    pae = _pae(s['items'][d.i])
    try:
        res = servicio_guias.deshacer(s, d.i)
    except servicio.ErrorEntrada as e:
        _hist('guias', f'Deshacer {pae}', 'error', s, detalle=str(e))
        raise HTTPException(409, str(e))
    _hist('guias', f'Deshecho: {pae}', 'ok', s, archivos=[s['items'][d.i]['guia'].get('archivo', '')],
          detalle=res.get('mensaje', ''))
    return res


# ======================= Historial de cargas =======================
def _por_proxy(request):
    """La petición llegó a través de un proxy (nginx del servidor), no desde el propio equipo."""
    return bool(request.headers.get('x-forwarded-for') or request.headers.get('x-real-ip'))


def _abierto_sin_clave(request):
    """Sin clave solo se abre si se pidió expresamente (HISTORIAL_LOCAL=1, en el propio equipo) y la petición no
    viene de un proxy. No depende solo de cabeceras: por defecto, sin clave, está cerrado."""
    return historial.local() and not _por_proxy(request)


def _acceso_historial(request, x_clave):
    """Falla cerrado: sin HISTORIAL_CLAVE el historial solo se ve con HISTORIAL_LOCAL=1 y sin proxy.
    La clave solo viaja en la cabecera X-Historial-Clave (nunca en la URL)."""
    if not historial.habilitado():
        raise HTTPException(404, 'El historial está desactivado.')
    k = historial.clave()
    if not k:
        if not _abierto_sin_clave(request):
            raise HTTPException(403, 'El historial necesita HISTORIAL_CLAVE en el archivo .env '
                                     '(o HISTORIAL_LOCAL=1 si el sistema solo se usa en este equipo).')
        return
    if not secrets.compare_digest((x_clave or '').encode('utf-8'), k.encode('utf-8')):
        raise HTTPException(401, 'Falta la clave del historial o no es correcta.')


_FORMULA = ('=', '+', '-', '@', '\t', '\r')


def _celda_csv(v):
    """Evita que Excel interprete un nombre de archivo o una nota como fórmula."""
    v = str(v if v is not None else '')
    return "'" + v if v.startswith(_FORMULA) else v


@app.get('/historial')
def historial_pagina():
    return FileResponse(os.path.join(BASE, 'static', 'historial.html'))


@app.get('/api/historial/estado')
def historial_estado(request: Request):
    return dict(habilitado=historial.habilitado(), requiere_clave=bool(historial.clave()) or not _abierto_sin_clave(request))


@app.get('/api/historial')
def historial_listar(tipo: str = '', curso: str = '', q: str = '', orden: str = 'desc',
                     request: Request = None, x_historial_clave: str = Header('')):
    _acceso_historial(request, x_historial_clave)
    todos = historial.listar()
    cursos = {}
    for e in todos:
        if e['curso_id'] and (e['curso_nombre'] or e['curso_id'] not in cursos):
            cursos[e['curso_id']] = e['curso_nombre'] or cursos.get(e['curso_id'], '')
    filas = historial.listar(tipo=tipo or None, curso=curso or None, texto=q.strip() or None, orden=orden)
    return dict(eventos=filas, resumen=historial.resumen(filas),
                cursos=[dict(id=k, nombre=v) for k, v in sorted(cursos.items(), key=lambda kv: kv[1] or kv[0])])


class Correccion(BaseModel):
    resultado: str
    nota: str = ''


@app.post('/api/historial/{id_}/corregir')
def historial_corregir(id_: int, c: Correccion, request: Request = None, x_historial_clave: str = Header('')):
    _acceso_historial(request, x_historial_clave)
    if c.resultado not in historial.RESULTADOS or len(c.nota) > 500:
        raise HTTPException(422, 'Resultado no válido o nota de más de 500 caracteres.')
    try:
        return historial.corregir(id_, c.resultado, c.nota)
    except KeyError:
        raise HTTPException(404, 'Registro no encontrado.')


@app.delete('/api/historial/{id_}/correccion')
def historial_quitar(id_: int, request: Request = None, x_historial_clave: str = Header('')):
    _acceso_historial(request, x_historial_clave)
    try:
        return historial.quitar_correccion(id_)
    except KeyError:
        raise HTTPException(404, 'Registro no encontrado.')


@app.get('/api/historial.csv')
def historial_csv(tipo: str = '', curso: str = '', q: str = '', request: Request = None, x_historial_clave: str = Header('')):
    import csv
    _acceso_historial(request, x_historial_clave)
    out = io.StringIO()
    w = csv.writer(out, delimiter=';', lineterminator='\r\n')
    w.writerow(['fecha', 'tipo', 'archivos', 'curso', 'accion', 'resultado', 'resultado_corregido', 'nota',
                'detalle', 'reconstruido', 'fuente'])
    for e in historial.listar(tipo=tipo or None, curso=curso or None, texto=q.strip() or None):
        corr = e['correccion'] or {}
        w.writerow([_celda_csv(x) for x in [e['fecha'], 'Sílabos' if e['tipo'] == 'silabos' else 'Guías', ', '.join(e['archivos']),
                    f'{e["curso_nombre"]} ({e["curso_id"]})' if e['curso_id'] else '', e['accion'], e['resultado'],
                    corr.get('resultado', ''), corr.get('nota', ''), e['detalle'], 'sí' if e['reconstruido'] else 'no',
                    e['fuente']]])
    datos = ('﻿' + out.getvalue()).encode('utf-8')
    return StreamingResponse(io.BytesIO(datos), media_type='text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename="historial_cargas.csv"'})


@app.exception_handler(Exception)
async def _error(request, exc):
    return JSONResponse(status_code=500, content={'detail': f'Error inesperado: {type(exc).__name__}'})
