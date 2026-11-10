# -*- coding: utf-8 -*-
"""/api/salud: estado de las piezas (reglas, Qwen, Qdrant) sin bloquear aunque la IA no responda."""
import os
import sys
import time

from fastapi.testclient import TestClient

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SIS)

import app as appmod  # noqa: E402


def test_salud_sin_qwen_responde_200(monkeypatch):
    monkeypatch.setenv('QWEN_URL', 'http://127.0.0.1:9/v1')
    monkeypatch.setenv('QDRANT_URL', '')
    t = time.time()
    r = TestClient(appmod.app).get('/api/salud')
    assert r.status_code == 200
    j = r.json()
    assert j['reglas'] == 'ok'
    assert j['qwen'] == 'no_disponible'
    assert j['qdrant'] == 'memoria'
    assert j['modelo']
    assert time.time() - t < 6
