# -*- coding: utf-8 -*-
"""Flujo "Guías prácticas": sílabo + guías → tareas PAE (grupo Actividades) + rúbricas con el mismo nombre.

analizar → (adaptar con IA) → generar (vista previa + controles) → publicar (con confirmación) → deshacer.
Nada se escribe en Canvas sin `confirmado=True`; deshacer solo borra lo que creó esta sesión.
"""
import re
from datetime import date

from . import canvas, guia, pae, silabo
from .servicio import ErrorEntrada, _sin_tildes

SUBMISSION = ['online_upload', 'online_url']


def _modulo_de(modulos, n):
    return next((m['id'] for m in modulos if canvas.es_titulo_momento(m.get('name', ''), n)), None)


def analizar(pdf_silabo, pdfs_guias, url, token, transport=None):
    curso = canvas.curso_desde_url(url)
    if not curso:
        raise ErrorEntrada('La URL no es de un curso de Canvas. Debe verse así: '
                           'https://indoamerica.instructure.com/courses/12345')
    try:
        sil = silabo.leer(pdf_silabo)
    except silabo.FormatoNoReconocido as e:
        raise ErrorEntrada(f'Sílabo: {e}') from e
    guias = []
    for nombre, f in pdfs_guias:
        try:
            for g in guia.leer(f):
                g['archivo'] = nombre
                guias.append(g)
        except guia.FormatoNoReconocido as e:
            raise ErrorEntrada(f'{nombre}: {e}') from e
    if not guias:
        raise ErrorEntrada('Carga al menos una guía práctica.')
    try:
        cv = canvas.Canvas(curso, token, transport)
        info = cv.info_curso()
        grupos = cv.grupos_tareas()
        tareas = cv.tareas('PAE')
        modulos = cv.modulos()
    except canvas.ErrorCanvas as e:
        raise ErrorEntrada(str(e)) from e
    curso['nombre'] = info.get('name', '')

    adv = []
    grupo = next((g for g in grupos if _sin_tildes(g.get('name', '')).strip() == 'actividades'), None)
    if not grupo:
        adv.append(dict(tipo='Canvas', grave=True, texto='No encontré el grupo "Actividades" en Tareas. '
                                                          'Elige en qué grupo crear las PAE.'))
    existentes = {}
    for t in tareas:
        k = pae.numero_pae(t.get('name'))
        if k:
            existentes.setdefault(k, dict(id=t['id'], nombre=t['name']))

    proyecto = _sin_tildes(sil['ficha'].get('proyecto', ''))
    nombre_c = _sin_tildes(curso['nombre'])
    if proyecto and nombre_c and not any(w in nombre_c for w in proyecto.split() if len(w) > 3):
        adv.append(dict(tipo='Curso', grave=True,
                        texto=f'El curso de Canvas se llama "{curso["nombre"]}" y el sílabo es de '
                              f'"{sil["ficha"].get("proyecto")}". Verifica que sea el curso correcto.'))

    items = []
    for g in sorted(guias, key=lambda x: (x['n'] or 999)):
        if g['faltan']:
            adv.append(dict(tipo='Guía', grave=True, texto=f'{g["archivo"]}: no se pudo leer {", ".join(g["faltan"])}.'))
        if g['proyecto'] and proyecto and _sin_tildes(g['proyecto']) != proyecto:
            adv.append(dict(tipo='Guía', grave=True,
                            texto=f'Guía N° {g["n"]} es de "{g["proyecto"]}" y el sílabo de "{sil["ficha"].get("proyecto")}".'))
        mom, info_m, aviso = pae.emparejar(g, sil['momentos'])
        if aviso:
            adv.append(dict(tipo='Guía', grave=mom is None, texto=aviso))
        if not g['ra']:
            adv.append(dict(tipo='Guía', grave=False,
                            texto=f'Guía N° {g["n"]}: "Resultados de Aprendizaje" viene vacío en el PDF; '
                                  'se toma del sílabo.'))
        items.append(dict(guia=g, momento=mom['n'] if mom else None, empareja=info_m,
                          nombre=pae.nombre_pae(g['n'], g['titulo']), puntos=pae.PUNTOS_POR_DEFECTO,
                          inicio=g['inicio'], fin=g['fin'],
                          rubrica=[dict(f, ia=[False] * 5) for f in pae.rubrica_base(mom)] if mom else [],
                          rubrica_origen='sílabo', modulo=True, incluir=True, creado=None))

    sesion = dict(tipo='guias', silabo=sil, curso=curso, canvas=cv, grupos=grupos,
                  grupo_id=grupo['id'] if grupo else None, existentes=existentes,
                  modulos=[dict(id=m['id'], name=m.get('name', '')) for m in modulos],
                  items=items, advertencias=adv, version=0, generada=-1)
    for it in items:
        k = pae.numero_pae(it['nombre'])
        if k in existentes:
            it['incluir'] = False
    return sesion


