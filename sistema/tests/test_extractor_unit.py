# -*- coding: utf-8 -*-
"""Entrada etiquetada por columna para Qwen y filtro contra valores inventados (sin red)."""
import os
import sys

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SIS)
sys.path.insert(0, SIS)

from ia import documento, extractor  # noqa: E402

MED = os.path.join(ROOT, 'silabos_prueba', 'silabo_pf20261106_165315med-paral_02.pdf')
B26 = os.path.join(ROOT, 'B26_Software_Programacion Estructurada.pdf')


def _campo(registro, etiqueta):
    linea = next(l for l in registro.split('\n') if l.startswith(etiqueta + ':'))
    return linea.split(':', 1)[1].strip()


def test_registros_sesiones_med_m1():
    reg = documento.registros_sesiones(MED)
    s3 = reg[1][2]
    assert _campo(s3, 'HORAS DOCENTE') == '2.0'
    assert _campo(s3, 'ACTIVIDADES CON EL DOCENTE').endswith('digitales en medicina.')  # continuación de la pág. 5
    assert [len(reg[m]) for m in (1, 2, 3, 4)] == [4, 4, 6, 4]


def test_registros_columnas_extra_m2():
    s1 = documento.registros_sesiones(MED)[2][0]
    assert _campo(s1, 'HORAS DOCENTE') == '2.0'
    assert _campo(s1, 'HORAS PRÁCTICO') == '2.0'
    assert _campo(s1, 'HORAS AUTÓNOMO') == '1.0'
    assert _campo(s1, 'ACTIVIDADES PRÁCTICO-EXPERIMENTALES').startswith('Creación de un formulario digital')


def test_registros_b26_separa_otras_actividades():
    s1 = documento.registros_sesiones(B26)[2][0]
    doc = _campo(s1, 'ACTIVIDADES CON EL DOCENTE')
    assert 'Otras actividades' not in doc and doc.endswith('con ejemplos resueltos en el entorno de programación.')
    assert _campo(s1, 'HORAS DOCENTE') == '6.0'
    assert _campo(s1, 'OTRAS ACTIVIDADES (HORAS)') == '4.0'
    assert _campo(s1, 'OTRAS ACTIVIDADES').endswith('operaciones que la solución debe realizar sobre ella.')


def test_registros_sin_otras_actividades_quedan_vacias():
    s1 = documento.registros_sesiones(MED)[1][0]
    assert _campo(s1, 'OTRAS ACTIVIDADES (HORAS)') == '' and _campo(s1, 'OTRAS ACTIVIDADES') == ''


def test_pie_momentos_totales_etiquetados():
    pie = documento.pie_momentos(B26)
    assert _campo(pie[3], 'TOTAL DOCENTE') == '27.0'
    assert _campo(pie[3], 'TOTAL PRÁCTICO') == '24.0'
    assert _campo(pie[3], 'TOTAL AUTÓNOMO') == '20.0'
    assert _campo(pie[3], 'RECURSOS PARA EL APRENDIZAJE').startswith('Entorno de programación')
    assert _campo(pie[3], 'POLÍTICA DE IA').startswith('Se permite el uso de IA para depurar')
    assert _campo(documento.pie_momentos(MED)[2], 'TOTAL PRÁCTICO') == '6.0'


def test_limpiar_rotulos():
    assert extractor.limpiar_rotulos('Proyecto interdisciplinario socioformativo', extractor.ROTULOS_PIS) == ''
    assert extractor.limpiar_rotulos('  proyecto interdisciplinario  socioformativo. ', extractor.ROTULOS_PIS) == ''
    v = 'Desarrollo de soluciones de software para escenarios simulados'
    assert extractor.limpiar_rotulos(v, extractor.ROTULOS_PIS) == v
    assert extractor.limpiar_rotulos('Actividades con el docente', extractor.ROTULOS_SESIONES) == ''


def test_bibliografia_partida_si_no_cabe():
    partes = extractor.partes_bibliografia('Bibliografía básica\nA, B. (2020). T. X.\nBibliografía complementaria\nC, D. (2021). U. Y.')
    assert [p[0] for p in partes] == ['basica', 'complementaria']
    largo = 'Bibliografía básica\n' + '\n'.join(f'Autor{i}, A. (2020). Titulo {i} ' + 'x' * 400 + '. Ed.' for i in range(20))
    partes = extractor.partes_bibliografia(largo, max_tokens=1500)
    assert len(partes) > 1 and all(p[0] == 'basica' for p in partes)
    assert sum(p[1].count('(2020)') for p in partes) == 20


def test_bibliografia_larga_separa_obras_con_editor_y_nombre_completo():
    texto = 'Bibliografía básica\n' + '\n'.join(
        f'Alarcón-Benítez, Ángel (Ed.). (2023). Obra {i} ' + 'x' * 400 + '. Editorial.' for i in range(20))
    partes = extractor.partes_bibliografia(texto, max_tokens=1500)
    assert len(partes) > 1
    assert sum(t.count('(2023)') for _, t in partes) == 20
    assert all(extractor.qwen.tokens_aprox(t) <= 1500 for _, t in partes)
