# -*- coding: utf-8 -*-
"""Extracción del sílabo con Qwen: tareas pequeñas, cada una con su esquema JSON.

Produce el mismo diccionario que core.silabo.leer() para poder renderizar con el mismo motor y
comparar campo a campo contra la lectura por reglas.

Lecciones de las pruebas (progress.md): las sesiones van UNA POR TAREA con las celdas ya etiquetadas por
columna (documento.registros_sesiones); todo valor que sea solo un rótulo de la tabla se descarta
(limpiar_rotulos), y la bibliografía se parte si no cabe en la ventana.
"""
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from . import documento, qwen

S = {'type': 'string'}
HORA = {'type': 'string', 'description': 'número con un decimal, p. ej. "6.0"'}

ROTULOS_PIS = ['Proyecto interdisciplinario socioformativo',
               'Aporte del proyecto formativo al proyecto interdisciplinario socioformativo']
ROTULOS_SESIONES = ['Sesión - fecha', 'Actividades con el docente', 'Horas', 'Hora s',
                    'Actividades práctico- experimentales', 'Actividades práctico-experimentales',
                    'Actividades de trabajo autónomo', 'Contenidos']

REGLAS = """Eres un extractor de datos de sílabos universitarios. Recibes filas de tablas del PDF como "| celda | celda |" o registros "ETIQUETA: valor".
REGLAS:
- Copia el texto LITERAL, carácter por carácter: no resumas, no corrijas, no traduzcas, no agregues ni quites palabras.
- Las tablas se cortan entre páginas: si una fila empieza con celdas vacías o con texto que continúa la anterior,
  UNE ese texto a la celda correspondiente de la fila anterior con un espacio. Ignora los encabezados repetidos.
- Si un dato no existe o la celda está vacía, usa "" (cadena vacía). NUNCA pongas como valor el nombre de una columna o de un rótulo.
- Responde solo con el JSON pedido."""

ESQ_RA = {'type': 'object', 'properties': {'ra': {'type': 'array', 'items': {
    'type': 'object', 'properties': {'codigo': S, 'texto': S}, 'required': ['codigo', 'texto']}}}, 'required': ['ra']}
ESQ_PIS = {'type': 'object', 'properties': {'titulo': S, 'aporte': S}, 'required': ['titulo', 'aporte']}
_OBRA = {'type': 'object', 'properties': {'texto': S, 'url': S}, 'required': ['texto', 'url']}
ESQ_BIB = {'type': 'object', 'properties': {'obras': {'type': 'array', 'items': _OBRA}}, 'required': ['obras']}
ESQ_CAB = {'type': 'object', 'properties': {'titulo': S, 'inicio': S, 'fin': S,
                                            'ra': {'type': 'array', 'items': S}, 'evidencia': S},
           'required': ['titulo', 'inicio', 'fin', 'ra', 'evidencia']}
_CAMPOS_SES = ['n', 'desde', 'hasta', 'docente', 'horas_docente', 'otras_horas', 'otras_texto', 'practico',
               'horas_practico', 'autonomo', 'horas_autonomo', 'contenidos']
ESQ_SESION = {'type': 'object', 'properties': {
    'n': {'type': 'integer'}, 'desde': S, 'hasta': S, 'docente': S, 'horas_docente': HORA,
    'otras_horas': S, 'otras_texto': S, 'practico': S, 'horas_practico': HORA,
    'autonomo': S, 'horas_autonomo': HORA, 'contenidos': S}, 'required': _CAMPOS_SES}
ESQ_PIE = {'type': 'object', 'properties': {'total_docente': HORA, 'total_practico': HORA, 'total_autonomo': HORA,
                                            'recursos': S, 'politica_ia': S},
           'required': ['total_docente', 'total_practico', 'total_autonomo', 'recursos', 'politica_ia']}
ESQ_SES = {'type': 'object', 'properties': {   # respaldo: tabla completa si no hay registros etiquetados
    'sesiones': {'type': 'array', 'items': ESQ_SESION}, **ESQ_PIE['properties']},
    'required': ['sesiones'] + ESQ_PIE['required']}
