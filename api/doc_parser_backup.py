import io
import PyPDF2
import docx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def parse_pdf(file_bytes: bytes) -> str:
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error parsing PDF: {e}")
        return f"[Error parsing PDF: {e}]"

def parse_docx(file_bytes: bytes) -> str:
    try:
        doc = docx.Document(io.BytesIO(file_bytes))
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error parsing DOCX: {e}")
        return f"[Error parsing DOCX: {e}]"

def parse_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode('utf-8', errors='ignore').strip()
    except Exception as e:
        logger.error(f"Error parsing TXT: {e}")
        return f"[Error parsing TXT: {e}]"

def process_document(filename: str, file_bytes: bytes) -> Optional[str]:
    ext = filename.split('.')[-1].lower()
    if ext == 'pdf':
        return parse_pdf(file_bytes)
    elif ext in ['doc', 'docx']:
        return parse_docx(file_bytes)
    elif ext in ['txt', 'md', 'py', 'js', 'html', 'css']:
        return parse_txt(file_bytes)
    else:
        logger.warning(f"Unsupported file extension: {ext}")
        return None
