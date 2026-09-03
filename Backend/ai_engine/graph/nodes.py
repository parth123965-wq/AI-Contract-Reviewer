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
        
    def extract_text_node(self,state: ContractState) -> ContractState:
        state['extracted_text'] = self.text_extractor.extract_text(file_path=state['file_path'])
        return state
    
    def chunk_text_node(self,state: ContractState) -> ContractState:
        state['chunks'] = self.chunk_service.chunk_text(state['extracted_text'])
        return state
    
    def embedding_node(self,state: ContractState) -> ContractState:
        state['embeddings'] = self.embedding_service.create_embeddings(chunks=state['chunks'])
        if state['embeddings']:
            state['query_embedding'] = state['embeddings'][0]
        else:
            state['query_embedding'] = []
        return state
    
    def store_vector_node(self,state: ContractState) -> ContractState:
        self.vector_store.store_embeddings(
            contract_id=state['contract_id'],
            user_id=state['user_id'],
            chunks=state['chunks'],
            embeddings=state['embeddings'],
            version=state['analysis_version']
        )
        return state
    
    def retrieve_context_node(self,state: ContractState) -> ContractState:
        retrieved = self.vector_store.search(
            contract_id=state['contract_id'],
            user_id=state['user_id'],
            query_embedding=state['query_embedding'],
        )
        if not retrieved and state.get('chunks'):
            retrieved = state['chunks'][:5]
        state['retrieved_chunks'] = retrieved
        return state
    
    def prompt_node(self,state: ContractState) -> ContractState:
        prompt = self.prompt_service.build_prompt(
            request=state["retrieved_chunks"]
        )
        state["prompt"] = prompt
        return state
    
    def llm_node(self,state: ContractState) -> ContractState:
        response = self.llm_service.generate(
            prompt=state["prompt"]
        )
        state["llm_response"] = response
        return state
    
    def parser_node(self,state: ContractState) -> ContractState:
        result = self.parser_service.process_json(
            jsons=state["llm_response"]
        )

        state["analysis_result"] = result
        return state
    
    def save_analysis_node(self,state: ContractState) -> ContractState:
        self.analysis_service.save_analysis(
            db=state["db"],
            contract_id=state["contract_id"],
            result=state["analysis_result"],
            model_name=settings.AI_MODEL_NAME,
            processing_time_ms=state.get("processing_time_ms", 0),
            analysis_version=state.get("analysis_version", 1)
        )

        return state