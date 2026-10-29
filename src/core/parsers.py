import hashlib
import logging
from typing import List, Dict, Any, Optional, Generator
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod
import mimetypes

logger = logging.getLogger(__name__)

@dataclass
class ParsedDocument:
    content: str
    metadata: Dict[str, Any]
    source_type: str
    source_uri: str

class DocumentParser(ABC):
    @abstractmethod
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        pass

    @abstractmethod
    def parse(self, file_path: str, source_uri: str) -> ParsedDocument:
        pass

class TextParser(DocumentParser):
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in ['.txt', '.md', '.markdown', '.rst', '.csv', '.json', '.jsonl', '.yaml', '.yml', '.toml', '.xml', '.py', '.js', '.ts', '.html', '.htm', '.css', '.sql', '.sh', '.rs', '.go', '.java', '.cpp', '.c', '.h', '.rb', '.php', '.swift', '.kt', '.scala', '.r', '.m', '.jl', '.lua', '.pl', '.bat', '.ps1', '.ini', '.cfg', '.conf']

    def parse(self, file_path: str, source_uri: str) -> ParsedDocument:
        ext = Path(file_path).suffix.lower()
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return ParsedDocument(
            content=content,
            metadata={"extension": ext},
            source_type="text",
            source_uri=source_uri
        )

class PDFParser(DocumentParser):
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return Path(file_path).suffix.lower() == '.pdf'

    def parse(self, file_path: str, source_uri: str) -> ParsedDocument:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                content = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
                metadata = {"pages": len(pdf.pages), "title": pdf.metadata.get("Title") if pdf.metadata else None}
        except ImportError:
            # Fallback to pypdf
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            content = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            metadata = {"pages": len(reader.pages)}
        return ParsedDocument(content=content, metadata=metadata, source_type="pdf", source_uri=source_uri)

class DocxParser(DocumentParser):
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return Path(file_path).suffix.lower() in ['.docx', '.doc']

    def parse(self, file_path: str, source_uri: str) -> ParsedDocument:
        from docx import Document
        doc = Document(file_path)
        content = "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
        metadata = {"paragraphs": len(doc.paragraphs)}
        return ParsedDocument(content=content, metadata=metadata, source_type="docx", source_uri=source_uri)

class HTMLParser(DocumentParser):
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return Path(file_path).suffix.lower() in ['.html', '.htm', '.xhtml']

    def parse(self, file_path: str, source_uri: str) -> ParsedDocument:
        from bs4 import BeautifulSoup
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
        # Extract main content, remove scripts/styles
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
        content = soup.get_text(separator='\n', strip=True)
        metadata = {"title": soup.title.string if soup.title else None}
        return ParsedDocument(content=content, metadata=metadata, source_type="html", source_uri=source_uri)

class CSVParser(DocumentParser):
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return Path(file_path).suffix.lower() == '.csv'

    def parse(self, file_path: str, source_uri: str) -> ParsedDocument:
        import csv
        rows = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        content = "\n".join(json.dumps(r) for r in rows)
        metadata = {"row_count": len(rows)}
        return ParsedDocument(content=content, metadata=metadata, source_type="csv", source_uri=source_uri)

class JSONParser(DocumentParser):
    def can_parse(self, file_path: str, mime_type: str) -> bool:
        return Path(file_path).suffix.lower() in ['.json', '.jsonl']

    def parse(self, file_path: str, source_uri: str) -> ParsedDocument:
        import json
        content_lines = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            if file_path.endswith('.jsonl'):
                for line in f:
                    if line.strip():
                        content_lines.append(json.dumps(json.loads(line)))
            else:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        content_lines.append(json.dumps(item))
                else:
                    content_lines.append(json.dumps(data))
        content = "\n".join(content_lines)
        metadata = {"records": len(content_lines)}
        return ParsedDocument(content=content, metadata=metadata, source_type="json", source_uri=source_uri)

import json

