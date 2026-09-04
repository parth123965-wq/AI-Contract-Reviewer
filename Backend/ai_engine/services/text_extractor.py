try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

from pypdf import PdfReader
from typing import Any
import os
from app.core.config import settings

class TextExtractor:

    def _validate_file(
        self,
        file_path: str
    ):
        file_exists = Path(file_path)
        if not file_exists.exists():
            raise FileNotFoundError("File is not found.")

    def _open_pdf(
        self,
        file_path: str
    ):
        pdf_path = Path(file_path)
        if HAS_FITZ:
            return ("fitz", fitz.open(pdf_path))
        else:
            return ("pypdf", PdfReader(pdf_path))

    def _extract_text(
        self,
        doc_tuple: Any
    ) -> list[str]:
        engine, doc = doc_tuple
        text_list = []
        if engine == "fitz":
            for page_number, page in enumerate(doc, start=1):
                text = page.get_text()
                if text and len(text.strip()) > 5:
                    text_list.append(text.strip())
        else:
            for page in doc.pages:
                text = page.extract_text()
                if text and len(text.strip()) > 5:
                    text_list.append(text.strip())
        return text_list

    def _ocr_extract_pdf(self, doc_tuple: Any) -> str:
        """Extracts text from scanned/image-based PDFs using Gemini Vision OCR."""
        engine, doc = doc_tuple
        if engine != "fitz":
            return ""
        ocr_texts = []
        try:
            from google import genai
            api_key = (
                getattr(settings, "GOOGLE_API_KEY", None)
                or getattr(settings, "GEMINI_API_KEY", None)
                or os.getenv("GOOGLE_API_KEY")
                or os.getenv("GEMINI_API_KEY")
            )
            if not api_key:
                return ""

            client = genai.Client(api_key=api_key)
            for page in doc:
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")
                try:
                    response = client.models.generate_content(
                        model="gemini-flash-latest",
                        contents=[
                            "Extract all text, tables, dates, and numbers from this document image cleanly and completely:",
                            genai.types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                        ]
                    )
                    if response and response.text:
                        ocr_texts.append(response.text.strip())
                except Exception as exc:
                    print(f"Gemini OCR page error: {exc}")
        except Exception as exc:
            print(f"Gemini Vision OCR setup note: {exc}")

        return "\n\n".join(ocr_texts)

    def extract_text(
        self,
        file_path: str
    ) -> str:
        self._validate_file(file_path=file_path)
        doc_tuple = self._open_pdf(file_path=file_path)
        text_list = self._extract_text(doc_tuple=doc_tuple)
        single_string = " ".join(text_list).strip()

        # If vector font extraction returned very little or no text (< 20 chars), use Gemini Vision OCR
        if len(single_string) < 20:
            ocr_text = self._ocr_extract_pdf(doc_tuple=doc_tuple)
            if ocr_text:
                single_string = ocr_text

        if not single_string or len(single_string.strip()) < 3:
            raise ValueError("No meaningful text found in document.")

        return single_string