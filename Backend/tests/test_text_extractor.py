import pymupdf

from ai_engine.services.text_extractor import TextExtractor


def test_text_extractor_reads_pdf_bytes_without_a_local_file():
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Contract text loaded directly from Supabase storage.")
    file_content = document.tobytes()
    document.close()

    extracted_text = TextExtractor().extract_text(file_content=file_content)

    assert "loaded directly from Supabase storage" in extracted_text
