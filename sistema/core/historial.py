# -*- coding: utf-8 -*-
"""Historial de cargas del docente (SQLite).

Guarda qué se analizó y publicó: fecha, tipo (Sílabos/Guías), nombres de archivo, curso, acción, resultado y enlaces.
Nunca guarda el token ni el contenido del PDF. Si el historial falla o está apagado, el sistema sigue igual.

    HISTORIAL_DB     ruta de la base (por defecto <raíz>/datos/historial.sqlite; en Docker /datos/historial.sqlite)
    HISTORIAL=0      lo apaga
    HISTORIAL_CLAVE  si está definida, la API exige esta clave (para publicarlo en un servidor)
    HISTORIAL_LOCAL=1  sin clave, permite verlo en el propio equipo (por defecto, sin clave está cerrado)
"""
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

RESULTADOS = ('ok', 'error', 'avisos')
TIPOS = ('silabos', 'guias')
ECUADOR = timezone(timedelta(hours=-5))
_lock = threading.Lock()
_log = logging.getLogger('historial')

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL, tipo TEXT NOT NULL, archivos TEXT NOT NULL DEFAULT '[]',
    curso_id TEXT NOT NULL DEFAULT '', curso_nombre TEXT NOT NULL DEFAULT '',
    accion TEXT NOT NULL, resultado TEXT NOT NULL, detalle TEXT NOT NULL DEFAULT '',
    enlaces TEXT NOT NULL DEFAULT '[]', reconstruido INTEGER NOT NULL DEFAULT 0, fuente TEXT NOT NULL DEFAULT '',
    corr_resultado TEXT, corr_nota TEXT, corr_fecha TEXT);
