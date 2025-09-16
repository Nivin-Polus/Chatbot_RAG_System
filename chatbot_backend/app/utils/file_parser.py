# app/utils/file_parser.py

from io import BytesIO
from typing import List
from math import ceil

# PDF
from PyPDF2 import PdfReader

# DOCX
from docx import Document

# PPTX
from pptx import Presentation

# Excel
import pandas as pd

# Chunk size (number of words per chunk)
CHUNK_SIZE = 200


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))
    return chunks


def parse_file(filename: str, content: bytes, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """
    Extract text from file and split into chunks.
    Supports PDF, DOCX, PPTX, XLS/XLSX, TXT.
    """
    ext = filename.split('.')[-1].lower()
    text = ""

    try:
        if ext == "pdf":
            reader = PdfReader(BytesIO(content))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        elif ext == "docx":
            doc = Document(BytesIO(content))
            for para in doc.paragraphs:
                if para.text:
                    text += para.text + "\n"

        elif ext == "pptx":
            prs = Presentation(BytesIO(content))
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text += shape.text + "\n"

        elif ext in ["xls", "xlsx"]:
            xls = pd.ExcelFile(BytesIO(content))
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                for row in df.itertuples(index=False):
                    row_text = " ".join([str(cell) for cell in row if pd.notna(cell)])
                    if row_text.strip():
                        text += row_text + "\n"

        elif ext == "txt":
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1")

        else:
            raise ValueError(f"Unsupported file type: {ext}")

    except Exception as e:
        raise ValueError(f"Error parsing file {filename}: {str(e)}")

    # Split text into chunks
    return chunk_text(text, chunk_size)
