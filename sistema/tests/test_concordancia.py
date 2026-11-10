# -*- coding: utf-8 -*-
"""Diferencias reglas ↔ IA que se muestran al docente (sin red)."""
import copy
import os
import sys

SIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SIS)

from ia import concordancia  # noqa: E402


def _sil():
    ses = dict(n=1, desde='22/12/2026', hasta='04/01/2027', doc='Clase invertida.', hd='6.0', otras_h='4.0',
               otras='Taller.', pe='Práctica.', hpe='6.0', aut='Lectura.', ha='5.0', cont='Listas enlazadas.')
    return dict(ra={'RA1': 'Identifica estructuras de datos.'}, pis=dict(titulo='PIS X', aporte='Aporte Y'),
                bibliografia=dict(basica=[dict(texto='A, B. (2020). T. X.', url='https://x.org/1', clave='https://x.org/1')],
                                  complementaria=[]),
                momentos=[dict(n=2, titulo='Planeación', inicio='22/12/2026', fin='12/01/2027', ra=['RA1'],
                               evidencia='Ficha.', sesiones=[ses], totales=('6.0', '6.0', '5.0'),
                               rubrica=[['Ind', ['a', 'b', 'c', 'd', 'e']]])])


def test_sin_diferencias_triviales():
    ref, ia = _sil(), _sil()
    ia['ra']['RA1'] = 'Identifica estructuras de datos'           # sin punto final
    ia['momentos'][0]['sesiones'][0]['cont'] = '• Listas  enlazadas.'  # viñeta y espacio doble
    ia['momentos'][0]['ra'] = ['ra1']                              # código en minúsculas
    assert concordancia.discrepancias(ref, ia) == []


def test_horas_es_alta():
    ref, ia = _sil(), _sil()
    ia['momentos'][0]['sesiones'][0]['hd'] = '4.0'
    d = concordancia.discrepancias(ref, ia)
    assert len(d) == 1 and d[0]['campo'] == 'M2.S1.horas' and d[0]['gravedad'] == 'alta'
    assert d[0]['reglas'] == '6.0/6.0/5.0/4.0' and d[0]['ia'] == '4.0/6.0/5.0/4.0'


def test_ia_vacia_no_es_discrepancia_de_texto():
    ref, ia = _sil(), _sil()
    ia['pis']['titulo'] = ''  # descartado por limpiar_rotulos
    d = concordancia.discrepancias(ref, ia)
    assert [(x['campo'], x['tipo'], x['gravedad']) for x in d] == [('titulo', 'ia_sin_dato', 'media')]


def test_texto_distinto_es_media_y_altas_primero():
    ref, ia = _sil(), _sil()
    ia['momentos'][0]['sesiones'][0]['doc'] = 'Otra cosa.'
    ia['momentos'][0]['fin'] = '13/01/2027'
    d = concordancia.discrepancias(ref, ia)
    assert [(x['campo'], x['gravedad']) for x in d] == [('M2.fin', 'alta'), ('M2.S1.docente', 'media')]
    r = concordancia.resumen(d)
    assert r == dict(total=2, altas=1, medias=1, por_categoria={'Cabecera': 1, 'Texto de sesiones': 1})