def ra_texto(sil, mom, g):
    if g['ra']:
        return g['ra']
    if not mom:
        return ''
    return ' '.join(f'{c}: {sil["ra"].get(c, "")}'.strip() for c in mom['ra'])


def _momento(sesion, n):
    return next((m for m in sesion['silabo']['momentos'] if m['n'] == n), None)


def adaptar(sesion, i):
    it = sesion['items'][i]
    mom = _momento(sesion, it['momento'])
    if not mom:
        raise ErrorEntrada('Primero elige el momento de esta guía.')
    base = pae.rubrica_base(mom)
    rub, cambiadas, err = pae.adaptar_ia(it['guia'], mom, base)
    if err:
        return dict(ok=False, mensaje='La IA no respondió; se mantiene la rúbrica del sílabo.', rubrica=it['rubrica'])
    it['rubrica'], it['rubrica_origen'] = rub, 'ia'
    sesion['version'] += 1
    return dict(ok=True, cambiadas=cambiadas, rubrica=rub,
                mensaje=f'Qwen ajustó {cambiadas} de {5 * len(rub)} descriptores. Revisa antes de publicar.')


def _fecha(t):
    if isinstance(t, date) or t is None:
        return t
    m = re.match(r'^(\d{4})-(\d\d)-(\d\d)$', t or '')
    return date(*map(int, m.groups())) if m else None


def generar(sesion, edicion):
    """Aplica lo que editó el docente y calcula vista previa + controles de cada guía."""
    if edicion.get('grupo_id') is not None:
        ids = {g['id'] for g in sesion['grupos']}
        if int(edicion['grupo_id']) not in ids:
            raise ErrorEntrada('Ese grupo de tareas no existe en el curso.')
        sesion['grupo_id'] = int(edicion['grupo_id'])
    for e in edicion.get('items', []):
        it = sesion['items'][int(e['i'])]
        if 'momento' in e and e['momento'] and int(e['momento']) != it['momento']:
            mom = _momento(sesion, int(e['momento']))
            if mom:
                it['momento'] = mom['n']
                it['rubrica'] = [dict(f, ia=[False] * 5) for f in pae.rubrica_base(mom)]
                it['rubrica_origen'] = 'sílabo'
        for k in ('nombre',):
            if k in e:
                it[k] = re.sub(r'\s+', ' ', e[k] or '').strip()[:250]
        if 'puntos' in e:
            try:
                it['puntos'] = round(float(e['puntos']), 2)
            except (TypeError, ValueError):
                it['puntos'] = 0
        for k in ('inicio', 'fin'):
            if k in e:
                it[k] = _fecha(e[k])
        for k in ('incluir', 'modulo'):
            if k in e:
                it[k] = bool(e[k])
        if e.get('rubrica') is not None:
            nueva = []
            for f, vieja in zip(e['rubrica'], it['rubrica'] + [None] * len(e['rubrica'])):
                niv = [re.sub(r'\s+', ' ', t or '').strip() for t in (f.get('niveles') or [])][:5]
                ia = (vieja or {}).get('ia', [False] * 5)
                ia = [a and vieja['niveles'][k] == niv[k] for k, a in enumerate(ia[:len(niv)])] + [False] * (5 - len(niv))
                nueva.append(dict(indicador=re.sub(r'\s+', ' ', f.get('indicador') or '').strip(), niveles=niv, ia=ia))
            it['rubrica'] = nueva
        if e.get('restaurar_rubrica'):
            mom = _momento(sesion, it['momento'])
            if mom:
                it['rubrica'] = [dict(f, ia=[False] * 5) for f in pae.rubrica_base(mom)]
                it['rubrica_origen'] = 'sílabo'
    sesion['version'] += 1
    sesion['generada'] = sesion['version']
    return vista(sesion)


