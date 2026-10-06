try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

from pypdf import PdfReader
from io import BytesIO
from typing import Any
import time
import os

from app.core.config import settings

class TextExtractor:

    def _validate_file_content(
        self,
        file_content: bytes
    ):
        if not file_content:
            raise ValueError("File content is empty.")

    def _open_pdf(
        self,
        file_content: bytes
    ):
        if HAS_FITZ:
            return ("fitz", fitz.open(stream=file_content, filetype="pdf"))
        else:
            return ("pypdf", PdfReader(BytesIO(file_content)))

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

            model_name = getattr(settings, "AI_MODEL_NAME", "gemini-3.6-flash") or "gemini-3.6-flash"
            client = genai.Client(api_key=api_key)
            
            if engine == "fitz":
                for page in doc:
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    models_to_try = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]


                    extracted = False
                    for m in models_to_try:
                        if extracted:
                            break
                        for attempt in range(3):
                            try:
                                response = client.models.generate_content(
                                    model=m,
                                    contents=[
                                        "Extract all text, tables, dates, and numbers from this document image cleanly and completely:",
                                        genai.types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                                    ]
                                )
                                if response and response.text:
                                    ocr_texts.append(response.text.strip())
                                    extracted = True
                                    break
                            except Exception as exc:
                                print(f"Gemini OCR page error (model={m}, attempt={attempt}): {exc}")
                                time.sleep(1)


            else:
                for page in doc.pages:
                    for img in page.images:
                        img_bytes = img.data
                        try:
                            response = client.models.generate_content(
                                model=model_name,
                                contents=[
                                    "Extract all text, tables, dates, and numbers from this document image cleanly and completely:",
                                    genai.types.Part.from_bytes(data=img_bytes, mime_type=f"image/{img.name.split('.')[-1]}")
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
        file_content: bytes
    ) -> str:
        self._validate_file_content(file_content=file_content)
        doc_tuple = self._open_pdf(file_content=file_content)
        text_list = self._extract_text(doc_tuple=doc_tuple)
        single_string = " ".join(text_list).strip()

        # If vector font extraction returned very little or no text (< 20 chars), use Gemini Vision OCR
        if len(single_string) < 20:
            ocr_text = self._ocr_extract_pdf(doc_tuple=doc_tuple)
            if ocr_text:
                single_string = ocr_text

        if not single_string or len(single_string.strip()) < 3:
            raise ValueError("No text found in document. If this is a scanned PDF image, Gemini API rate limits (429) may have prevented OCR processing. Please upload a searchable PDF or try again later.")

        return single_string