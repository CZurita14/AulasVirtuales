"""La interfaz funciona tanto en / como detrás del proxy /aulasvirtuales/."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='verificación de JavaScript requiere Node.js')
@pytest.mark.parametrize('base', ['https://ejemplo.test/', 'https://ejemplo.test/aulasvirtuales/'])
def test_operaciones_respetan_la_ruta_publica(base):
    sistema = Path(__file__).resolve().parents[1]
    resultado = subprocess.run(
        ['node', str(Path(__file__).with_name('comprobar_ruta_publica.cjs')),
         str(sistema / 'static' / 'index.html'), base],
        capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