def controles(sesion, i):
    it = sesion['items'][i]
    c = []

    # `bloquea`: sin esto Canvas no puede crear la tarea (o la duplicaría). Los demás fallos graves
    # se avisan, pero el docente puede crearla igual y corregirla en Canvas.
    def chk(ok, texto, grave=True, bloquea=False):
        c.append(dict(ok=bool(ok), texto=texto, grave=grave, bloquea=bloquea))
    n = pae.numero_pae(it['nombre'])
    chk(re.match(r'^PAE\d+-\S', it['nombre'] or ''), 'Nombre con formato PAE#-Nombre de la guía')
    otros = [pae.numero_pae(o['nombre']) for j, o in enumerate(sesion['items']) if j != i and o['incluir']]
    chk(n not in otros, 'Número de PAE único entre las guías cargadas')
    ex = sesion['existentes'].get(n)
    chk(not ex or it['creado'], f'No existe ya en el curso{" (existe: " + ex["nombre"] + ")" if ex and not it["creado"] else ""}', bloquea=True)
    chk(it['momento'], 'Guía emparejada con un momento del sílabo', bloquea=True)
    chk(sesion['grupo_id'], 'Grupo de tareas elegido', bloquea=True)
    chk(it['inicio'] and it['fin'] and it['inicio'] <= it['fin'], 'Fechas válidas (inicio ≤ fin)', bloquea=True)
    errores = pae.revisar_rubrica(it['rubrica'], it['puntos'])
    chk(not errores, 'Rúbrica completa (5 niveles por indicador) y puntos que cuadran' +
        ('' if not errores else ': ' + ' '.join(errores[:3])))
    mom = _momento(sesion, it['momento'])
    chk(ra_texto(sesion['silabo'], mom, it['guia']), 'Resultado de aprendizaje', grave=False)
    chk(not it['modulo'] or _modulo_de(sesion['modulos'], it['momento']),
        f'Módulo "Momento {it["momento"]}" encontrado en el curso', grave=False)
    return c


def vista(sesion):
    out = []
    for i, it in enumerate(sesion['items']):
        mom = _momento(sesion, it['momento'])
        por, lv = pae.puntos(it['puntos'], len(it['rubrica']))
        ctrl = controles(sesion, i)
        out.append(dict(
            i=i, nombre=it['nombre'], puntos=it['puntos'], por_indicador=por, niveles_pts=lv,
            descripcion=pae.descripcion_html(it['guia'], mom, ra_texto(sesion['silabo'], mom, it['guia']), it['nombre'])
            if mom else '',
            controles=ctrl, listo=all(x['ok'] for x in ctrl if x['grave']),
            publicable=all(x['ok'] for x in ctrl if x['bloquea']), incluir=it['incluir'],
            creado=it['creado']))
    return dict(items=out, listo=any(x['listo'] and x['incluir'] for x in out),
                publicable=any(x['publicable'] and x['incluir'] for x in out))


def _criterios(it):
    por, lv = pae.puntos(it['puntos'], len(it['rubrica']))
    return [dict(descripcion=f['indicador'], puntos=por,
                 niveles=[dict(descripcion=nom, detalle=t, puntos=p)
                          for nom, t, p in reversed(list(zip(pae.NIVELES, f['niveles'], lv)))])
            for f in it['rubrica']]


