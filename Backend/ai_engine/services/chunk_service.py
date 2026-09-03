from langchain_text_splitters import RecursiveCharacterTextSplitter


class ChunkService:
    
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size = self.CHUNK_SIZE,
            chunk_overlap = self.CHUNK_OVERLAP,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                ""
            ]
        )
    
    def _validate_text(
        self,
        text: str
    ) -> None:
        if not text or not text.strip():
            raise ValueError("Text is empty.")
        
    def chunk_text(
        self,
        text: str
    ) -> list[str]:
        self._validate_text(text=text)
        raw_chunks = self.splitter.split_text(text=text)
        valid_chunks = [
            c.strip() for c in raw_chunks
            if isinstance(c, str) and len(c.strip()) >= 3 and not (c.strip().isdigit() and len(c.strip()) <= 3)
        ]
        return valid_chunks if valid_chunks else [text.strip()]
