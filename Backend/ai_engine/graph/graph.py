from langgraph.graph import END , START , StateGraph
from ai_engine.graph.state import ContractState
from ai_engine.graph.nodes import ContractNodes 


class ContractGraph:
    
    
    def __init__(self):
        self.graph = StateGraph(ContractState)
        self.node = ContractNodes()
        
    def add_nodes(self):
        self.graph.add_node("extract_node",self.node.extract_text_node)
        self.graph.add_node("chunk_node",self.node.chunk_text_node)
        self.graph.add_node("embedding_node",self.node.embedding_node)
        self.graph.add_node("vector_store_node",self.node.store_vector_node)
        self.graph.add_node("retrieve_context_node",self.node.retrieve_context_node)
        self.graph.add_node("prompt_node",self.node.prompt_node)
        self.graph.add_node("llm_node",self.node.llm_node)
        self.graph.add_node("parser_node",self.node.parser_node)
        self.graph.add_node("save_analysis_node",self.node.save_analysis_node)
        
    def add_edges(self):
        self.graph.add_edge(START,"extract_node")
        self.graph.add_edge("extract_node","chunk_node")
        self.graph.add_edge("chunk_node","embedding_node")
        self.graph.add_edge("embedding_node","vector_store_node")
        self.graph.add_edge("vector_store_node","retrieve_context_node")
        self.graph.add_edge("retrieve_context_node","prompt_node")
        self.graph.add_edge("prompt_node","llm_node")
        self.graph.add_edge("llm_node","parser_node")
        self.graph.add_edge("parser_node","save_analysis_node")
        self.graph.add_edge("save_analysis_node",END)
        
    def compile_graph(self):
        self.add_nodes()
        self.add_edges()
        return self.graph.compile()