def publicar(sesion, indices, confirmado):
    if not confirmado:
        raise ErrorEntrada('Falta tu confirmación para crear las tareas en Canvas.')
    if sesion['generada'] != sesion['version']:
        raise ErrorEntrada('Hay cambios sin vista previa: genera la vista previa de nuevo antes de publicar.')
    cv = sesion.get('canvas')
    if not cv:
        raise ErrorEntrada('La sesión ya terminó.')
    res = {}
    for i in indices:
        it = sesion['items'][int(i)]
        if it['creado']:
            res[i] = dict(ok=True, mensaje='Ya se creó en esta sesión.', **_enlaces(sesion, it)); continue
        if not it['incluir']:
            res[i] = dict(ok=False, mensaje='No marcada para publicar.'); continue
        ctrl = controles(sesion, int(i))
        bloqueos = [c['texto'] for c in ctrl if c['bloquea'] and not c['ok']]
        if bloqueos:
            res[i] = dict(ok=False, mensaje='No se creó: ' + '; '.join(bloqueos)); continue
        pendientes = [c['texto'] for c in ctrl if c['grave'] and not c['ok']]
        mom = _momento(sesion, it['momento'])
        desde, hasta = pae.fechas_canvas(it['inicio'], it['fin'])
        datos = dict(name=it['nombre'], points_possible=it['puntos'], grading_type='points',
                     submission_types=SUBMISSION, assignment_group_id=sesion['grupo_id'],
                     unlock_at=desde, due_at=hasta, published=False,
                     description=pae.descripcion_html(it['guia'], mom, ra_texto(sesion['silabo'], mom, it['guia']),
                                                      it['nombre']))
        creado = dict(tarea=None, rubrica=None, modulo=None)
        try:
            t = cv.crear_tarea(datos, aprobado=True)
            creado['tarea'] = t['id']
            it['creado'] = creado
            r = cv.crear_rubrica(it['nombre'], _criterios(it), t['id'], aprobado=True)
            creado['rubrica'] = (r.get('rubric') or r).get('id')
            mid = _modulo_de(sesion['modulos'], it['momento']) if it['modulo'] else None
            if mid:
                try:
                    creado['modulo'] = cv.agregar_a_modulo(mid, t['id'], aprobado=True).get('id')
                except canvas.ErrorCanvas:
                    creado['modulo'] = None
            res[i] = dict(ok=True, **verificar(sesion, it), **_enlaces(sesion, it))
            if pendientes:
                res[i]['pendientes'] = pendientes
                res[i]['verificado'] = False
                res[i]['mensaje'] = 'Creada con fallos por corregir en Canvas.'

        except canvas.ErrorCanvas as e:
            parte = 'la tarea' if not creado['tarea'] else 'la rúbrica (la tarea sí se creó; puedes deshacer)'
            res[i] = dict(ok=False, mensaje=f'No se pudo crear {parte}: {e}', **_enlaces(sesion, it))
    return res


def verificar(sesion, it):
    """Relee de Canvas lo creado: grupo de la tarea, rúbrica asociada y rúbrica en el apartado Rúbricas."""
    cv, c = sesion['canvas'], it['creado']
    chequeos = []
    try:
        t = cv.tarea(c['tarea'])
        chequeos.append(dict(ok=t.get('name') == it['nombre'], texto='Tarea creada con el nombre PAE'))
        chequeos.append(dict(ok=t.get('assignment_group_id') == sesion['grupo_id'],
                             texto=f'En el grupo "{_grupo(sesion)}"'))
        chequeos.append(dict(ok=bool(t.get('rubric')) or bool(t.get('rubric_settings')), texto='Rúbrica asociada a la tarea'))
        chequeos.append(dict(ok=t.get('published') is False, texto='Sin publicar (la publicas tú en Canvas)'))
    except canvas.ErrorCanvas as e:
        chequeos.append(dict(ok=False, texto=f'No se pudo releer la tarea ({e})'))
    if c.get('rubrica'):
        try:
            lista = cv.rubricas()
            chequeos.append(dict(ok=any(r.get('id') == c['rubrica'] and r.get('title') == it['nombre'] for r in lista),
                                 texto='Rúbrica visible en el apartado Rúbricas con el mismo nombre'))
        except canvas.ErrorCanvas as e:
            chequeos.append(dict(ok=False, texto=f'No se pudo leer el apartado Rúbricas ({e})'))
    if it['modulo']:
        chequeos.append(dict(ok=bool(c.get('modulo')), texto=f'Agregada al módulo Momento {it["momento"]}'))
    ok = all(x['ok'] for x in chequeos)
    return dict(verificado=ok, chequeos=chequeos,
                mensaje='Creada y verificada.' if ok else 'Creada, pero revisa los puntos marcados.')


