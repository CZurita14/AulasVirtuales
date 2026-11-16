# -*- coding: utf-8 -*-
"""Ninguna prueba escribe en el historial real del docente: cada sesión de pruebas usa una base temporal."""
import pytest


@pytest.fixture(autouse=True, scope='session')
def _historial_temporal(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv('HISTORIAL_DB', str(tmp_path_factory.mktemp('historial') / 'historial.sqlite'))
    yield
    mp.undo()
