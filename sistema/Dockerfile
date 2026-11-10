FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 \
    FASTEMBED_CACHE=/modelos \
    EMBEDDINGS_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# El modelo de embeddings queda dentro de la imagen: el contenedor no descarga nada al arrancar.
RUN python -c "import os; from fastembed import TextEmbedding; TextEmbedding(os.environ['EMBEDDINGS_MODEL'], cache_dir=os.environ['FASTEMBED_CACHE'])"

COPY . .
EXPOSE 8770
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8770"]
