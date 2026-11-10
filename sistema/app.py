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

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from core import paquete, servicio

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
def inicio():
    return FileResponse(os.path.join(BASE, 'static', 'index.html'))


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
    try:
        s = servicio.analizar(io.BytesIO(datos), url, token, transport=TRANSPORT)
    except servicio.ErrorEntrada as e:
        raise HTTPException(422, str(e))
    finally:
        token = None  # noqa: F841  (no conservar el token fuera de la sesión)
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
    try:
        return dict(resultados=servicio.publicar(s, p.momentos, p.confirmado))
    except servicio.ErrorEntrada as e:
        raise HTTPException(409, str(e))


class Restauracion(BaseModel):
    sid: str
    momento: int


@app.post('/api/restaurar')
def restaurar(r: Restauracion):
    s = _sesion(r.sid)
    try:
        return servicio.restaurar(s, r.momento)
    except servicio.ErrorEntrada as e:
        raise HTTPException(409, str(e))


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


@app.exception_handler(Exception)
async def _error(request, exc):
    return JSONResponse(status_code=500, content={'detail': f'Error inesperado: {type(exc).__name__}'})
