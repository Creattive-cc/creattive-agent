"""
scripts/ingest_pdfs.py — Ingestão de PDFs no ChromaDB.
Responsabilidade: ler PDFs de data/pdfs/, chunkar via pypdf e indexar no ChromaDB local.
"""

import pypdf
import chromadb
import pathlib
import os
