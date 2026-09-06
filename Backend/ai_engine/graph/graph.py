try:
    from langgraph.graph import END , START , StateGraph
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    END, START, StateGraph = "END", "START", None

import asyncio
from ai_engine.graph.state import ContractState
from ai_engine.graph.nodes import ContractNodes 


class FallbackCompiledGraph:
    def __init__(self, node: ContractNodes):
        self.node = node

    def invoke(self, state: ContractState) -> ContractState:
        state = self.node.extract_text_node(state)
        state = self.node.chunk_text_node(state)
        state = self.node.embedding_node(state)
        state = self.node.store_vector_node(state)
        state = self.node.retrieve_context_node(state)
        state = self.node.prompt_node(state)
        state = self.node.llm_node(state)
        state = self.node.parser_node(state)
        if state.get("db") is not None and not (state.get("error") or state.get("status") == "FAILED"):
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(self.node.save_analysis_node(state))
                else:
                    asyncio.run(self.node.save_analysis_node(state))
            except Exception:
                pass
        return state


class ContractGraph:
    
    def __init__(self):
        self.node = ContractNodes()
        if HAS_LANGGRAPH:
            self.graph = StateGraph(ContractState)
        else:
            self.graph = None
        
    def add_nodes(self):
        if not self.graph:
            return
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
        if not self.graph:
            return
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
        if not HAS_LANGGRAPH or self.graph is None:
            return FallbackCompiledGraph(self.node)
        self.add_nodes()
        self.add_edges()
        return self.graph.compile()