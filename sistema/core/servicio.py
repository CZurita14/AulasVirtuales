# -*- coding: utf-8 -*-
"""Orquesta el flujo: analizar (sílabo + curso con token) → editar propuestos → generar → publicar en Canvas."""
import re
import unicodedata

from bs4 import BeautifulSoup

from . import calidad, canvas, propuestas, render, silabo, validador


class ErrorEntrada(ValueError):
    """Error que se muestra tal cual al docente."""


def _norm_txt(h):
    return re.sub(r'\s+', ' ', BeautifulSoup(h or '', 'html.parser').get_text(' ')).strip()


def _sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn').lower()


def analizar(pdf, url, token, transport=None):
    curso = canvas.curso_desde_url(url)
    if not curso:
        raise ErrorEntrada('La URL no es de un curso de Canvas. Debe verse así: '
                           'https://indoamerica.instructure.com/courses/12345')
    try:
        sil = silabo.leer(pdf)
    except silabo.FormatoNoReconocido as e:
        raise ErrorEntrada(str(e)) from e
    try:
        cv = canvas.Canvas(curso, token, transport)
        info = cv.info_curso()
        inicio = cv.pagina_inicio() or {}
        numeros = [m['n'] for m in sil['momentos']]
        destinos, avisos = canvas.localizar_momentos(cv, numeros)
    except canvas.ErrorCanvas as e:
        raise ErrorEntrada(str(e)) from e

    curso.update(slug=inicio.get('url') or 'inicio', nombre=info.get('name', ''))
    curso['url_inicio'] = f'https://{curso["host"]}/courses/{curso["id"]}/pages/{curso["slug"]}'

    institucional = render.leer_plantilla_institucional()
    plantillas, origen = {}, {}
    for n in numeros:
        cuerpo = (destinos.get(n) or {}).get('cuerpo', '')
        if cuerpo and render.analizar_plantilla(cuerpo)['valida']:
            plantillas[n], origen[n] = cuerpo, 'la página actual del curso'
        else:
            plantillas[n], origen[n] = institucional, 'institucional'
            if n in destinos:
                avisos.append(f'Momento {n}: la página "{destinos[n]["titulo"]}" no tiene la estructura de la plantilla; '
                              'se usará la plantilla institucional.')

    adv = validador.validar(sil, curso, None)
    adv += [dict(tipo='Canvas', texto=t, grave=True) for t in avisos]
    proyecto = _sin_tildes(sil['ficha'].get('proyecto', ''))
    nombre = _sin_tildes(curso['nombre'])
    if proyecto and nombre and not any(w in nombre for w in proyecto.split() if len(w) > 3):
        adv.append(dict(tipo='Curso', grave=True,
                        texto=f'El curso de Canvas se llama "{curso["nombre"]}" y el sílabo es de '
                              f'"{sil["ficha"].get("proyecto")}". Verifica que sea el curso correcto antes de publicar.'))
    prop = propuestas.proponer(sil)
    return dict(silabo=sil, curso=curso, canvas=cv, destinos=destinos, plantillas=plantillas,
                plantilla_origen=origen, advertencias=adv, propositos=prop['propositos'],
                complementaria=prop['complementaria'], respaldos={}, publicacion={})


def generar(sesion, propositos=None, complementaria=None, urls=None):
    version = sesion.get('version_datos', 0)   # la segunda lectura con IA puede cambiar los datos mientras tanto
    sil = sesion['silabo']
    if urls is not None:          # enlaces que el docente agrega a obras sin URL (PROPUESTO)
        for lista in sil['bibliografia'].values():
            for o in lista:
                if not o['url']:
                    u = (urls.get(o['clave']) or '').strip()
                    o['url_doc'] = u if re.match(r'^https?://\S+\.\S+$', u) else ''
    if propositos:
        sesion['propositos'].update({int(k): v.strip() for k, v in propositos.items() if v and v.strip()})
    if complementaria:
        validas = {o['clave'] for o in sil['bibliografia']['complementaria']}
        for k, urls in complementaria.items():
            sesion['complementaria'][int(k)] = list(dict.fromkeys(u for u in urls if u in validas))
    paginas, control = {}, {}
    for m in sil['momentos']:
        n = m['n']
        tpl = sesion['plantillas'][n]
        try:
            h = render.render(sil, n, tpl, sesion['curso'], sesion['propositos'][n], sesion['complementaria'][n])
            control[n] = calidad.controlar(h, m, sil, sesion['curso'], tpl, sesion['complementaria'][n],
                                           sesion['propositos'][n])
        except Exception as e:
            h = ''
            control[n] = [dict(nombre='Generación del HTML', ok=False, bloquea=True, detalle=f'{type(e).__name__}: {e}')]
        paginas[n] = h
    sesion['paginas'], sesion['control'] = paginas, control
    sesion['version_generada'] = version
    # La lista de control informa: el docente decide publicar tras revisar los avisos.
    # Una página sin generar o una vista previa desactualizada siguen sin ser publicables.
    sesion['listo'] = (bool(paginas) and all(h.strip() for h in paginas.values())
                       and version == sesion.get('version_datos', 0))
    return sesion