ESQ_RUB = {'type': 'object', 'properties': {
    'evidencia': S,
    'indicadores': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'nombre': S, 'receptivo': S, 'resolutivo': S, 'reflexivo': S, 'critico': S, 'cocreativo': S},
        'required': ['nombre', 'receptivo', 'resolutivo', 'reflexivo', 'critico', 'cocreativo']}}},
    'required': ['evidencia', 'indicadores']}

INSTR = {
    'ra': 'Extrae cada resultado de aprendizaje (RA1, RA2, …) con su texto completo (columna "Resultado de aprendizaje", sin la evidencia).',
    'pis': ('Extrae el título del Proyecto interdisciplinario socioformativo (la celda DEBAJO del rótulo) y el aporte del proyecto '
            'formativo (la celda DEBAJO de su rótulo). Si esas celdas están vacías, devuelve "" en ambos.'),
    'bibliografia': ('Extrae cada obra listada. "texto" es la referencia COMPLETA tal como aparece, desde el primer autor hasta '
                     'justo antes de la URL: autores, año, título, revista o editorial, volumen, número, páginas y editorial. '
                     '"url" es la URL o DOI unida sin espacios (las URL pueden venir partidas en dos líneas). Si la obra no tiene '
                     'URL, url = "". Ejemplo: "Kosar, T., & Mernik, M. (2024). Título del artículo. Mathematics, 12(5), 629. MDPI. '
                     'https://doi.org/10.3390/math12050629" → texto = "Kosar, T., & Mernik, M. (2024). Título del artículo. '
                     'Mathematics, 12(5), 629. MDPI.", url = "https://doi.org/10.3390/math12050629".'),
    'cabecera': ('Extrae del momento: título (texto de la fila "Momento N", sin la palabra "Momento N"), fecha de inicio y fin '
                 '(dd/mm/aaaa), códigos de RA (p. ej. ["RA1","RA2"]) y la evidencia de desempeño (producto esperado).'),
    'sesion': ('Recibes UNA sesión con sus celdas ya etiquetadas. Devuelve: "n" (número de la sesión), "desde" y "hasta" (fechas '
               'dd/mm/aaaa del rótulo SESIÓN; si hay una sola fecha, "hasta" = ""), "docente" (= ACTIVIDADES CON EL DOCENTE), '
               '"horas_docente" (= HORAS DOCENTE), "otras_horas" (= OTRAS ACTIVIDADES (HORAS)), "otras_texto" (= OTRAS ACTIVIDADES), '
               '"practico" (= ACTIVIDADES PRÁCTICO-EXPERIMENTALES), "horas_practico" (= HORAS PRÁCTICO), "autonomo" (= ACTIVIDADES DE '
               'TRABAJO AUTÓNOMO), "horas_autonomo" (= HORAS AUTÓNOMO), "contenidos" (= CONTENIDOS, sin la viñeta "•"). '
               'Copia cada valor tal cual, completo; si una etiqueta está vacía, devuelve "".'),
    'pie': ('Recibes los datos ya etiquetados. Devuelve "total_docente" (= TOTAL DOCENTE), "total_practico" (= TOTAL PRÁCTICO), '
            '"total_autonomo" (= TOTAL AUTÓNOMO), "recursos" (= RECURSOS PARA EL APRENDIZAJE) y "politica_ia" (= POLÍTICA DE IA), '
            'copiados tal cual.'),
    'sesiones': ('Extrae cada sesión de la tabla. Columnas: Sesión-fecha | Actividades con el docente | Horas | '
                 'Actividades práctico-experimentales | Horas | Actividades de trabajo autónomo | Horas | Contenidos (guíate por el '
                 'encabezado: puede haber columnas vacías extra). Separa "Otras actividades con el docente (X h): …". '
                 'Incluye la fila Total, "Recursos para el aprendizaje" y la "Política de gobernanza crítica y ética de la IA".'),
    'rubrica': ('Extrae la rúbrica del momento: la evidencia de desempeño (columna "Evidencia de desempeño del momento", sin el RA) '
                'y cada indicador con sus 5 niveles en orden: Receptivo, Resolutivo, Reflexivo, Crítico, Cocreativo. '
                'Algunas filas de un indicador continúan en la página siguiente con la primera celda vacía: únelas.'),
}


