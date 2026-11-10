# -*- coding: utf-8 -*-
"""Textos PROPUESTOS (el sílabo no los trae). Todo es editable por el docente en el paso 2.

- Propósito del momento: 1 oración que empieza con verbo en infinitivo, derivada del título y la evidencia.
- Bibliografía complementaria: 2 obras por momento según afinidad temática, cubriendo todas las obras.
"""
import re
import unicodedata

# sustantivo de acción (como aparece en los títulos) → infinitivo
VERBOS = {
    'análisis': 'analizar', 'aplicación': 'aplicar', 'comprensión': 'comprender', 'construcción': 'construir',
    'contextualización': 'contextualizar', 'conceptualización': 'conceptualizar', 'creación': 'crear',
    'depuración': 'depurar', 'desarrollo': 'desarrollar', 'diseño': 'diseñar', 'elaboración': 'elaborar',
    'evaluación': 'evaluar', 'exploración': 'explorar', 'identificación': 'identificar',
    'implementación': 'implementar', 'integración': 'integrar', 'investigación': 'investigar',
    'mejora': 'mejorar', 'modelado': 'modelar', 'modelación': 'modelar', 'planeación': 'planear',
    'planificación': 'planificar', 'presentación': 'presentar', 'programación': 'programar',
    'reconocimiento': 'reconocer', 'resolución': 'resolver', 'selección': 'seleccionar',
    'sensibilización': 'sensibilizar', 'socialización': 'socializar', 'solución': 'solucionar',
    'sustentación': 'sustentar', 'transferencia': 'transferir', 'validación': 'validar',
    'verificación': 'verificar', 'producción': 'producir', 'organización': 'organizar',
    'metacognición': 'reflexionar sobre el propio aprendizaje', 'reflexión': 'reflexionar',
}
ARTICULOS = [(r'^del ', 'el '), (r'^de la ', 'la '), (r'^de los ', 'los '), (r'^de las ', 'las '), (r'^de ', '')]


def _verbalizar(frase):
    """'validación y sustentación del prototipo' → 'Validar y sustentar el prototipo'."""
    palabras = frase.strip().split(' ')
    out, i, conv = [], 0, False
    while i < len(palabras):
        w = palabras[i]
        base = w.lower().rstrip(',')
        if base in VERBOS and (i == 0 or palabras[i - 1].lower() in ('y', 'e', ',') or palabras[i - 1].endswith(',')):
            out.append(VERBOS[base] + (',' if w.endswith(',') else '')); conv = True
        else:
            break
        i += 1
        if i < len(palabras) and palabras[i].lower() in ('y', 'e'):
            out.append(palabras[i]); i += 1
    if not conv:
        return None
    resto = ' '.join(palabras[i:])
    for pat, rep in ARTICULOS:
        if re.match(pat, resto):
            resto = re.sub(pat, rep, resto, count=1); break
    txt = ' '.join(out + ([resto] if resto else []))
    return txt[0].upper() + txt[1:]


def proposito(momento):
    titulo = momento.get('titulo', '')
    if titulo.isupper():          # títulos en MAYÚSCULAS: se pasan a minúsculas para redactar
        titulo = titulo.lower()
    partes = [p.strip() for p in titulo.split(':')]
    candidatos = partes[1:] + partes[:1] if len(partes) > 1 else partes
    accion = None
    for c in candidatos:
        for sub in [re.sub(r'\s*/\s*', ' y ', c)] + re.split(r'\s*/\s*', c):
            accion = _verbalizar(sub)
            if accion:
                break
        if accion:
            break
    if not accion:
        accion = 'Desarrollar ' + (partes[-1][:1].lower() + partes[-1][1:] if partes[-1] else 'las actividades del momento')
    ev = re.split(r'[,;:]', momento.get('evidencia', ''))[0].strip().rstrip('.')
    if ev.isupper():
        ev = ev.lower()
    ev = ev[:1].lower() + ev[1:]
    frase = f'{accion}, con la elaboración de: {ev}.' if ev else f'{accion}.'
    palabras = frase.split()
    if len(palabras) > 45:
        frase = ' '.join(palabras[:44]).rstrip(',;:') + '.'
    return frase


# ---------------- bibliografía complementaria ----------------
PISTAS = {  # términos temáticos (inglés o español) de la bibliografía → raíces del sílabo
    'debug': ['depura'], 'depura': ['depura'], 'test': ['prueba'], 'prueba': ['prueba'],
    'data structur': ['estruc', 'listas', 'arbole', 'grafos'], 'estructura de datos': ['estruc', 'listas', 'arbole', 'grafos'],
    'algorithm': ['algori', 'ordena', 'busque'], 'algoritm': ['algori', 'ordena', 'busque'],
    'chatgpt': ['intelig'], 'generative ai': ['intelig'], ' ai ': ['intelig'], 'artificial intelligence': ['intelig'],
    'large language': ['intelig'], 'llm': ['intelig'], 'inteligencia artificial': ['intelig'],
    'tree': ['arbole'], 'graph': ['grafos'], 'linked list': ['listas'], 'stack': ['pilas'], 'queue': ['colas'],
    'recurs': ['recurs'], 'sorting': ['ordena'], 'search': ['busque'], 'misconcept': ['concep', 'diagno'],
    'database': ['datos'], 'requirement': ['requer'], 'security': ['seguri'], 'cyber': ['seguri'],
}
STOP = set('para como sobre entre desde hasta donde cada este esta estos estas según mediante también '
           'caso estudio sesión aula material clase equipo datos'.split())


