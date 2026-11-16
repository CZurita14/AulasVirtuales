# -*- coding: utf-8 -*-
"""Guía práctica + sílabo → tarea PAE con su rúbrica.

- La guía se empareja con su momento del sílabo (título del momento y fechas).
- La rúbrica base es la del momento (indicadores × 5 niveles). Se puede adaptar al contexto de la guía
  con Qwen; lo que no cumpla las reglas se queda con el texto del sílabo.
- Puntos: el total se reparte por igual entre indicadores y cada nivel vale 1/5 más que el anterior.
"""
import html
import re
import unicodedata
from datetime import date

from .silabo import NIVELES

ZONA = '-05:00'                 # Ecuador continental
PUNTOS_POR_DEFECTO = 10


def _base(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def _fecha_silabo(t):
    m = re.match(r'(\d\d)/(\d\d)/(\d{4})', t or '')
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def emparejar(g, momentos):
    """→ (momento | None, dict(titulo=bool, fechas=bool), aviso | None)."""
    tg = _base(g['momento'])
    mejor, info = None, dict(titulo=False, fechas=False)
    por_titulo = [m for m in momentos if tg and _base(m['titulo']) and
                  (_base(m['titulo']).startswith(tg[:60]) or tg.startswith(_base(m['titulo'])[:60]))]

    def solape(m):
        a, b = _fecha_silabo(m.get('inicio')), _fecha_silabo(m.get('fin'))
        if not (a and b and g['inicio'] and g['fin']):
            return -1
        return (min(b, g['fin']) - max(a, g['inicio'])).days

    por_fecha = sorted((m for m in momentos if solape(m) >= 0), key=solape, reverse=True)
    if por_titulo:
        mejor = por_titulo[0]
    elif por_fecha:
        mejor = por_fecha[0]
    if mejor is None:
        return None, info, (f'Guía N° {g["n"]}: no encontré su momento en el sílabo (ni por título ni por fechas). '
                            'Elígelo a mano.')
    info['titulo'] = mejor in por_titulo
    info['fechas'] = bool(por_fecha) and por_fecha[0] is mejor
    aviso = None
    if por_titulo and por_fecha and por_fecha[0] is not mejor:
        aviso = (f'Guía N° {g["n"]}: el título apunta al Momento {mejor["n"]}, pero las fechas encajan mejor con el '
                 f'Momento {por_fecha[0]["n"]}. Revisa cuál corresponde.')
    elif not info['fechas'] and mejor:
        aviso = (f'Guía N° {g["n"]}: sus fechas ({g["inicio"]:%d/%m/%Y} – {g["fin"]:%d/%m/%Y}) no caen dentro del '
                 f'Momento {mejor["n"]} ({mejor.get("inicio")} – {mejor.get("fin")}).')
    return mejor, info, aviso


def nombre_pae(n, titulo):
    t = re.sub(r'\s+', ' ', titulo or '').strip().rstrip('.')
    return f'PAE{n}-{t}'[:250]


def numero_pae(nombre):
    m = re.match(r'^\s*PAE\s*0*(\d+)\b', nombre or '', re.I)
    return int(m.group(1)) if m else None


def rubrica_base(momento):
    """[{indicador, niveles:[5]}] tal cual el sílabo."""
    return [dict(indicador=ind, niveles=list(niv) + [''] * (5 - len(niv))) for ind, niv in momento['rubrica']]


def puntos(total, n_ind):
    """→ (por_indicador, [puntos por nivel Receptivo…Cocreativo])."""
    por = round(total / n_ind, 2) if n_ind else 0
    return por, [round(por * k / 5, 2) for k in range(1, 6)]


# ---------------- reglas de la rúbrica ----------------
def revisar_rubrica(rub, total):
    """Lista de problemas (vacía = cumple)."""
    errores = []
    if not rub:
        return ['La rúbrica no tiene indicadores.']
    for i, f in enumerate(rub, 1):
        if not (f.get('indicador') or '').strip():
            errores.append(f'Indicador {i}: falta el nombre.')
        niv = f.get('niveles') or []
        if len(niv) != 5:
            errores.append(f'Indicador {i}: debe tener 5 niveles.')
        for nom, t in zip(NIVELES, niv):
            if not (t or '').strip():
                errores.append(f'Indicador {i} · {nom}: celda vacía.')
    por, lv = puntos(total, len(rub))
    if total <= 0:
        errores.append('Los puntos de la tarea deben ser mayores que 0.')
    elif abs(por * len(rub) - total) > 0.001:
        errores.append(f'Los puntos no cuadran: {len(rub)} indicadores × {por} ≠ {total}. Usa un total divisible.')
    return errores


# ---------------- adaptación con Qwen (una llamada por indicador) ----------------
_SIS = ('Eres un experto en evaluación por competencias (enfoque socioformativo). Adaptas UN indicador de una '
        'rúbrica al contexto de una guía práctica. Recibes los 5 descriptores originales (Receptivo, Resolutivo, '
        'Reflexivo, Crítico, Cocreativo) y devuelves los 5 adaptados, cada uno en SU MISMO nivel: el nivel '
        'receptivo adaptado parte del receptivo original, el resolutivo del resolutivo, y así. Mantén el verbo '
        'inicial y la exigencia de cada nivel. Cada descriptor es UNA oración en tercera persona que empieza con '
        'un verbo en presente, de máximo 40 palabras, sin anteponer el nombre del nivel. ADAPTAR significa '
        'reemplazar las expresiones generales del original por los elementos CONCRETOS de la guía que tengan '
        'relación con este indicador (operaciones, estructuras, herramientas, productos, pasos). Ejemplo de otra '
        'asignatura: original "Elabora estados financieros básicos del caso." + guía "Registrar asientos de compra '
        'y venta en el libro diario; elaborar el balance de comprobación" → "Registra en el libro diario los '
        'asientos de compra y venta y elabora el balance de comprobación sin descuadres." Si la guía no dice nada '
        'relacionado con un descriptor, devuélvelo igual. No añadas "según la guía" ni inventes contenidos. '
        'Responde solo con el JSON pedido.')
_CLAVES = ['receptivo', 'resolutivo', 'reflexivo', 'critico', 'cocreativo']
_ESQUEMA = {'type': 'object', 'properties': {k: {'type': 'string'} for k in _CLAVES}, 'required': _CLAVES}

_PREFIJO_NIVEL = re.compile(r'^\s*(?:nivel\s+)?(?:receptivo|resolutivo|reflexivo|cr[ií]tico|cocreativo)\s*[:\-–—.]\s*', re.I)
_RELLENO = re.compile(r',?\s*(?:seg[uú]n|de acuerdo con|conforme a)\s+(?:el|la|lo)\s+(?:procedimiento|gu[ií]a)(?:\s+pr[aá]ctica)?', re.I)


def _limpiar(t):
    t = _PREFIJO_NIVEL.sub('', re.sub(r'\s+', ' ', t or '').strip())
    t = _RELLENO.sub('', t).strip()
    return t[:1].upper() + t[1:]


def _palabras(t):
    return set(re.findall(r'\w{4,}', _base(t)))


def _parecido(a, b):
    a, b = _palabras(a), _palabras(b)
    return len(a & b) / len(a | b) if a | b else 0


def _aporta(nuevo, viejo):
    """El descriptor nuevo trae algo de la guía y no es una copia del sílabo con retoques."""
    a, b = _palabras(nuevo), _palabras(viejo)
    return bool(a - b) and len(a ^ b) >= 3


def _en_su_nivel(nuevo, k, originales):
    """El descriptor adaptado se parece más a su original que a los de otros niveles (evita niveles corridos)."""
    p = [_parecido(nuevo, o) for o in originales]
    return p[k] > 0 and all(p[k] >= x for j, x in enumerate(p) if j != k)


def _descriptor_ok(t):
    t = re.sub(r'\s+', ' ', t or '').strip()
    return bool(t) and len(t.split()) <= 45 and t[0].isupper() and not re.search(r'[{}<>]', t)


def _adaptar_fila(qwen, contexto, fila):
    usuario = (f'{contexto}\n\nINDICADOR: {fila["indicador"]}\n' +
               '\n'.join(f'{n} (original): {t}' for n, t in zip(NIVELES, fila['niveles'])) +
               '\n\nAdapta estos 5 descriptores a la guía, cada uno en su mismo nivel.')
    datos, _ = qwen.json_con_esquema(_SIS, usuario, _ESQUEMA, nombre='indicador', max_tokens=900, temperatura=0.2)
    out = dict(indicador=fila['indicador'], niveles=list(fila['niveles']), ia=[False] * 5)
    for k, clave in enumerate(_CLAVES):
        t = _limpiar(datos.get(clave))
        if _descriptor_ok(t) and _aporta(t, fila['niveles'][k]) and _en_su_nivel(t, k, fila['niveles']):
            out['niveles'][k] = t
            out['ia'][k] = True
    return out


def adaptar_ia(g, momento, base):
    """→ (rúbrica, cambiadas, error). Cada celda que no cumpla las reglas se queda con el texto del sílabo."""
    from concurrent.futures import ThreadPoolExecutor

    from ia import qwen
    pasos = '\n'.join(f'{i}. {p}' for i, p in enumerate(g['procedimiento'], 1))
    contexto = (f'GUÍA PRÁCTICA N° {g["n"]}: {g["titulo"]}\nObjetivo: {g["objetivos"]}\n'
                f'Procedimiento:\n{pasos}\nResultado esperado: {g["resultado_esperado"]}\n'
                f'Evidencia del momento {momento["n"]}: {momento.get("rubrica_ev") or momento.get("evidencia", "")}')
    copia = [dict(f, niveles=list(f['niveles']), ia=[False] * 5) for f in base]
    try:
        with ThreadPoolExecutor(max_workers=4) as ex:
            out = list(ex.map(lambda f: _adaptar_fila(qwen, contexto, f), base))
    except Exception as e:  # noqa: BLE001  servidor caído, ventana, JSON inválido…
        return copia, 0, type(e).__name__
    return out, sum(sum(f['ia']) for f in out), None


# ---------------- descripción de la tarea (lo que ve el estudiante) ----------------
def _e(t):
    return html.escape(t or '', quote=False)


def descripcion_html(g, momento, ra_texto, nombre):
    rango = (f'{g["inicio"]:%d/%m/%Y} – {g["fin"]:%d/%m/%Y}' if g.get('inicio') and g.get('fin') else '')
    g = dict(g, horas=re.sub(r'\.0+$', '', g.get('horas') or ''))
    cab = (f'<div style="background: #3a1467; color: #ffffff; padding: 14px 18px; border-radius: 8px; '
           f'border-bottom: 4px solid #f37121;"><strong style="font-size: 1.15em;">{_e(nombre.split("-", 1)[0])} · '
           f'Guía práctica N° {g["n"]}</strong><br><span style="opacity: .9;">Momento {momento["n"]}'
           f'{" · " + _e(g["horas"]) + " horas" if g.get("horas") else ""}{" · " + rango if rango else ""}</span></div>')
    partes = [cab, f'<h3 style="color: #3a1467;">{_e(g["titulo"])}</h3>']

    def sec(titulo, cuerpo):
        if cuerpo:
            partes.append(f'<h4 style="color: #3a1467; border-left: 4px solid #f37121; padding-left: 8px;">{titulo}</h4>{cuerpo}')
    sec('Objetivo', f'<p>{_e(g["objetivos"])}</p>' if g.get('objetivos') else '')
    sec('Fundamento teórico', f'<p>{_e(g["fundamento"])}</p>' if g.get('fundamento') else '')
    if g.get('recursos'):
        sec('Recursos', '<ul>' + ''.join(f'<li><strong>{k.capitalize()}:</strong> {_e(v)}</li>'
                                         for k, v in g['recursos'].items()) + '</ul>')
    sec('Procedimiento', '<ol>' + ''.join(f'<li>{_e(p)}</li>' for p in g['procedimiento']) + '</ol>')
    sec('Resultado esperado', f'<p>{_e(g["resultado_esperado"])}</p>' if g.get('resultado_esperado') else '')
    sec('Conclusiones', f'<p>{_e(g["conclusiones"])}</p>' if g.get('conclusiones') else '')
    if ra_texto:
        partes.append(f'<p style="color: #6b6480; font-size: .9em;"><strong>Resultado de aprendizaje:</strong> {_e(ra_texto)}</p>')
    partes.append('<p style="color: #6b6480; font-size: .9em;">Esta actividad se califica con la rúbrica adjunta.</p>')
    return '\n'.join(partes)


def fechas_canvas(inicio, fin):
    """date → ISO con hora de Ecuador: disponible desde 00:00 del inicio, entrega 23:59 del fin."""
    return (f'{inicio:%Y-%m-%d}T00:00:00{ZONA}' if inicio else None,
            f'{fin:%Y-%m-%d}T23:59:00{ZONA}' if fin else None)
