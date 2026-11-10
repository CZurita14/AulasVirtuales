"""Las referencias sin URL no se reescriben al generar ni publicar."""
import sys
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import render, servicio
from mock_canvas import TOKEN, MockCanvas


@pytest.mark.parametrize('texto', [
    'Pérez, A. (2024). Enfermería clínica. Editorial Salud. Página 35',
    'Gómez, L. (2023). Cuidados. Revista de Salud, 12(2), 10–20. Editorial Médica. Páginas 15–18.',
    'Libro de anatomía & fisiología <consulta>, página 42',
])
@pytest.mark.parametrize('url_doc', ['', 'https://biblioteca.ejemplo.edu/libro'])
def test_copia_literal_sin_url_en_vista_previa_y_publicacion(texto, url_doc):
    raiz = Path(__file__).resolve().parents[2]
    pdf = raiz / 'silabos_prueba' / 'silabo_pf20261106_165315med-paral_02.pdf'
    mock = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    s = servicio.analizar(str(pdf), 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                          transport=httpx.MockTransport(mock.handler))
    s['silabo']['bibliografia'] = {
        'basica': [dict(texto=texto, url='', clave='basica')],
        'complementaria': [dict(texto=texto, url='', clave='complementaria')],
    }
    s['complementaria'] = {m['n']: ['complementaria'] for m in s['silabo']['momentos']}
    servicio.generar(s, urls={'basica': url_doc, 'complementaria': url_doc})

    def comprobar(html):
        soup = BeautifulSoup(html, 'html.parser')
        tabla = render._bloques(soup)['biblio']
        ps = tabla.find('tbody').find_all('p')
        assert len(ps) == 2
        for p in ps:
            numero = p.find('strong')
            assert numero.get_text() == '1.'
            numero.extract()
            a = p.find('a')
            if url_doc:
                assert a['href'] == url_doc and a.get_text() == 'Acceder'
                a.extract()
            else:
                assert a is None
            assert p.get_text().strip() == texto

    comprobar(s['paginas'][1])
    aviso = next(c for c in s['control'][1] if c['nombre'] == 'Sílabo: todas las obras con enlace')
    assert aviso['ok'] == bool(url_doc)
    assert not aviso['bloquea']
    assert all(c['ok'] for c in s['control'][1] if c['bloquea'])
    resultado = servicio.publicar(s, [1], confirmado=True)
    assert resultado[1]['ok']
    comprobar(s['canvas'].pagina(s['destinos'][1]['slug'])['body'])
