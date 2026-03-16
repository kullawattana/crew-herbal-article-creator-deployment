"""
Universal RAG Module for CrewAI Projects
support PDF and JSON sources (filtering and MMR search)

Usage:
    from common_rag import RAGEngine
    
    # For PDF
    rag = RAGEngine(
        sources=["/path/to/doc.pdf"],
        source_type="pdf",
        target_label="my_doc"
    )
    
    # For JSON
    rag = RAGEngine(
        sources=["/path/to/data.json"],
        source_type="json",
        target_label="my_data"
    )
    
    # search and build context
    context = rag.build_context(["query1", "query2"], k=3)
"""

import os
import json
import glob
from pathlib import Path
from typing import List, Dict, Optional, Union

from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Document class with fallback
try:
    from langchain_core.documents import Document
except Exception:
    from langchain.docstore.document import Document

# PDF Loaders
try:
    from langchain_community.document_loaders import (
        PyMuPDFLoader,
        PyPDFium2Loader,
        PDFPlumberLoader
    )
    PDF_LOADERS_AVAILABLE = True
except ImportError:
    PDF_LOADERS_AVAILABLE = False
    print("[WARNING] PDF loaders not installed. Install with: pip install pymupdf pypdfium2 pdfplumber")


class RAGEngine:
    """
    Universal RAG Engine supporting both PDF and JSON sources
    """
    
    def __init__(
        self,
        sources: Union[str, List[str]],
        source_type: str = "pdf",  # "pdf" or "json"
        target_label: str = "default",
        chunk_size: int = 1000,
        chunk_overlap: int = 120,
        embedding_model: str = "models/text-embedding-004",
        use_mmr: bool = True,
        mmr_k: int = 8,
        mmr_fetch_k: int = 24,
        mmr_lambda: float = 0.5,
    ):
        """
        Initialize RAG Engine
        
        Args:
            sources: single file (str) / multiple file (List[str] or directory -> path
            source_type: "pdf" or "json"
            target_label: label and filter metadata
            chunk_size: chunk size for splitting
            chunk_overlap: overlap between chunks
            embedding_model: Google embedding model
            use_mmr (optional): MMR search or not
            mmr_k: number of results for MMR
            mmr_fetch_k: number of candidates for MMR
            mmr_lambda: diversity parameter (0-1)
        """
        self.source_type = source_type.lower()
        self.target_label = target_label
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_mmr = use_mmr
        self.mmr_k = mmr_k
        self.mmr_fetch_k = mmr_fetch_k
        self.mmr_lambda = mmr_lambda
        
        # Validate source type
        if self.source_type not in ["pdf", "json"]:
            raise ValueError(f"source_type must be 'pdf' or 'json', got: {source_type}")
        
        # Check API key
        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("Please set GOOGLE_API_KEY environment variable")
        
        # Collect source files
        self.source_files = self._collect_sources(sources)
        if not self.source_files:
            raise RuntimeError(f"No {source_type.upper()} files found in: {sources}")
        
        print(f"[RAG] Found {len(self.source_files)} {source_type.upper()} file(s)")
        
        # Initialize embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)
        
        # Load and process documents
        self.documents = self._load_documents()
        self.chunks = self._split_documents()
        
        # Create vector store
        self.vectorstore = Chroma.from_documents(
            documents=self.chunks,
            embedding=self.embeddings
        )
        
        print(f"[RAG] Initialized with {len(self.chunks)} chunks")
    
    def _collect_sources(self, sources: Union[str, List[str]]) -> List[str]:
        """Collect all source file paths"""
        paths = []
        
        # Convert single string to list
        if isinstance(sources, str):
            sources = [sources]
        
        for source in sources:
            p = Path(source)
            
            # If directory, glob for files
            if p.is_dir():
                pattern = "*.pdf" if self.source_type == "pdf" else "*.json"
                paths.extend([str(f) for f in p.glob(pattern)])
            # If file exists, add it
            elif p.exists():
                paths.append(str(p))
            # If pattern with wildcards
            elif "*" in source:
                paths.extend(glob.glob(source))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)
        
        return unique_paths
    
    def _load_documents(self) -> List[Document]:
        """Load documents based on source type"""
        if self.source_type == "pdf":
            return self._load_pdfs()
        else:
            return self._load_jsons()
    
    def _load_pdfs(self) -> List[Document]:
        """Load PDF documents with fallback loaders"""
        if not PDF_LOADERS_AVAILABLE:
            raise ImportError(
                "PDF loaders not available. Install with: "
                "pip install pymupdf pypdfium2 pdfplumber"
            )
        
        all_docs = []
        for path in self.source_files:
            docs = self._robust_load_pdf(path)
            print(f"[RAG] Loaded {len(docs)} pages from: {Path(path).name}")
            all_docs.extend(docs)
        
        return all_docs
    
    def _robust_load_pdf(self, path: str) -> List[Document]:
        """Load single PDF with fallback loaders"""
        loaders = [PyMuPDFLoader, PyPDFium2Loader, PDFPlumberLoader]
        
        for loader_cls in loaders:
            try:
                docs = loader_cls(path).load()
                # Add metadata
                for doc in docs:
                    doc.metadata = doc.metadata or {}
                    doc.metadata["source"] = str(path)
                    doc.metadata["source_type"] = self.target_label
                    doc.metadata["filename"] = Path(path).name
                return docs
            except Exception as e:
                continue
        
        raise RuntimeError(f"Failed to load PDF: {path}")
    
    def _load_jsons(self) -> List[Document]:
        """Load JSON documents"""
        all_docs = []
        for path in self.source_files:
            docs = self._load_single_json(path)
            print(f"[RAG] Loaded {len(docs)} items from: {Path(path).name}")
            all_docs.extend(docs)
        
        return all_docs
    
    def _load_single_json(self, path: str) -> List[Document]:
        """Load single JSON file and flatten to documents"""
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        
        # Flatten JSON structure
        flattened = self._flatten_json(data)
        
        docs = []
        for key_path, text, page in flattened:
            if not text or not text.strip():
                continue
            
            metadata = {
                "source": p.name,
                "source_path": str(p),
                "source_type": self.target_label,
                "json_path": key_path,
                "page": page if page is not None else "N/A",
                "filename": p.name
            }
            docs.append(Document(page_content=text, metadata=metadata))
        
        return docs
    
    def _flatten_json(self, obj, prefix=""):
        """Flatten JSON to (path, text, page) tuples"""
        items = []
        
        if isinstance(obj, dict):
            # Try to extract page number from common keys
            page_hint = (
                obj.get("page") or 
                obj.get("page_no") or 
                obj.get("page_num") or 
                obj.get("หน้า")
            )
            
            for k, v in obj.items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, (dict, list)):
                    items.extend(self._flatten_json(v, new_prefix))
                else:
                    text = str(v) if v is not None else ""
                    items.append((new_prefix, text, page_hint))
        
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                new_prefix = f"{prefix}[{i}]"
                if isinstance(v, (dict, list)):
                    items.extend(self._flatten_json(v, new_prefix))
                else:
                    text = str(v) if v is not None else ""
                    items.append((new_prefix, text, None))
        
        else:
            items.append((prefix, str(obj), None))
        
        return items
    
    def _split_documents(self) -> List[Document]:
        """Split documents into chunks"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        return splitter.split_documents(self.documents)
    
    def retrieve(self, query: str, k: int = 3, filter_target: bool = True) -> List[Document]:
        """
        Retrieve relevant documents
        
        Args:
            query: search query
            k: number of results
            filter_target: filter by target_label or not
        
        Returns:
            List of Document objects
        """
        target_filter = {"source_type": self.target_label} if filter_target else None
        
        try:
            if self.use_mmr:
                hits = self.vectorstore.max_marginal_relevance_search(
                    query,
                    k=self.mmr_k,
                    fetch_k=self.mmr_fetch_k,
                    lambda_mult=self.mmr_lambda,
                    filter=target_filter
                )[:k]
            else:
                hits = self.vectorstore.similarity_search(
                    query,
                    k=k,
                    filter=target_filter
                )
        except TypeError:
            # Fallback: search without filter, then post-filter
            if self.use_mmr:
                base = self.vectorstore.max_marginal_relevance_search(
                    query,
                    k=max(k*5, 15),
                    fetch_k=self.mmr_fetch_k,
                    lambda_mult=self.mmr_lambda
                )
            else:
                base = self.vectorstore.similarity_search(query, k=max(k*5, 15))
            
            if filter_target:
                hits = [h for h in base if h.metadata.get("source_type") == self.target_label][:k]
            else:
                hits = base[:k]
        
        # Final fallback if still no hits
        if not hits and filter_target:
            base = self.vectorstore.similarity_search(query, k=max(k*5, 15))
            hits = [h for h in base if h.metadata.get("source_type") == self.target_label][:k]
        
        return hits
    
    def format_hit(self, doc: Document) -> str:
        """Format a single document hit for display"""
        filename = doc.metadata.get("filename", doc.metadata.get("source", "unknown"))
        page = doc.metadata.get("page", "N/A")
        content = doc.page_content.strip()
        return f"- [{filename} | p.{page}] {content}"
    
    def build_context(
        self,
        queries: List[str],
        k: int = 3,
        max_chars: int = 8000,
        filter_target: bool = True
    ) -> str:
        """
        Build context string from multiple queries
        
        Args:
            queries: list of search queries
            k: number of results per query
            max_chars: maximum context length
            filter_target: filter by target_label or not
        
        Returns:
            Formatted context string
        """
        parts = []
        
        for i, query in enumerate(queries, 1):
            hits = self.retrieve(query, k=k, filter_target=filter_target)
            
            if not hits:
                continue
            
            block = f"### Query {i}: {query}\n"
            block += "\n".join(self.format_hit(h) for h in hits)
            parts.append(block)
        
        if not parts:
            return "No results found."
        
        context = "\n\n----\n\n".join(parts)
        
        # Truncate if too long
        if len(context) > max_chars:
            context = context[:max_chars]
        
        return context
    
    def get_citation_format(self) -> str:
        """Get the citation format string for this source"""
        if self.source_files:
            filename = Path(self.source_files[0]).name
            return f"[{filename}, p.X]"
        return "[source, p.X]"


# ============================================
# Helper function for easy integration
# ============================================

def create_rag_tool(
    sources: Union[str, List[str]],
    source_type: str,
    target_label: str,
    seed_queries: List[str],
    **kwargs
) -> tuple[RAGEngine, str]:
    """
    Create RAG engine and build initial context
    
    Returns:
        (rag_engine, context_string)
    
    Example:
        rag, context = create_rag_tool(
            sources="/path/to/docs",
            source_type="pdf",
            target_label="my_docs",
            seed_queries=["query1", "query2"]
        )
    """
    rag = RAGEngine(
        sources=sources,
        source_type=source_type,
        target_label=target_label,
        **kwargs
    )
    
    context = rag.build_context(seed_queries)
    
    return rag, context