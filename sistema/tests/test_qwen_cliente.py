# -*- coding: utf-8 -*-
"""Cliente Qwen: presupuesto de la ventana de 8192, reintento único y disponibilidad (sin red salvo donde se indica)."""
import glob
import os
import sys
import time
from types import SimpleNamespace

import httpx
import openai
import pytest

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)

from ia import documento, extractor, qwen  # noqa: E402


def _resp(texto='{"ok": true}', fin='stop', entrada=100, salida=10):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=texto), finish_reason=fin)],
                           usage=SimpleNamespace(prompt_tokens=entrada, completion_tokens=salida))


class ClienteFalso:
    def __init__(self, efectos):
        self.efectos = list(efectos)
        self.llamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.llamadas.append(kw)
        e = self.efectos.pop(0)
        if isinstance(e, Exception):
            raise e
        return e


def _bad_request(msg):
    req = httpx.Request('POST', 'http://x/v1/chat/completions')
    return openai.BadRequestError(msg, response=httpx.Response(400, request=req), body=None)


ESQ = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}


def test_reduce_max_tokens_si_excede_ventana(monkeypatch):
    falso = ClienteFalso([_bad_request("This model's maximum context length is 8192 tokens. However, you requested "
                                       "7326 output tokens and your prompt contains at least 867 input tokens"), _resp()])
    monkeypatch.setattr(qwen, 'cliente', lambda: falso)
    monkeypatch.setattr(qwen, 'contar_tokens', lambda t: len(t) // 4 + 1)
    datos, met = qwen.json_con_esquema('sis', 'usuario', ESQ)
    assert datos == {'ok': True}
    assert len(falso.llamadas) == 2
    assert falso.llamadas[1]['max_tokens'] + 867 <= 8192
    assert falso.llamadas[1]['max_tokens'] < falso.llamadas[0]['max_tokens']


def test_presupuesto_con_texto_en_ingles_y_urls(monkeypatch):
    """El caso real que falló: la bibliografía de Programación Estructurada (inglés + URL)."""
    pdf = os.path.join(ROOT, 'B26_Software_Programacion Estructurada.pdf')
    bib = next(f['texto'] for f in documento.fragmentos(pdf) if f['bloque'] == 'bibliografia')
    usuario = extractor.INSTR['bibliografia'] + '\n\nFILAS DEL SÍLABO:\n' + bib
    falso = ClienteFalso([_resp()])
    monkeypatch.setattr(qwen, 'cliente', lambda: falso)
    qwen.json_con_esquema(extractor.REGLAS, usuario, ESQ)
    entrada = qwen.contar_tokens(extractor.REGLAS) + qwen.contar_tokens(usuario)  # cuenta real si el servidor responde
    assert falso.llamadas[0]['max_tokens'] + entrada <= 8192 - 32


def test_contar_tokens_no_subestima_ingles_con_urls(monkeypatch):
    monkeypatch.setenv('QWEN_URL', 'http://127.0.0.1:9/v1')  # sin servidor: usa la estimación de respaldo
    qwen._cache_disp.clear()
    texto = 'Bible, P. W., & Moser, L. (2023). An open guide to data structures and algorithms. https://doi.org/10.3390/math12050629 ' * 20
    # el tokenizador real de Qwen da ~1 token cada 3.4 caracteres en este texto; la estimación debe quedar por encima
    assert qwen.contar_tokens(texto) >= len(texto) / 3.0


def test_timeout_lanza_qwen_no_disponible(monkeypatch):
    req = httpx.Request('POST', 'http://x/v1/chat/completions')
    falso = ClienteFalso([openai.APITimeoutError(request=req), openai.APITimeoutError(request=req)])
    monkeypatch.setattr(qwen, 'cliente', lambda: falso)
    monkeypatch.setattr(qwen, 'contar_tokens', lambda t: 10)
    with pytest.raises(qwen.QwenNoDisponible):
        qwen.json_con_esquema('sis', 'usuario', ESQ)
    assert len(falso.llamadas) == 2


def test_disponible_falso_si_no_responde(monkeypatch):
    monkeypatch.setenv('QWEN_URL', 'http://127.0.0.1:9/v1')
    qwen._cache_disp.clear()
    t = time.time()
    assert qwen.disponible() is False
    assert time.time() - t < 4