def _verificar(n, esperado, publicado):
    """Compara lo que quedó en Canvas con lo enviado (Canvas puede reescribir algo de HTML)."""
    if f'Momento {n}:' not in _norm_txt(publicado):
        return False, 'la página no muestra "Momento N:"'
    if any(x in publicado for x in ('Copiar y pegar', '[Día, Mes')):
        return False, 'quedaron marcadores sin reemplazar'
    if _norm_txt(publicado) != _norm_txt(esperado):
        return False, 'Canvas guardó un contenido distinto al enviado (revisa la página)'
    filas = lambda h: len(BeautifulSoup(h, 'html.parser').find_all('table', recursive=False)[2]
                          .find('tbody').find_all('tr', recursive=False))
    try:
        if filas(publicado) != filas(esperado):
            return False, 'el número de sesiones publicado no coincide'
    except (IndexError, AttributeError):
        return False, 'Canvas alteró la estructura de tablas'
    return True, ''


def publicar(sesion, numeros, confirmado=False):
    if confirmado is not True:
        raise ErrorEntrada('Falta la confirmación del docente para publicar.')
    if sesion.get('version_generada', 0) != sesion.get('version_datos', 0):
        raise ErrorEntrada('La IA completó datos después de tu vista previa: genera la vista previa de nuevo antes de publicar.')
    if not sesion.get('listo'):
        raise ErrorEntrada('Falta generar una vista previa completa antes de publicar.')
    cv = sesion['canvas']
    res = {}
    for n in numeros:
        n = int(n)
        dest = sesion['destinos'].get(n)
        html = sesion['paginas'].get(n, '')
        if not dest:
            res[n] = dict(ok=False, mensaje='No se encontró la página de este momento en el curso.')
            continue
        # el contenido debe corresponder a la página destino
        if f'Momento {n}:' not in _norm_txt(html) or not canvas.es_titulo_momento(dest['titulo'], n) and \
                dest['fuente'] == 'búsqueda':
            res[n] = dict(ok=False, mensaje='El contenido no corresponde a la página destino: no se publicó.')
            continue
        try:
            actual = cv.pagina(dest['slug'])
            sesion['respaldos'].setdefault(n, actual.get('body') or '')
            cv.actualizar_cuerpo(dest['slug'], html, aprobado=True)
            despues = cv.pagina(dest['slug'])
            ok, motivo = _verificar(n, html, despues.get('body') or '')
            res[n] = dict(ok=ok, mensaje='Publicada y verificada.' if ok else f'Publicada, pero {motivo}.',
                          url=dest['url'], publicada=despues.get('published'))
        except canvas.ErrorCanvas as e:
            res[n] = dict(ok=False, mensaje=f'No se publicó: {e}', url=dest['url'])
    sesion['publicacion'].update(res)
    return res


def restaurar(sesion, n):
    n = int(n)
    if n not in sesion['respaldos']:
        raise ErrorEntrada('No hay respaldo de esa página en esta sesión.')
    dest = sesion['destinos'][n]
    try:
        sesion['canvas'].actualizar_cuerpo(dest['slug'], sesion['respaldos'][n], aprobado=True)
        ok = _norm_txt(sesion['canvas'].pagina(dest['slug']).get('body')) == _norm_txt(sesion['respaldos'][n])
    except canvas.ErrorCanvas as e:
        raise ErrorEntrada(f'No se pudo restaurar: {e}') from e
    sesion['publicacion'][n] = dict(ok=False, restaurada=True, url=dest['url'],
                                    mensaje='Restaurada a la versión anterior.' if ok else 'Restaurada (verifícala en Canvas).')
    return sesion['publicacion'][n]


def cerrar(sesion):
    """Olvida el token y cierra la conexión."""
    cv = sesion.pop('canvas', None)
    if cv:
        cv.cerrar()


def resumen(sesion):
    """Lo que necesita la interfaz en el paso 2 (sin token, sin PDF, sin datos de contacto)."""
    sil = sesion['silabo']
    fi = sil['ficha']
    return dict(
        ficha=dict(proyecto=fi.get('proyecto', ''), codigo=fi.get('codigo', ''), periodo=fi.get('periodo', ''),
                   inicio=fi.get('inicio', ''), fin=fi.get('fin', ''), nivel=fi.get('nivel', ''),
                   modalidad=fi.get('modalidad', ''), docente=fi.get('docente', ''), horas=fi.get('horas', '')),
        curso={k: sesion['curso'][k] for k in ('id', 'host', 'url', 'nombre', 'url_inicio')},
        destinos={n: dict(titulo=d['titulo'], url=d['url'], fuente=d['fuente'], publicada=d['publicada'],
                          plantilla=sesion['plantilla_origen'][n]) for n, d in sesion['destinos'].items()},
        momentos=[dict(n=m['n'], titulo=m['titulo'], inicio=m['inicio'], fin=m['fin'], ra=m['ra'],
                       sesiones=len(m['sesiones']), totales=m['totales'], indicadores=len(m['rubrica']),
                       plantilla=sesion['plantilla_origen'][m['n']],
                       proposito=render.analizar_plantilla(sesion['plantillas'][m['n']])['proposito'])
                  for m in sil['momentos']],
        advertencias=sesion['advertencias'], propositos=sesion['propositos'],
        complementaria=sesion['complementaria'],
        obras=[dict(clave=o['clave'], url=o['url'], texto=o['texto']) for o in sil['bibliografia']['complementaria']],
        sin_url=[dict(clave=o['clave'], tipo=t, texto=o['texto'], url_doc=o.get('url_doc', ''))
                 for t, lista in sil['bibliografia'].items() for o in lista if not o['url']],
        basicas=len(sil['bibliografia']['basica']),
    )
