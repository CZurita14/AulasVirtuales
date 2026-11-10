"""Modo IA: extracción del sílabo con el modelo local de la universidad (Qwen3-8B vía vLLM) + BD vectorial.

El modelo NO escribe el HTML (su ventana es de 8192 tokens y una página Momento ocupa ~10 000):
extrae los datos del sílabo como JSON validado por esquema, y el renderizador determinista del
sistema construye la página. Así el diseño es siempre idéntico y lo que se evalúa es la lectura.
"""