def _sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _raices(txt):
    r = {_sin_tildes(w[:6]) for w in re.findall(r'[a-záéíóúñü]{5,}', txt.lower()) if w not in STOP}
    if re.search(r'\bIA\b', txt):
        r.add('intelig')
    return r


def _raices_obra(texto):
    t = ' ' + _sin_tildes(texto.lower()) + ' '
    return {r for k, v in PISTAS.items() if _sin_tildes(k) in t for r in v}


def reparto_complementaria(sil, por_momento=None):
    obras = sil['bibliografia']['complementaria']
    # Por defecto conservar todas las referencias del sílabo en cada momento.
    if por_momento is None:
        return {m['n']: [o['clave'] for o in obras] for m in sil['momentos']}
    if not obras:
        return {m['n']: [] for m in sil['momentos']}
    perfil_obra = [_raices_obra(o['texto']) for o in obras]
    ns = [m['n'] for m in sil['momentos']]
    puntaje = {}
    for m in sil['momentos']:
        txt = ' '.join([m.get('titulo', ''), m.get('evidencia', ''), m.get('politica_ia', '')] +
                       [s['cont'] + ' ' + s['doc'] + ' ' + s['pe'] + ' ' + s['aut'] for s in m['sesiones']])
        rm = _raices(txt)
        for i, po in enumerate(perfil_obra):
            puntaje[(i, m['n'])] = len(po & rm)
    cupo = min(por_momento, len(obras))
    asign = {n: [] for n in ns}
    # 1) cada obra una vez, en su momento más afín con cupo (pares de mayor afinidad primero)
    pares = sorted(puntaje, key=lambda k: (-puntaje[k], k[1], k[0]))
    usadas = set()
    for i, n in pares:
        if i not in usadas and len(asign[n]) < cupo:
            asign[n].append(i); usadas.add(i)
    # 2) completar cupos con las obras más afines que aún no estén en ese momento
    for n in ns:
        for i in sorted(range(len(obras)), key=lambda i: (-puntaje[(i, n)], i)):
            if len(asign[n]) >= cupo:
                break
            if i not in asign[n]:
                asign[n].append(i)
    return {n: [obras[i]['clave'] for i in sorted(asign[n])] for n in ns}


_ESQ_PROP = {'type': 'object', 'properties': {'proposito': {'type': 'string'}}, 'required': ['proposito']}
_SIS_PROP = ('Eres diseñador instruccional universitario. Redactas el "Propósito del momento" de un proyecto formativo: '
             'UNA sola oración, que empiece con un verbo en infinitivo, de 20 a 40 palabras, en español formal, '
             'basada en el título, la evidencia y los contenidos del momento. No copies la evidencia textualmente.')


def _valido(texto, momento):
    t = re.sub(r'\s+', ' ', texto or '').strip()
    pal = t.split()
    if not t.endswith('.') or t[:-1].count('. ') or not pal or len(pal) > 45:
        return False
    if not re.match(r'^[a-záéíóúñ]+(ar|er|ir)$', pal[0].rstrip(',').lower()):
        return False
    ev = re.sub(r'\s+', ' ', momento.get('evidencia', '')).strip().rstrip('.').lower()
    return not (len(ev) > 30 and ev[:60] in t.lower())


def proposito_ia(momento):
    """Propósito redactado por el modelo local; None si no está disponible o no cumple el formato."""
    from ia import qwen
    contenidos = '; '.join(s['cont'] for s in momento.get('sesiones', []) if s.get('cont'))
    usuario = (f'Título del momento: {momento.get("titulo", "")}\n'
               f'Evidencia de desempeño: {momento.get("evidencia", "")}\n'
               f'Contenidos: {contenidos}\nRedacta el propósito del momento.')
    try:
        datos, _ = qwen.json_con_esquema(_SIS_PROP, usuario, _ESQ_PROP, nombre='proposito', max_tokens=200, temperatura=0.2)
    except Exception:
        return None
    t = re.sub(r'\s+', ' ', datos.get('proposito', '')).strip()
    return t if _valido(t, momento) else None


def proponer(sil, usar_ia=False):
    """Textos PROPUESTOS. Con `usar_ia` y el modelo disponible, el propósito lo redacta Qwen (validado);
    si no sirve o no responde, se usa la regla por momento."""
    propositos = {m['n']: proposito(m) for m in sil['momentos']}
    if usar_ia:
        from ia import qwen
        if qwen.disponible():
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=4) as ex:
                for m, p in zip(sil['momentos'], ex.map(proposito_ia, sil['momentos'])):
                    if p:
                        propositos[m['n']] = p
    return dict(propositos=propositos, complementaria=reparto_complementaria(sil))
