from ai_engine.services.chunk_service import ChunkService
from ai_engine.services.embedding_service import EmbeddingService
from ai_engine.services.text_extractor import TextExtractor
from ai_engine.services.vector_store_service import VectorStoreService
from ai_engine.graph.state import ContractState
from ai_engine.services.prompt_service import PromptService
from ai_engine.services.llm_service import LLMService
from ai_engine.services.parser_service import ParserService
from ai_engine.services.save_analysis import AnalysisService
from app.core.config import settings
from app.models.contract import ContractStatus
from ai_engine.logger import get_ai_logger

logger = get_ai_logger("graph.nodes")

class ContractNodes:
    
    def __init__(self):
        self.text_extractor = TextExtractor()
        self.chunk_service = ChunkService()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()
        self.prompt_service = PromptService()
        self.llm_service = LLMService()
        self.parser_service = ParserService()
        self.analysis_service = AnalysisService()

    def _should_skip(self, state: ContractState) -> bool:
        return bool(state.get("error") or state.get("status") == ContractStatus.FAILED)
        
    def extract_text_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            state['extracted_text'] = self.text_extractor.extract_text(
                file_content=state['file_content']
            )
        except Exception as exc:
            logger.error(f"Error in extract_text_node: {exc}", exc_info=True)
            state['error'] = str(exc)
            state['status'] = ContractStatus.FAILED
        return state
    
    def chunk_text_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            state['chunks'] = self.chunk_service.chunk_text(state.get('extracted_text', ''))
        except Exception as exc:
            logger.error(f"Error in chunk_text_node: {exc}", exc_info=True)
            state['error'] = str(exc)
            state['status'] = ContractStatus.FAILED
        return state
    
    def embedding_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            state['embeddings'] = self.embedding_service.create_embeddings(chunks=state.get('chunks', []))
            if state['embeddings']:
                state['query_embedding'] = state['embeddings'][0]
            else:
                state['query_embedding'] = []
        except Exception as exc:
            logger.error(f"Error in embedding_node: {exc}", exc_info=True)
            state['error'] = str(exc)
            state['status'] = ContractStatus.FAILED
        return state
    
    def store_vector_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            self.vector_store.store_embeddings(
                contract_id=state['contract_id'],
                user_id=state['user_id'],
                chunks=state.get('chunks', []),
                embeddings=state.get('embeddings', []),
                version=state.get('analysis_version', 1)
            )
        except Exception as exc:
            logger.error(f"Error in store_vector_node: {exc}", exc_info=True)
            state['error'] = str(exc)
            state['status'] = ContractStatus.FAILED
        return state
    
    def retrieve_context_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            # Bug Fix: Do not use the first chunk's embedding to filter chunks for general analysis.
            # We want to analyze the entire document context, so we pass all chunks to the prompt.
            state['retrieved_chunks'] = state.get('chunks', [])
        except Exception as exc:
            logger.error(f"Error in retrieve_context_node: {exc}", exc_info=True)
            state['error'] = str(exc)
            state['status'] = ContractStatus.FAILED
        return state
    
    def prompt_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            prompt = self.prompt_service.build_prompt(
                request=state.get("retrieved_chunks", [])
            )
            state["prompt"] = prompt
        except Exception as exc:
            logger.error(f"Error in prompt_node: {exc}", exc_info=True)
            state["error"] = str(exc)
            state["status"] = ContractStatus.FAILED
        return state
    
    def llm_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            response = self.llm_service.generate(
                prompt=state.get("prompt", "")
            )
            state["llm_response"] = response
        except Exception as exc:
            logger.error(f"Error in llm_node: {exc}", exc_info=True)
            state["error"] = str(exc)
            state["status"] = ContractStatus.FAILED
        return state
    
    def parser_node(self, state: ContractState) -> ContractState:
        if self._should_skip(state):
            return state
        try:
            result = self.parser_service.process_json(
                jsons=state.get("llm_response", "")
            )
            state["analysis_result"] = result
        except Exception as exc:
            logger.error(f"Error in parser_node: {exc}", exc_info=True)
            state["error"] = str(exc)
            state["status"] = ContractStatus.FAILED
        return state
    
    def save_analysis_node(self, state: ContractState) -> ContractState:
        # Bug Fix: Saving is now awaited safely in ai_analysis_service.py to prevent 
        # the AsyncSession from closing before the background task completes.
        return state