def _norm(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')
    return re.sub(r'[\W_]+', '', s.lower())


def limpiar_rotulos(valor, rotulos):
    """'' si el valor es solo un rótulo de la tabla (Qwen lo copió en vez del dato)."""
    v = _norm(valor)
    return '' if v and any(v == _norm(r) for r in rotulos) else (valor or '')


_INICIO_OBRA = re.compile(r'^[A-ZÁÉÍÓÚÑÜ][^()\n]{0,200}?(?:\([^()\n]*\)\.\s*)?\(\d{4}[a-z]?\)\.')


def partes_bibliografia(texto, max_tokens=2500):
    """[(tipo, texto)] por sección (básica/complementaria) y, si una sección no cabe, en trozos de obras completas."""
    secciones = []
    for tipo, etq in (('basica', 'Bibliografía básica'), ('complementaria', 'Bibliografía complementaria')):
        i = texto.find(etq)
        if i < 0:
            continue
        fin = texto.find('Bibliografía complementaria', i + 1) if tipo == 'basica' else -1
        secciones.append((tipo, texto[i + len(etq):fin if fin > 0 else None].strip()))
    partes = []
    for tipo, sec in secciones:
        if qwen.tokens_aprox(sec) <= max_tokens:
            partes.append((tipo, sec)); continue
        obras, cur = [], ''
        for l in sec.split('\n'):
            if cur and _INICIO_OBRA.match(l):
                obras.append(cur); cur = l
            else:
                cur = (cur + '\n' + l) if cur else l
        if cur:
            obras.append(cur)
        trozo = ''
        for o in obras:
            if trozo and qwen.tokens_aprox(trozo + '\n' + o) > max_tokens:
                partes.append((tipo, trozo)); trozo = o
            else:
                trozo = (trozo + '\n' + o) if trozo else o
        if trozo:
            partes.append((tipo, trozo))
    return partes


def _tarea(nombre, texto, esquema, momento=None, clave=None):
    usuario = INSTR[nombre] + '\n\nDATOS DEL SÍLABO:\n' + texto
    datos, met = qwen.json_con_esquema(REGLAS, usuario, esquema, nombre=nombre)
    met.update(tarea=nombre, momento=momento)
    return (clave or (nombre, momento)), datos, met


def _sesion(s):
    t = {k: limpiar_rotulos(str(s.get(k, '')).strip(), ROTULOS_SESIONES) for k in _CAMPOS_SES if k != 'n'}
    return dict(n=int(s.get('n') or 0), desde=t['desde'], hasta=t['hasta'], doc=t['docente'], hd=t['horas_docente'],
                otras_h=t['otras_horas'] or None, otras=t['otras_texto'] or None, pe=t['practico'],
                hpe=t['horas_practico'], aut=t['autonomo'], ha=t['horas_autonomo'],
                cont=t['contenidos'].lstrip('• ').strip())


def extraer(alm, silabo_id, ficha=None, paralelo=6, pdf_path=None, al_avanzar=None):
    """Devuelve (sil, métricas). `ficha` (portada) viene de la lectura por reglas: no se publica.
    `al_avanzar(hechas, total)` se llama al terminar cada tarea (barra de avance)."""
    t0 = time.time()
    momentos = alm.momentos(silabo_id)
    txt = lambda bloque, m=None: '\n'.join(f['texto'] for f in alm.bloques(silabo_id, bloque, m))
    registros = documento.registros_sesiones(pdf_path) if pdf_path else {}
    pies = documento.pie_momentos(pdf_path) if pdf_path else {}
    tareas = [('ra', txt('ra'), ESQ_RA, None, None), ('pis', txt('pis'), ESQ_PIS, None, None)]
    for i, (tipo, sec) in enumerate(partes_bibliografia(txt('bibliografia'))):
        tareas.append(('bibliografia', sec, ESQ_BIB, None, ('bibliografia', tipo, i)))
    for m in momentos:
        tareas += [('cabecera', txt('cabecera', m), ESQ_CAB, m, None), ('rubrica', txt('rubrica', m), ESQ_RUB, m, None)]
        if registros.get(m):
            tareas.append(('pie', pies.get(m) or txt('sesiones', m), ESQ_PIE, m, None))
            tareas += [('sesion', r, ESQ_SESION, m, ('sesion', m, j)) for j, r in enumerate(registros[m])]
        else:
            tareas.append(('sesiones', txt('sesiones', m), ESQ_SES, m, None))
    resultados, metricas, errores = {}, [], []
    hechas = 0
    parar = threading.Event()   # en cuanto Qwen deja de responder, las tareas pendientes no lo llaman

    def _una(*t):
        if parar.is_set():
            raise qwen.QwenNoDisponible('cancelada: el servidor de IA dejó de responder')
        try:
            return _tarea(*t)
        except qwen.QwenNoDisponible:
            parar.set()
            raise

    with ThreadPoolExecutor(max_workers=paralelo) as ex:
        futs = [ex.submit(_una, *t) for t in tareas]
        for f, t in zip(futs, tareas):
            try:
                clave, datos, met = f.result()
                resultados[clave] = datos
                metricas.append(met)
            except qwen.QwenNoDisponible:
                for g in futs:      # el servidor no responde: no tiene sentido seguir intentando el resto
                    g.cancel()
                raise
            except Exception as e:
                errores.append(dict(tarea=t[0], momento=t[3], error=f'{type(e).__name__}: {e}'))
            hechas += 1
            if al_avanzar:
                al_avanzar(hechas, len(tareas))

    def g(*k):
        return resultados.get(k) or {}

    sil = dict(ficha=ficha or {}, paginas=0, presentacion={}, momentos=[], pis={}, ra={})
    sil['ra'] = {r['codigo'].strip(): r['texto'].strip() for r in g('ra', None).get('ra', [])}
    pis = g('pis', None)
    sil['pis'] = dict(titulo=limpiar_rotulos(pis.get('titulo', '').strip(), ROTULOS_PIS),
                      aporte=limpiar_rotulos(pis.get('aporte', '').strip(), ROTULOS_PIS))
    sil['bibliografia'] = {'basica': [], 'complementaria': []}
    for clave in sorted(k for k in resultados if k[0] == 'bibliografia'):
        sil['bibliografia'][clave[1]] += [dict(texto=o['texto'].strip(), url=''.join(o['url'].split()))
                                          for o in resultados[clave].get('obras', [])]
    for tipo, lista in sil['bibliografia'].items():
        for i, o in enumerate(lista, 1):
            o['clave'] = o['url'] or f'{tipo}-{i}'
    for m in momentos:
        cab, rub = g('cabecera', m), g('rubrica', m)
        if registros.get(m):
            pie = g('pie', m)
            sesiones = [_sesion(resultados[('sesion', m, j)]) for j in range(len(registros[m])) if ('sesion', m, j) in resultados]
        else:
            pie = g('sesiones', m)
            sesiones = [_sesion(s) for s in pie.get('sesiones', [])]
        sil['momentos'].append(dict(
            n=m, titulo=cab.get('titulo', '').strip(), inicio=cab.get('inicio', '').strip(), fin=cab.get('fin', '').strip(),
            ra=[c.strip() for c in cab.get('ra', [])], evidencia=cab.get('evidencia', '').strip(), sesiones=sesiones,
            totales=(pie.get('total_docente', ''), pie.get('total_practico', ''), pie.get('total_autonomo', '')),
            recursos=pie.get('recursos', ''), politica_ia=pie.get('politica_ia', ''),
            rubrica_ev=rub.get('evidencia', '').strip(), ra_textos={},
            rubrica=[[i['nombre'].strip(), [i[k].strip() for k in ('receptivo', 'resolutivo', 'reflexivo', 'critico', 'cocreativo')]]
                     for i in rub.get('indicadores', [])]))
    resumen = dict(segundos_total=round(time.time() - t0, 1), tareas=len(tareas), errores=errores,
                   tokens_entrada=sum(x['entrada'] for x in metricas), tokens_salida=sum(x['salida'] for x in metricas),
                   tarea_mas_lenta=max(metricas, key=lambda x: x['segundos'], default=None), metricas=metricas)
    return sil, resumen
