# -*- coding: utf-8 -*-
"""BD vectorial (Qdrant) con embeddings multilingües locales (FastEmbed, sin enviar nada a internet).

QDRANT_URL=http://qdrant:6333  → servidor Qdrant (Docker)
QDRANT_URL vacío               → modo local en memoria (pruebas)
"""
import hashlib
import os
import uuid
import warnings

from qdrant_client import QdrantClient, models

COLECCION = 'silabos'
MODELO_EMB = os.environ.get('EMBEDDINGS_MODEL', 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
_emb = None


def _embedder():
    global _emb
    if _emb is None:
        from fastembed import TextEmbedding
        with warnings.catch_warnings():   # aviso informativo de FastEmbed sobre su pooling: toda la colección usa la misma versión
            warnings.simplefilter('ignore', UserWarning)
            _emb = TextEmbedding(MODELO_EMB, cache_dir=os.environ.get('FASTEMBED_CACHE', None))
    return _emb


def embed(textos):
    return [list(map(float, v)) for v in _embedder().embed(list(textos))]


class Almacen:
    def __init__(self, url=None):
        url = os.environ.get('QDRANT_URL', '') if url is None else url
        self.local = not url
        self.cli = QdrantClient(url=url, timeout=30) if url else QdrantClient(':memory:')
        dim = len(embed(['prueba'])[0])
        if not self.cli.collection_exists(COLECCION):
            self.cli.create_collection(COLECCION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE))
            for campo, tipo in (('silabo_id', models.PayloadSchemaType.KEYWORD),
                                ('bloque', models.PayloadSchemaType.KEYWORD),
                                ('momento', models.PayloadSchemaType.INTEGER)):
                if not self.local:     # en memoria los índices no tienen efecto
                    self.cli.create_payload_index(COLECCION, campo, tipo)

    @staticmethod
    def id_silabo(pdf_path):
        with open(pdf_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def borrar(self, silabo_id):
        """Elimina todos los fragmentos de un sílabo (el sistema no conserva sílabos después de usarlos)."""
        self.cli.delete(COLECCION, points_selector=models.FilterSelector(filter=models.Filter(
            must=[models.FieldCondition(key='silabo_id', match=models.MatchValue(value=silabo_id))])))

    def indexar(self, silabo_id, fragmentos):
        """Idempotente: borra lo anterior de ese sílabo y vuelve a cargar."""
        self.cli.delete(COLECCION, points_selector=models.FilterSelector(filter=models.Filter(
            must=[models.FieldCondition(key='silabo_id', match=models.MatchValue(value=silabo_id))])))
        vecs = embed(f['texto'] for f in fragmentos)
        self.cli.upsert(COLECCION, points=[
            models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, f'{silabo_id}/{f["id"]}')), vector=v,
                               payload=dict(f, silabo_id=silabo_id))
            for f, v in zip(fragmentos, vecs)])
        return len(fragmentos)

    def bloques(self, silabo_id, bloque, momento=None):
        """Recupera por metadatos (exacto, en orden de página)."""
        must = [models.FieldCondition(key='silabo_id', match=models.MatchValue(value=silabo_id)),
                models.FieldCondition(key='bloque', match=models.MatchValue(value=bloque))]
        if momento is not None:
            must.append(models.FieldCondition(key='momento', match=models.MatchValue(value=momento)))
        pts, _ = self.cli.scroll(COLECCION, scroll_filter=models.Filter(must=must), limit=100, with_payload=True)
        return sorted((p.payload for p in pts), key=lambda x: x['id'])

    def buscar(self, silabo_id, consulta, k=3):
        """Búsqueda semántica dentro de un sílabo."""
        res = self.cli.query_points(COLECCION, query=embed([consulta])[0], limit=k, with_payload=True,
                                    query_filter=models.Filter(must=[models.FieldCondition(
                                        key='silabo_id', match=models.MatchValue(value=silabo_id))]))
        return [dict(p.payload, score=p.score) for p in res.points]

    def momentos(self, silabo_id):
        pts, _ = self.cli.scroll(COLECCION, scroll_filter=models.Filter(must=[
            models.FieldCondition(key='silabo_id', match=models.MatchValue(value=silabo_id)),
            models.FieldCondition(key='bloque', match=models.MatchValue(value='cabecera'))]), limit=100, with_payload=True)
        return sorted({p.payload['momento'] for p in pts})
