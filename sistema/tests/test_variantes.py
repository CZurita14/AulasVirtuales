# -*- coding: utf-8 -*-
"""Variantes reales del formato institucional del sílabo (cada PDF de silabos_prueba/ debe pasar).

Casos cubiertos por el sílabo de Medicina (Computación y Sociedad, B26):
- sesiones de UN solo día ("Sesión 1 06/10/2026") en lugar de un rango;
- tabla de sesiones con columnas vacías extra (el lector mapea por encabezado, no por posición);
- sesiones de examen con 0.0 h práctico-experimentales y autónomas;
- PIS vacío en el sílabo (la página no debe inventarlo);
- libros sin URL/DOI (se citan sin "Acceder") y apellidos compuestos;
- títulos de momento en MAYÚSCULAS.
"""
import glob
import os
import re
import sys

import httpx
import pytest
from bs4 import BeautifulSoup

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import render, servicio, silabo, validador  # noqa: E402
from mock_canvas import TOKEN, MockCanvas  # noqa: E402

MED = os.path.join(ROOT, 'silabos_prueba', 'silabo_pf20261106_165315med-paral_02.pdf')
TODOS = sorted(glob.glob(os.path.join(ROOT, 'silabos_prueba', '*.pdf')) + glob.glob(os.path.join(ROOT, '*.pdf')))


@pytest.mark.parametrize('separador', [[], [''], ['', '']])
def test_cabecera_momento_admite_distinto_numero_de_columnas(separador):
    rows = [
        ['Momento 1', *separador, 'Bioética'],
        ['Fecha', *separador, '06/10/2026 al 03/11/2026'],
        ['Resultados de aprendizaje', *separador, 'RA1, RA2'],
        ['Evidencia de desempeño (producto esperado)', *separador, 'Análisis de un caso.'],
    ]
    d = {'momentos': []}
    silabo._momentos(rows, d)
    m = d['momentos'][0]
    assert m['titulo'] == 'Bioética'
    assert (m['inicio'], m['fin']) == ('06/10/2026', '03/11/2026')
    assert m['ra'] == ['RA1', 'RA2']
    assert m['evidencia'] == 'Análisis de un caso.'


@pytest.mark.parametrize('pdf', TODOS, ids=[os.path.basename(p) for p in TODOS])
def test_cada_silabo_genera_paginas_validas(pdf):
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    s = servicio.analizar(pdf, 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                          transport=httpx.MockTransport(m.handler))
    graves = [a for a in s['advertencias'] if a['grave'] and a['tipo'] not in ('Curso',)]
    assert not graves, graves  # un sílabo completo no debe dar errores de lectura
    sil = s['silabo']
    for mo in sil['momentos']:
        assert mo['sesiones'] and all(x['n'] > 0 and x['desde'] for x in mo['sesiones'])
        assert all(x['hd'] and x['hpe'] and x['ha'] for x in mo['sesiones'])
        assert len(mo['rubrica']) >= 1 and all(len(niv) == 5 and all(niv) for _, niv in mo['rubrica'])
        assert all(sil['ra'].get(c) for c in mo['ra'])
    servicio.generar(s)
    fallos = {n: [i['nombre'] for i in items if not i['ok'] and i['bloquea']] for n, items in s['control'].items()}
    assert s['listo'] and not any(fallos.values()), fallos


@pytest.fixture(scope='module')
def med():
    return silabo.leer(MED)


def test_med_sesiones_de_un_dia_y_columnas_extra(med):
    m2 = next(m for m in med['momentos'] if m['n'] == 2)
    assert [(x['n'], x['desde'], x['hasta']) for x in m2['sesiones']] == [
        (1, '10/11/2026', ''), (2, '17/11/2026', ''), (3, '24/11/2026', ''), (4, '01/12/2026', '')]
    assert [(x['hd'], x['hpe'], x['ha']) for x in m2['sesiones']] == [
        ('2.0', '2.0', '1.0'), ('2.0', '2.0', '2.0'), ('2.0', '2.0', '2.0'), ('2.0', '0.0', '0.0')]
    assert m2['totales'] == ('8.0', '6.0', '5.0')
    assert m2['sesiones'][0]['doc'].startswith('Taller sobre diseño de formularios digitales')
    assert m2['sesiones'][0]['pe'].startswith('Creación de un formulario digital')
    assert m2['sesiones'][0]['aut'].startswith('Investigación de buenas prácticas')


def test_med_horas_cuadran_con_la_presentacion(med):
    tipos = [a['tipo'] for a in validador.validar(med)]
    assert 'Horas' not in tipos and 'Sesiones' not in tipos and 'Fechas solapadas' not in tipos


def test_med_ra_completos_desde_la_tabla(med):
    assert med['ra']['RA1'].startswith('Identifica la importancia y el impacto de las TIC')
    assert med['ra']['RA1'].endswith('quehacer Humano')
    assert med['ra']['RA2'].startswith('Maneja los servicios de la Web')


def test_med_pis_vacio_no_se_inventa(med):
    assert med['pis'] == {'titulo': '', 'aporte': ''}
    assert any(a['tipo'] == 'PIS' for a in validador.validar(med))


