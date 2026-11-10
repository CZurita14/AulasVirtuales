# AulasVirtuales

Asistente para convertir sílabos institucionales PDF en páginas Momento de cursos de Canvas, con revisión del docente, respaldo y verificación de lo publicado.

## Ejecutar con Docker

```powershell
Copy-Item .env.example .env
# Ajustar .env con la dirección del servidor Qwen de la universidad.
docker compose up -d --build
```

Abrir http://localhost:8770. Para acceso externo se requiere HTTPS mediante un proxy o túnel. El archivo `.env`, los tokens de Canvas y los PDF de docentes no se incluyen en este repositorio.

La aplicación permite revisar las páginas antes de publicar, conserva referencias sin enlace, incluye toda la bibliografía complementaria por defecto y sustituye plantillas incompletas por la institucional. Cada publicación guarda un respaldo que puede restaurarse.

## Documentación

- [Uso, arquitectura y configuración](sistema/README.md)
- [Reglas de transformación del sílabo](PROMPT_MAESTRO_Silabo_a_Canvas.md)
- [Pruebas del HTML](tests/README.md)

## Pruebas y documentos privados

```powershell
python -m pip install -r sistema/requirements.txt
python -m pip install pytest
python -m pytest -q
```

La suite completa usa documentos locales que se excluyen por privacidad. Antes de ejecutarla, restaurar las siguientes muestras autorizadas en estas rutas (sin subirlas a Git):

- `B26_Software_Programacion Estructurada.pdf`
- `silabos_prueba/silabo_pf20261106_165315med-paral_02.pdf`
- `sistema/tests/fixtures/anatomia_general_b26.pdf`
- `sistema/tests/fixtures/integracion.pdf`

Sin estas muestras, los tests de integración con PDF no se pueden ejecutar. Las pruebas marcadas `qwen` requieren el modelo real y están excluidas por defecto. Ninguna prueba publica en Canvas real: se utiliza un simulador.