class ParserRegistry:
    def __init__(self):
        self.parsers: List[DocumentParser] = [
            TextParser(),
            PDFParser(),
            DocxParser(),
            HTMLParser(),
            CSVParser(),
            JSONParser(),
        ]

    def register(self, parser: DocumentParser):
        self.parsers.append(parser)

    def get_parser(self, file_path: str, mime_type: str = "") -> Optional[DocumentParser]:
        for parser in self.parsers:
            if parser.can_parse(file_path, mime_type):
                return parser
        return None

    def parse(self, file_path: str, source_uri: str = None) -> ParsedDocument:
        parser = self.get_parser(file_path, mimetypes.guess_type(file_path)[0] or "")
        if not parser:
            raise ValueError(f"No parser available for {file_path}")
        return parser.parse(file_path, source_uri or f"file://{file_path}")

# Chunking Strategies

class Chunker(ABC):
    @abstractmethod
    def chunk(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        pass

class RecursiveChunker(Chunker):
    """Recursive character-based chunking with overlap."""
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""]

    def chunk(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not content.strip():
            return []
        return self._split_text(content, 0, metadata)

    def _split_text(self, text: str, start_offset: int, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if len(text) <= self.chunk_size:
            return [{
                "content": text,
                "start_offset": start_offset,
                "end_offset": start_offset + len(text),
                "metadata": metadata or {},
            }]

        # Find best separator
        for sep in self.separators:
            if sep in text:
                parts = text.split(sep)
                chunks = []
                current = ""
                current_start = start_offset
                for i, part in enumerate(parts):
                    if current and len(current) + len(sep) + len(part) > self.chunk_size:
                        chunks.append({
                            "content": current,
                            "start_offset": current_start,
                            "end_offset": current_start + len(current),
                            "metadata": metadata or {},
                        })
                        # Overlap: keep last part of current
                        overlap_text = current[-self.chunk_overlap:] if self.chunk_overlap < len(current) else current
                        current = overlap_text + sep + part
                        current_start = current_start + len(current) - len(current) + len(overlap_text)
                    else:
                        if current:
                            current += sep + part
                        else:
                            current = part
                if current:
                    chunks.append({
                        "content": current,
                        "start_offset": current_start,
                        "end_offset": current_start + len(current),
                        "metadata": metadata or {},
                    })
                return chunks

        # Fallback: force split
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            chunks.append({
                "content": chunk,
                "start_offset": start_offset + i,
                "end_offset": start_offset + i + len(chunk),
                "metadata": metadata or {},
            })
        return chunks

class SentenceChunker(Chunker):
    """Sentence-aware chunking using simple heuristic."""
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not content.strip():
            return []
        sentences = self._split_sentences(content)
        chunks = []
        current = ""
        current_start = 0
        char_offset = 0
        
        for sent in sentences:
            sent_len = len(sent)
            if len(current) + sent_len > self.chunk_size and current:
                chunks.append({
                    "content": current.strip(),
                    "start_offset": current_start,
                    "end_offset": current_start + len(current),
                    "metadata": metadata or {},
                })
                # Overlap: keep last sentence or part
                overlap_start = max(0, len(current) - self.chunk_overlap)
                current = current[overlap_start:] + sent
                current_start = char_offset - len(current) + len(current[overlap_start:])
            else:
                if current:
                    current += " " + sent
                else:
                    current = sent
                    current_start = char_offset
            char_offset += sent_len + 1
        
        if current:
            chunks.append({
                "content": current.strip(),
                "start_offset": current_start,
                "end_offset": current_start + len(current),
                "metadata": metadata or {},
            })
        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        import re
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

class CodeChunker(Chunker):
    """Code-aware chunking preserving function/class boundaries."""
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # For now, use recursive chunking with larger size
        recursive = RecursiveChunker(chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
        return recursive.chunk(content, metadata)


class ChunkerRegistry:
    def __init__(self):
        self.chunkers = {
            "recursive": RecursiveChunker,
            "sentence": SentenceChunker,
            "code": CodeChunker,
        }

    def get_chunker(self, strategy: str, chunk_size: int = 500, chunk_overlap: int = 50) -> Chunker:
        cls = self.chunkers.get(strategy, RecursiveChunker)
        return cls(chunk_size=chunk_size, chunk_overlap=chunk_overlap)