def test_bibliografia_ignora_menciones_en_recursos_y_separa_autores_completos():
    texto = '''Índice
VI. BIBLIOGRAFÍA
VII. FIRMAS
IV. MOMENTOS DEL PROYECTO FORMATIVO
Recursos para el aprendizaje
Bibliografía básica y complementaria en eLibro; plataforma Canvas LMS.
Rúbrica de evaluación
Momento 2
Texto de sesiones que no es una referencia.
VI. BIBLIOGRAFÍA
Bibliografía básica
Alarcón-Benítez, Ángel (Ed.). (2023). Eugenio Espejo, médico y prócer. Acacia.
Kottow Lang, Miguel H. (2026). La medicina como bien común. Editorial Universitaria de Chile.
https://elibro.net/es/lc/uti/titulos/123
Bibliografía complementaria
Vargas, Amalia. (2026). Sabidurías ancestrales, I: medicina tradicional. Editorial Biblos.
https://elibro.net/es/lc/uti/titulos/456
VII. FIRMAS
Firmas del docente y autoridades.'''
    b = silabo._biblio(texto)
    assert len(b['basica']) == 2
    assert b['basica'][0]['texto'].startswith('Alarcón-Benítez, Ángel (Ed.). (2023).')
    assert b['basica'][1]['texto'].startswith('Kottow Lang, Miguel H. (2026).')
    assert b['basica'][1]['url'] == 'https://elibro.net/es/lc/uti/titulos/123'
    assert len(b['complementaria']) == 1
    assert b['complementaria'][0]['url'] == 'https://elibro.net/es/lc/uti/titulos/456'
    assert all('Rúbrica' not in o['texto'] and 'Firmas' not in o['texto']
               for obras in b.values() for o in obras)


def test_mencion_de_bibliografia_en_recursos_no_es_una_seccion():
    assert silabo._biblio('Recursos: Bibliografía básica y complementaria en eLibro; Canvas LMS.') == {
        'basica': [], 'complementaria': []}


def test_med_bibliografia_completa_con_libros_sin_url(med):
    bas = med['bibliografia']['basica']
    assert [o['texto'].split(' (')[0] for o in bas] == ['Castillo, F.; Naranjo-Avalos, H.; Buele, J.; et al.',
                                                       'Romero Gómez, F.', 'Solanet, V.; Martí, A.']
    assert bas[0]['url'] == 'https://repositorio.uti.edu.ec/items/9197e385-71be-450a-979a-76247b5ebe4e'
    assert bas[1]['url'] == '' and bas[2]['url'] == ''
    assert len(med['bibliografia']['complementaria']) == 1


def test_med_html_generado():
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    s = servicio.analizar(MED, 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                          transport=httpx.MockTransport(m.handler))
    servicio.generar(s)
    soup = BeautifulSoup(s['paginas'][2], 'html.parser')
    tablas = soup.find_all('table', recursive=False)
    assert 'Proyecto Interdisciplinario' not in soup.get_text()          # sin PIS
    fila4 = tablas[2].find('tbody').find_all('tr', recursive=False)[3]
    assert re.sub(r'\s+', ' ', fila4.find('th').get_text(' ')).strip() == '4 Fecha: 01/12/2026'
    bas = tablas[-1].find('tbody').find_all('td')[0]
    assert len(bas.find_all('p')) == 3 and len(bas.find_all('a')) == 1  # 2 libros sin "Acceder"
    assert 'Computación I' in bas.find_all('p')[1].find('em').get_text()


def _sesion_med():
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    return servicio.analizar(MED, 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                             transport=httpx.MockTransport(m.handler))


def test_checklist_avisa_lo_que_falta_sin_bloquear():
    s = _sesion_med()
    servicio.generar(s)
    assert s['listo'] is True
    for items in s['control'].values():
        av = {i['nombre']: i for i in items if not i['bloquea']}
        assert av['Sílabo: PIS registrado']['ok'] is False
        det = av['Sílabo: todas las obras con enlace']['detalle']
        assert av['Sílabo: todas las obras con enlace']['ok'] is False
        assert 'Romero Gómez, F. (2021)' in det and 'Solanet, V.; Martí, A. (2020)' in det


def test_enlace_agregado_por_el_docente():
    s = _sesion_med()
    claves = {o['texto'].split(',')[0]: o['clave'] for o in s['silabo']['bibliografia']['basica'] if not o['url']}
    url = 'https://biblioteca.ejemplo.edu/libro/123'
    servicio.generar(s, urls={claves['Romero Gómez']: url, claves['Solanet']: 'no-es-url'})
    bas = BeautifulSoup(s['paginas'][1], 'html.parser').find_all('table', recursive=False)[-1].find('tbody').find_all('td')[0]
    assert [a['href'] for a in bas.find_all('a')] == [s['silabo']['bibliografia']['basica'][0]['url'], url]
    av = next(i for i in s['control'][1] if i['nombre'] == 'Sílabo: todas las obras con enlace')
    assert av['ok'] is False and 'Solanet' in av['detalle'] and 'Romero' not in av['detalle']
    assert s['listo']
    from core import paquete
    assert 'PROPUESTO: no están en el sílabo' in paquete.informe(s) and url in paquete.informe(s)


def test_silabo_completo_sin_avisos():
    m = MockCanvas(plantilla_body=render.leer_plantilla_institucional())
    pdf = os.path.join(ROOT, 'B26_Software_Programacion Estructurada.pdf')
    s = servicio.analizar(pdf, 'https://indoamerica.instructure.com/courses/36254', TOKEN,
                          transport=httpx.MockTransport(m.handler))
    servicio.generar(s)
    assert all(i['ok'] for items in s['control'].values() for i in items)
