# -*- coding: utf-8 -*-
"""Estado de las piezas del sistema. Nunca lanza: si algo no responde, lo informa."""
import json
import os
import urllib.request


def _qwen():
    url = os.environ.get('QWEN_URL', 'http://172.16.8.69:8000/v1').rstrip('/')
    try:
        with urllib.request.urlopen(url + '/models', timeout=3) as r:
            json.load(r)
        return 'ok'
    except Exception:
        return 'no_disponible'


def _qdrant():
    url = os.environ.get('QDRANT_URL', '')
    if not url:
        return 'memoria'
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/collections', timeout=3) as r:
            json.load(r)
        return 'ok'
    except Exception:
        return 'no_disponible'


def estado():
    return dict(reglas='ok', qwen=_qwen(), qdrant=_qdrant(),
                modelo=os.environ.get('QWEN_MODEL', 'Qwen/Qwen3-8B-AWQ'),
                ia_activa=os.environ.get('IA_ACTIVA', '1') == '1')
