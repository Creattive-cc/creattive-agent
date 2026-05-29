
import os
import glob
import pathlib
import time
from functools import lru_cache
from typing import List

from google import genai as genai_new
from google.genai import errors as genai_errors
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

_IS_PROD = os.environ.get("ENV", "dev") == "prod"
_GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
_GCS_PREFIX = "chroma/"
_GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "creattive-licitacoes-dev")
_GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")


def _embed_with_retry(client, model: str, contents: str, max_retries: int = 5) -> list:
    delay = 2.0
    for attempt in range(max_retries):
        try:
            return client.models.embed_content(model=model, contents=contents).embeddings[0].values
        except genai_errors.ClientError as e:
            if e.status_code == 429 and attempt < max_retries - 1:
                print(f"[RAG] 429 rate limit, retry {attempt + 1}/{max_retries} in {delay:.1f}s")
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
            else:
                raise


class CustomGoogleGenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model: str = "gemini-embedding-001"):
        self._client = genai_new.Client(vertexai=True, project=_GCP_PROJECT, location=_GCP_LOCATION)
        self._model = model

    def __call__(self, input: Documents) -> Embeddings:
        results = []
        for i, doc in enumerate(input):
            if i > 0:
                time.sleep(0.5)
            results.append(_embed_with_retry(self._client, self._model, doc))
        return results


class RAGRetriever:
    def __init__(self, persist_directory: str = "/tmp/chroma"):
        self._client = genai_new.Client(vertexai=True, project=_GCP_PROJECT, location=_GCP_LOCATION)
        self.embedding_function = CustomGoogleGenAIEmbeddingFunction()
        self._persist_directory = persist_directory

        if _IS_PROD and _GCS_BUCKET:
            self._download_from_gcs()

        self.db_client = chromadb.PersistentClient(path=persist_directory)

        self.collection = self.db_client.get_or_create_collection(
            name="creattive_kb",
            embedding_function=self.embedding_function
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=50
        )

        if self.collection.count() == 0:
            print("Knowledge base is empty. Indexing all knowledge files...")
            self.index_all_knowledge()
            if _IS_PROD and _GCS_BUCKET:
                self._upload_to_gcs()

    def _gcs_client(self):
        from google.cloud import storage
        return storage.Client()

    def _download_from_gcs(self):
        try:
            client = self._gcs_client()
            bucket = client.bucket(_GCS_BUCKET)
            blobs = list(bucket.list_blobs(prefix=_GCS_PREFIX))
            if not blobs:
                print(f"GCS bucket '{_GCS_BUCKET}' has no chroma data. Will reindex.")
                return
            for blob in blobs:
                relative = blob.name[len(_GCS_PREFIX):]
                if not relative:
                    continue
                dest = pathlib.Path(self._persist_directory) / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                blob.download_to_filename(str(dest))
            print(f"Downloaded {len(blobs)} chroma files from GCS.")
        except Exception as e:
            print(f"GCS download skipped: {e}")

    def _upload_to_gcs(self):
        try:
            client = self._gcs_client()
            bucket = client.bucket(_GCS_BUCKET)
            base = pathlib.Path(self._persist_directory)
            files = list(base.rglob("*"))
            uploaded = 0
            for f in files:
                if f.is_file():
                    blob_name = _GCS_PREFIX + str(f.relative_to(base))
                    bucket.blob(blob_name).upload_from_filename(str(f))
                    uploaded += 1
            print(f"Uploaded {uploaded} chroma files to GCS bucket '{_GCS_BUCKET}'.")
        except Exception as e:
            print(f"GCS upload failed: {e}")

    def index_markdown(self, path: str, source_id: str):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        chunks = self.text_splitter.split_text(content)
        if chunks:
            self.collection.add(
                documents=chunks,
                ids=[f"{source_id}-{i}" for i in range(len(chunks))],
                metadatas=[{"source": source_id} for _ in range(len(chunks))],
            )
            print(f"Indexed {len(chunks)} chunks from {path}")

    def index_pdf(self, path: str):
        reader = PdfReader(path)
        full_text = "".join(page.extract_text() for page in reader.pages if page.extract_text())
        source_id = os.path.basename(path)
        chunks = self.text_splitter.split_text(full_text)
        if chunks:
            self.collection.add(
                documents=chunks,
                ids=[f"{source_id}-{i}" for i in range(len(chunks))],
                metadatas=[{"source": source_id} for _ in range(len(chunks))],
            )
            print(f"Indexed {len(chunks)} chunks from {path}")
        if _IS_PROD and _GCS_BUCKET:
            self._upload_to_gcs()

    @lru_cache(maxsize=128)
    def _cached_query_embedding(self, query: str) -> tuple:
        return tuple(_embed_with_retry(self._client, "gemini-embedding-001", query))

    def search(self, query: str, k: int = 5) -> List[str]:
        query_embedding = list(self._cached_query_embedding(query))
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents"]
        )
        return results["documents"][0] if results.get("documents") else []

    def index_all_knowledge(self):
        print("Starting to index all markdown files in 'knowledge/' directory...")
        md_files = glob.glob("knowledge/*.md")
        for md_file in md_files:
            source_id = os.path.basename(md_file)
            self.index_markdown(md_file, source_id)
        print("Finished indexing all knowledge files.")

    def clear(self):
        self.db_client.delete_collection(name="creattive_kb")
        self.collection = self.db_client.get_or_create_collection(
            name="creattive_kb",
            embedding_function=self.embedding_function
        )
        print("Cleared all documents from the knowledge base.")
        if _IS_PROD and _GCS_BUCKET:
            self._upload_to_gcs()

    def get_indexed_sources(self) -> dict:
        """Returns {source_name: chunk_count} for all indexed documents."""
        result = self.collection.get(include=["metadatas"])
        counts: dict = {}
        for meta in result.get("metadatas") or []:
            src = meta.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
        return counts

    def count(self) -> int:
        return self.collection.count()