CREATE TABLE IF NOT EXISTS meta (clave TEXT PRIMARY KEY, valor TEXT);
"""


def ruta():
    defecto = os.path.join(os.path.dirname(__file__), '..', '..', 'datos', 'historial.sqlite')
    return os.path.abspath(os.environ.get('HISTORIAL_DB') or defecto)


def habilitado():
    return os.environ.get('HISTORIAL', '1') != '0'


def local():
    """HISTORIAL_LOCAL=1: el sistema solo se usa en este equipo y el historial puede abrirse sin clave."""
    return os.environ.get('HISTORIAL_LOCAL', '0') == '1'


def clave():
    return os.environ.get('HISTORIAL_CLAVE', '')


def ahora():
    return datetime.now(ECUADOR).strftime('%Y-%m-%dT%H:%M')


def _conectar():
    os.makedirs(os.path.dirname(ruta()), exist_ok=True)
    con = sqlite3.connect(ruta(), timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript(_ESQUEMA)
    return con


def registrar(tipo, accion, resultado, archivos=(), curso=None, detalle='', enlaces=(), reconstruido=False,
              fuente='', fecha=None):
    """Agrega un evento. Devuelve su id, o None si está apagado o no se pudo escribir (nunca lanza)."""
    if not habilitado():
        return None
    try:
        if tipo not in TIPOS or resultado not in RESULTADOS:
            raise ValueError(f'tipo/resultado no válido: {tipo}/{resultado}')
        curso = curso or {}
        with _lock, _conectar() as con:
            cur = con.execute(
                'INSERT INTO eventos (fecha, tipo, archivos, curso_id, curso_nombre, accion, resultado, detalle, enlaces,'
                ' reconstruido, fuente) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                # fecha '' = desconocida (carga previa al historial); None = ahora
                (ahora() if fecha is None else fecha, tipo, json.dumps(list(archivos), ensure_ascii=False),
                 str(curso.get('id') or ''),
                 str(curso.get('nombre') or ''), accion, resultado, str(detalle or '')[:2000],
                 json.dumps([dict(texto=e['texto'], url=e['url']) for e in enlaces], ensure_ascii=False),
                 int(bool(reconstruido)), fuente))
            return cur.lastrowid
    except Exception as e:  # noqa: BLE001  el historial nunca debe romper el flujo
        _log.warning('No se pudo registrar en el historial: %s', type(e).__name__)
        return None


def _fila(r):
    corr = None
    if r['corr_resultado']:
        corr = dict(resultado=r['corr_resultado'], nota=r['corr_nota'] or '', fecha=r['corr_fecha'] or '')
    return dict(id=r['id'], fecha=r['fecha'], tipo=r['tipo'], archivos=json.loads(r['archivos']),
                curso_id=r['curso_id'], curso_nombre=r['curso_nombre'], accion=r['accion'], resultado=r['resultado'],
                detalle=r['detalle'], enlaces=json.loads(r['enlaces']), reconstruido=bool(r['reconstruido']),
                fuente=r['fuente'], correccion=corr)


def listar(tipo=None, curso=None, texto=None, orden='desc'):
    sql, args = 'SELECT * FROM eventos WHERE 1=1', []
    if tipo:
        sql += ' AND tipo = ?'; args.append(tipo)
    if curso:
        sql += ' AND curso_id = ?'; args.append(str(curso))
    if texto:
        sql += ' AND lower(archivos || " " || curso_nombre || " " || accion || " " || detalle) LIKE ?'
        args.append(f'%{texto.lower()}%')
    sql += f' ORDER BY fecha {"ASC" if orden == "asc" else "DESC"}, id {"ASC" if orden == "asc" else "DESC"}'
    with _lock, _conectar() as con:
        return [_fila(r) for r in con.execute(sql, args)]


def corregir(id_, resultado, nota):
    if resultado not in RESULTADOS:
        raise ValueError('Resultado no válido.')
    with _lock, _conectar() as con:
        cur = con.execute('UPDATE eventos SET corr_resultado=?, corr_nota=?, corr_fecha=? WHERE id=?',
                          (resultado, (nota or '').strip()[:500], ahora(), int(id_)))
        if not cur.rowcount:
            raise KeyError(id_)
        return _fila(con.execute('SELECT * FROM eventos WHERE id=?', (int(id_),)).fetchone())


def quitar_correccion(id_):
    with _lock, _conectar() as con:
        cur = con.execute('UPDATE eventos SET corr_resultado=NULL, corr_nota=NULL, corr_fecha=NULL WHERE id=?', (int(id_),))
        if not cur.rowcount:
            raise KeyError(id_)
        return _fila(con.execute('SELECT * FROM eventos WHERE id=?', (int(id_),)).fetchone())


def _efectivo(e):
    return (e['correccion'] or {}).get('resultado') or e['resultado']


def resumen(filas):
    return dict(eventos=len(filas), cursos=len({e['curso_id'] for e in filas if e['curso_id']}),
                publicaciones=sum(1 for e in filas if _efectivo(e) in ('ok', 'avisos') and
                                  any(p in e['accion'] for p in ('Publica', 'PAE creada', 'Momento 1 aprobado'))),
                errores=sum(1 for e in filas if _efectivo(e) == 'error'))


# ---------------- siembra: lo que ya se cargó antes de que existiera el historial ----------------
_PE = dict(id='36283', nombre='PROGRAMACION ESTRUCTURADA (curso 36283)')
SIEMBRA = [
    dict(fecha='2026-11-06', tipo='silabos', archivos=['B26_Software_Programacion Estructurada.pdf'], curso=_PE,
         accion='Momento 1 aprobado (con el prompt maestro, antes del sistema)', resultado='ok', fuente='progress.md'),
    dict(fecha='2026-11-06', tipo='silabos', archivos=['silabo_pf20261106_165315med-paral_02.pdf'], 
         curso=dict(id='36732', nombre='B26-MED-1-COMPUTACION Y SOCIEDAD PARALELO 02'),
         accion='Publicado Momentos 1–4', resultado='ok', detalle='4/4 páginas publicadas y verificadas', fuente='progress.md'),
    dict(fecha='2026-11-11', tipo='guias', archivos=['Guías N° 1–4 de Programación Estructurada'], curso=_PE,
         accion='Publicar PAE1–PAE4', resultado='error', detalle='Bloqueado: cambios sin vista previa', fuente='progress.md'),
    dict(fecha='2026-11-12T17:59', tipo='guias', archivos=[], curso=None, accion='PAE creadas', resultado='ok',
         detalle='Nombre no registrado; probablemente G1–G6 reporte_guias_laboratorio… (carpeta Descargas, 12/11 17:27)',
         fuente='registro de Docker + Descargas'),
    dict(fecha='2026-11-12T18:01', tipo='silabos', archivos=[], curso=None, accion='Publicado', resultado='ok',
         detalle='Nombre y curso no registrados', fuente='registro de Docker'),
    dict(fecha='2026-11-12T18:02', tipo='silabos', archivos=[], curso=None, accion='Publicado', resultado='ok',
         detalle='Nombre y curso no registrados', fuente='registro de Docker'),
    dict(fecha='2026-11-12T18:04', tipo='silabos', archivos=[], curso=None, accion='Publicar', resultado='error',
         detalle='Rechazado: vista previa desactualizada. Nombre y curso no registrados', fuente='registro de Docker'),
    dict(fecha='2026-11-12T18:05', tipo='silabos', archivos=[], curso=None, accion='Publicado', resultado='ok',
         detalle='Nombre y curso no registrados', fuente='registro de Docker'),
]


def sembrar():
    """Inserta una sola vez las filas reconstruidas. Devuelve cuántas insertó."""
    if not habilitado():
        return 0
    with _lock, _conectar() as con:
        if con.execute("SELECT 1 FROM meta WHERE clave='sembrado'").fetchone():
            return 0
        con.execute("INSERT INTO meta VALUES ('sembrado', ?)", (ahora(),))
    n = 0
    for s in SIEMBRA:
        if registrar(reconstruido=True, **s):
            n += 1
    return n
