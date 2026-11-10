# -*- coding: utf-8 -*-
"""Propósito del momento redactado por Qwen, validado; si no sirve, se usa la regla (sin red)."""
import os
import sys

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)

from core import propuestas, silabo  # noqa: E402
from ia import qwen  # noqa: E402

SIL = silabo.leer(os.path.join(ROOT, 'B26_Software_Programacion Estructurada.pdf'))
REGLA = propuestas.proponer(SIL)['propositos']


def _qwen(monkeypatch, texto, disponible=True):
    llamadas = []

    def falso(sistema, usuario, esquema, nombre='salida', **kw):
        llamadas.append(usuario)
        return {'proposito': texto}, {}
    monkeypatch.setattr(qwen, 'disponible', lambda: disponible)
    monkeypatch.setattr(qwen, 'json_con_esquema', falso)
    return llamadas


def test_proposito_ia_valido_se_usa(monkeypatch):
    t = 'Seleccionar estructuras de datos lineales adecuadas para el caso, justificando su eficiencia con criterios de memoria y tiempo.'
    llamadas = _qwen(monkeypatch, t)
    p = propuestas.proponer(SIL, usar_ia=True)['propositos']
    assert p[2] == t and len(llamadas) == 4
    assert SIL['momentos'][1]['titulo'] in llamadas[1]


def test_dos_oraciones_usa_la_regla(monkeypatch):
    _qwen(monkeypatch, 'Diseñar la solución del caso. Luego implementar las estructuras.')
    assert propuestas.proponer(SIL, usar_ia=True)['propositos'] == REGLA


def test_sin_infinitivo_usa_la_regla(monkeypatch):
    _qwen(monkeypatch, 'El estudiante selecciona estructuras de datos para el caso.')
    assert propuestas.proposito_ia(SIL['momentos'][0]) is None


def test_copia_de_la_evidencia_se_rechaza(monkeypatch):
    m = SIL['momentos'][0]
    _qwen(monkeypatch, 'Elaborar la ' + m['evidencia'][0].lower() + m['evidencia'][1:])
    assert propuestas.proposito_ia(m) is None


def test_qwen_no_disponible_usa_la_regla_sin_llamar(monkeypatch):
    llamadas = _qwen(monkeypatch, 'Diseñar algo útil para el caso.', disponible=False)
    assert propuestas.proponer(SIL, usar_ia=True)['propositos'] == REGLA and llamadas == []


def test_error_de_qwen_usa_la_regla(monkeypatch):
    monkeypatch.setattr(qwen, 'disponible', lambda: True)

    def falla(*a, **k):
        raise qwen.QwenNoDisponible('caído')
    monkeypatch.setattr(qwen, 'json_con_esquema', falla)
    assert propuestas.proponer(SIL, usar_ia=True)['propositos'] == REGLA
