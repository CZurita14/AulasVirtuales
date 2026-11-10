# -*- coding: utf-8 -*-
"""Cliente del modelo local (vLLM, API compatible con OpenAI). Salida JSON validada por esquema.

- La ventana es de 8192 tokens ENTRADA + SALIDA: se cuenta la entrada con el tokenizador del propio
  servidor (/tokenize) y se pide como máximo lo que sobra.
- Un solo reintento: si el servidor dice que se excedió la ventana, se reduce la salida; si no responde
  a tiempo, se lanza QwenNoDisponible y el sistema sigue con la lectura por reglas.
"""
import json
import math
import os
import re
import threading
import time
import urllib.request

import openai
from openai import OpenAI

MARGEN = 64          # plantilla de chat y separadores
_cache_disp = {}     # url → (instante, disponible)
_clientes = {}
_semaforos = {}      # límite → BoundedSemaphore compartido por todo el proceso (todos los docentes)
_lock_sem = threading.Lock()


def _semaforo():
    """Cola local: como máximo QWEN_MAX_SIMULTANEAS peticiones del sistema a la vez (el servidor atiende 16 y es
    compartido). Así la espera ocurre aquí y el timeout solo cuenta el tiempo real de servicio."""
    n = int(os.environ.get('QWEN_MAX_SIMULTANEAS', '12'))
    with _lock_sem:
        if n not in _semaforos:
            _semaforos[n] = threading.BoundedSemaphore(n)
        return _semaforos[n]


class QwenNoDisponible(Exception):
    pass


def url():
    return os.environ.get('QWEN_URL', 'http://172.16.8.69:8000/v1').rstrip('/')


def modelo():
    return os.environ.get('QWEN_MODEL', 'Qwen/Qwen3-8B-AWQ')


def contexto():
    return int(os.environ.get('QWEN_MAX_LEN', '8192'))


def cliente():
    u = url()
    if u not in _clientes:
        _clientes[u] = OpenAI(base_url=u, api_key='no-se-necesita', max_retries=0,
                              timeout=float(os.environ.get('QWEN_TIMEOUT', '120')))
    return _clientes[u]


def disponible():
    u = url()
    t, ok = _cache_disp.get(u, (0, None))
    if ok is not None and time.time() - t < 30:
        return ok
    try:
        with urllib.request.urlopen(u + '/models', timeout=3) as r:
            json.load(r)
        ok = True
    except Exception:
        ok = False
    _cache_disp[u] = (time.time(), ok)
    return ok


def contar_tokens(texto):
    """Tokens según el tokenizador del servidor; si no responde, estimación conservadora (1 token / 2.5 caracteres)."""
    if not texto:
        return 0
    if _cache_disp.get(url(), (0, True))[1] is not False:
        try:
            base = re.sub(r'/v1$', '', url())
            req = urllib.request.Request(base + '/tokenize', method='POST', headers={'Content-Type': 'application/json'},
                                         data=json.dumps({'model': modelo(), 'prompt': texto}).encode('utf-8'))
            with urllib.request.urlopen(req, timeout=5) as r:
                return int(json.load(r)['count'])
        except Exception:
            pass
    return math.ceil(len(texto) / 2.5)


def tokens_aprox(texto):
    """Compatibilidad: estimación local sin red."""
    return math.ceil(len(texto or '') / 2.5)


def _llamar(sistema, usuario, esquema, nombre, max_tokens, pensar, temperatura):
    return cliente().chat.completions.create(
        model=modelo(), temperature=temperatura, max_tokens=max_tokens,
        messages=[{'role': 'system', 'content': sistema}, {'role': 'user', 'content': usuario}],
        response_format={'type': 'json_schema', 'json_schema': {'name': nombre, 'schema': esquema}},
        extra_body={'chat_template_kwargs': {'enable_thinking': pensar}})


def json_con_esquema(sistema, usuario, esquema, nombre='salida', max_tokens=None, pensar=False, temperatura=0.0):
    """Devuelve (dict, métricas). Ajusta max_tokens a lo que queda de la ventana."""
    entrada = contar_tokens(sistema) + contar_tokens(usuario) + MARGEN
    libre = contexto() - entrada
    if libre < 256:
        raise ValueError(f'La entrada (~{entrada} tokens) no deja espacio de salida en la ventana de {contexto()}.')
    max_tokens = min(max_tokens or libre, libre)
    t0 = time.time()
    r = None
    for intento in range(2):
        try:
            with _semaforo():
                r = _llamar(sistema, usuario, esquema, nombre, max_tokens, pensar, temperatura)
            break
        except openai.BadRequestError as e:
            m = re.search(r'at least (\d+) input tokens', str(e))
            if intento or 'maximum context length' not in str(e) or not m:
                raise
            max_tokens = contexto() - int(m.group(1)) - 16
            if max_tokens < 128:
                raise
        except (openai.APITimeoutError, openai.APIConnectionError) as e:
            if intento:
                _cache_disp[url()] = (time.time(), False)
                raise QwenNoDisponible(f'El servidor de IA no respondió ({type(e).__name__}).') from e
    dt = time.time() - t0
    txt = r.choices[0].message.content or ''
    met = dict(segundos=round(dt, 2), entrada=r.usage.prompt_tokens, salida=r.usage.completion_tokens,
               fin=r.choices[0].finish_reason)
    if r.choices[0].finish_reason == 'length':
        raise ValueError(f'La respuesta se cortó por longitud ({met}).')
    return json.loads(txt), met