def _grupo(sesion):
    return next((g['name'] for g in sesion['grupos'] if g['id'] == sesion['grupo_id']), '')


def _enlaces(sesion, it):
    c = it.get('creado') or {}
    base = sesion['curso']['url']
    return dict(url_tarea=f'{base}/assignments/{c["tarea"]}' if c.get('tarea') else '',
                url_rubrica=f'{base}/rubrics/{c["rubrica"]}' if c.get('rubrica') else '')


def deshacer(sesion, i):
    it = sesion['items'][int(i)]
    c = it.get('creado')
    if not c:
        raise ErrorEntrada('Esta guía no se creó en esta sesión.')
    cv = sesion['canvas']
    try:
        if c.get('rubrica'):
            cv.borrar_rubrica(c['rubrica'], aprobado=True)
        if c.get('tarea'):
            cv.borrar_tarea(c['tarea'], aprobado=True)
    except canvas.ErrorCanvas as e:
        raise ErrorEntrada(f'No se pudo deshacer: {e}') from e
    it['creado'] = None
    return dict(ok=True, mensaje='Se eliminaron la tarea y la rúbrica creadas en esta sesión.')


def resumen(sesion):
    sil = sesion['silabo']
    items = []
    for i, it in enumerate(sesion['items']):
        g = it['guia']
        mom = _momento(sesion, it['momento'])
        items.append(dict(
            i=i, n=g['n'], archivo=g['archivo'], titulo=g['titulo'], horas=g['horas'], pasos=len(g['procedimiento']),
            procedimiento=g['procedimiento'], momento=it['momento'], empareja=it['empareja'],
            inicio=it['inicio'].isoformat() if it['inicio'] else '', fin=it['fin'].isoformat() if it['fin'] else '',
            nombre=it['nombre'], puntos=it['puntos'], incluir=it['incluir'], modulo=it['modulo'],
            existe=sesion['existentes'].get(pae.numero_pae(it['nombre'])),
            rubrica=it['rubrica'], rubrica_origen=it['rubrica_origen'],
            rubrica_silabo=pae.rubrica_base(mom) if mom else [],
            ra=ra_texto(sil, mom, g), ra_en_guia=bool(g['ra'])))
    nuevas = [pae.numero_pae(it['nombre']) for it in sesion['items']]
    todas = set(sesion['existentes']) | {n for n in nuevas if n}
    faltan = [k for k in range(1, max(todas) + 1) if k not in todas] if todas else []
    return dict(
        ficha=dict(proyecto=sil['ficha'].get('proyecto', ''), codigo=sil['ficha'].get('codigo', ''),
                   periodo=sil['ficha'].get('periodo', '')),
        curso={k: sesion['curso'][k] for k in ('id', 'host', 'url', 'nombre')},
        grupos=[dict(id=g['id'], nombre=g.get('name', '')) for g in sesion['grupos']], grupo_id=sesion['grupo_id'],
        momentos=[dict(n=m['n'], titulo=m['titulo'], inicio=m.get('inicio', ''), fin=m.get('fin', ''),
                       indicadores=len(m['rubrica'])) for m in sil['momentos']],
        existentes=[dict(n=k, **v) for k, v in sorted(sesion['existentes'].items())],
        secuencia=dict(existentes=sorted(sesion['existentes']), nuevas=nuevas, faltan=faltan),
        items=items, advertencias=sesion['advertencias'], niveles=pae.NIVELES)
