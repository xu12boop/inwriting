import io
from pypdf import PdfReader
import docx

def extract_text_from_pdf(file_content: bytes) -> str:
    text = ""
    try:
        reader = PdfReader(io.BytesIO(file_content))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"PDF解析失败: {e}")
    return text

def extract_text_from_docx(file_content: bytes) -> str:
    text = ""
    try:
        doc = docx.Document(io.BytesIO(file_content))
        for para in doc.paragraphs:
            if para.text:
                text += para.text + "\n"
    except Exception as e:
        print(f"Word解析失败: {e}")
    return text