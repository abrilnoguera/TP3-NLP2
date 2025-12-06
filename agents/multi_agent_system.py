"""
Multi-Agent System con LangGraph
=================================

Sistema de orquestación que usa LangGraph para coordinar
múltiples agentes de CV basado en la query del usuario.
"""

import os
from typing import TypedDict, List, Dict, Any
from dotenv import load_dotenv

from langgraph.graph import StateGraph, END
from agents.router import QueryRouter
from agents.agent_factory import AgentFactory
from groq import Groq

load_dotenv()


# ============================================
# ESTADO DEL GRAFO
# ============================================

class AgentState(TypedDict):
    """Estado compartido entre nodos del grafo."""
    query: str                          # Pregunta original del usuario
    detected_agents: List[str]          # Agentes detectados por el router
    requires_aggregation: bool          # Si requiere agregar múltiples respuestas
    agent_responses: Dict[str, str]     # Respuestas individuales {nombre: respuesta}
    final_answer: str                   # Respuesta final agregada
    routing_info: Dict[str, Any]        # Info de debugging del routing


# ============================================
# NODOS DEL GRAFO
# ============================================

class MultiAgentSystem:
    """
    Sistema multi-agente que orquesta las consultas usando LangGraph.
    """
    
    def __init__(self, docs_base_dir: str = "docs", default_agent: str = None):
        """
        Inicializa el sistema multi-agente.
        
        Args:
            docs_base_dir: Directorio con los CVs
            default_agent: Agente por defecto
        """
        self.docs_base_dir = docs_base_dir
        self.default_agent = default_agent or os.getenv("DEFAULT_AGENT", "abril")
        
        # Componentes
        self.router = QueryRouter(
            docs_dir=docs_base_dir,
            default_agent=self.default_agent
        )
        self.factory = AgentFactory(docs_base_dir=docs_base_dir)
        
        # Cliente Groq para agregación
        api_key = os.getenv("GROQ_API_KEY")
        self.groq = Groq(api_key=api_key) if api_key else None
        
        # Construir el grafo
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """
        Construye el grafo de estados con LangGraph.
        
        Flujo:
        1. route_node: Analiza la query y detecta agentes
        2. conditional_edge: Decide si es single o multi-agent
        3. single_agent_node: Responde con un solo agente
        4. multi_agent_node: Consulta múltiples agentes
        5. aggregate_node: Agrega respuestas múltiples
        6. END: Finaliza
        """
        # Crear el grafo
        builder = StateGraph(AgentState)
        
        # Agregar nodos
        builder.add_node("route", self.route_node)
        builder.add_node("single_agent", self.single_agent_node)
        builder.add_node("multi_agent", self.multi_agent_node)
        builder.add_node("aggregate", self.aggregate_node)
        
        # Entry point
        builder.set_entry_point("route")
        
        # Conditional edge después del routing
        builder.add_conditional_edges(
            "route",
            self.decide_path,
            {
                "single": "single_agent",
                "multi": "multi_agent"
            }
        )
        
        # Single agent va directo al final
        builder.add_edge("single_agent", END)
        
        # Multi agent va a agregación
        builder.add_edge("multi_agent", "aggregate")
        builder.add_edge("aggregate", END)
        
        return builder.compile()
    
    # ---- NODOS ----
    
    def route_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Nodo que analiza la query y detecta los agentes necesarios.
        """
        query = state["query"]
        routing_info = self.router.get_routing_info(query)
        
        return {
            "detected_agents": routing_info["detected_agents"],
            "requires_aggregation": routing_info["requires_aggregation"],
            "routing_info": routing_info
        }
    
    def single_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Nodo que maneja consultas de un solo agente.
        """
        query = state["query"]
        agent_name = state["detected_agents"][0]
        
        try:
            agent = self.factory.get_agent(agent_name)
            answer = agent.answer(query)
            
            return {
                "agent_responses": {agent_name: answer},
                "final_answer": answer
            }
        except Exception as e:
            error_msg = f"Error al consultar el agente '{agent_name}': {str(e)}"
            return {
                "agent_responses": {agent_name: error_msg},
                "final_answer": error_msg
            }
    
    def multi_agent_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Nodo que consulta múltiples agentes.
        """
        query = state["query"]
        agent_names = state["detected_agents"]
        
        responses = {}
        
        for agent_name in agent_names:
            try:
                agent = self.factory.get_agent(agent_name)
                answer = agent.answer(query)
                responses[agent_name] = answer
            except Exception as e:
                responses[agent_name] = f"Error: {str(e)}"
        
        return {"agent_responses": responses}
    
    def aggregate_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Nodo que agrega respuestas de múltiples agentes.
        """
        query = state["query"]
        responses = state["agent_responses"]
        
        # Construir el prompt de agregación
        responses_text = "\n\n".join([
            f"**Respuesta de {nombre.title()}:**\n{respuesta}"
            for nombre, respuesta in responses.items()
        ])
        
        aggregation_prompt = f"""
Tenés que combinar las siguientes respuestas individuales sobre diferentes personas 
en una respuesta coherente y profesional que responda a la pregunta original.

PREGUNTA ORIGINAL:
{query}

RESPUESTAS INDIVIDUALES:
{responses_text}

INSTRUCCIONES:
- Combina la información de manera clara y estructurada
- Si la pregunta compara personas, haz una comparación explícita
- Si la pregunta es general sobre el equipo, presenta la info de cada uno
- Mantén un tono profesional y natural
- No repitas información innecesariamente
        """.strip()
        
        try:
            if self.groq:
                resp = self.groq.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Sos un asistente que combina información de múltiples CVs."},
                        {"role": "user", "content": aggregation_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )
                final_answer = resp.choices[0].message.content.strip()
            else:
                # Fallback sin LLM
                final_answer = responses_text
        except Exception as e:
            final_answer = f"Error en agregación: {str(e)}\n\n{responses_text}"
        
        return {"final_answer": final_answer}
    
    # ---- CONDITIONAL EDGE ----
    
    def decide_path(self, state: AgentState) -> str:
        """
        Conditional edge que decide el camino según el número de agentes.
        """
        if state["requires_aggregation"]:
            return "multi"
        else:
            return "single"
    
    # ---- API PÚBLICA ----
    
    def query(self, question: str) -> str:
        """
        Procesa una pregunta y retorna la respuesta final.
        
        Args:
            question: Pregunta del usuario
            
        Returns:
            Respuesta final
        """
        initial_state = {
            "query": question,
            "detected_agents": [],
            "requires_aggregation": False,
            "agent_responses": {},
            "final_answer": "",
            "routing_info": {}
        }
        
        result = self.graph.invoke(initial_state)
        return result["final_answer"]
    
    def query_with_details(self, question: str) -> Dict[str, Any]:
        """
        Procesa una pregunta y retorna detalles completos.
        
        Args:
            question: Pregunta del usuario
            
        Returns:
            Estado completo con todos los detalles
        """
        initial_state = {
            "query": question,
            "detected_agents": [],
            "requires_aggregation": False,
            "agent_responses": {},
            "final_answer": "",
            "routing_info": {}
        }
        
        return self.graph.invoke(initial_state)
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Información sobre el sistema para debugging.
        """
        return {
            "default_agent": self.default_agent,
            "available_agents": self.factory.list_available_persons(),
            "router_info": {
                "available_agents": list(self.router.available_agents),
                "default": self.router.default_agent
            },
            "factory_info": self.factory.get_info()
        }


# ============================================
# FUNCIÓN HELPER
# ============================================

_global_system = None


def get_multi_agent_system(
    docs_base_dir: str = "docs",
    default_agent: str = None,
    force_new: bool = False
) -> MultiAgentSystem:
    """
    Obtiene la instancia global del sistema multi-agente (singleton).
    
    Args:
        docs_base_dir: Directorio de documentos
        default_agent: Agente por defecto
        force_new: Forzar creación de nueva instancia
        
    Returns:
        Instancia de MultiAgentSystem
    """
    global _global_system
    
    if _global_system is None or force_new:
        _global_system = MultiAgentSystem(
            docs_base_dir=docs_base_dir,
            default_agent=default_agent
        )
    
    return _global_system


# ============================================
# MAIN - TESTS
# ============================================

if __name__ == "__main__":
    print("=== Test del Multi-Agent System ===\n")
    
    system = MultiAgentSystem(docs_base_dir="docs", default_agent="abril")
    
    print("Info del sistema:")
    print(system.get_system_info())
    print("\n" + "="*60 + "\n")
    
    # Test queries
    test_queries = [
        "¿Qué experiencia tiene Abril en Machine Learning?",
        "¿Cuáles son las skills del equipo?",
        "Compara la experiencia de Abril con otros miembros",
    ]
    
    for query in test_queries:
        print(f"Query: {query}")
        print("-" * 60)
        
        result = system.query_with_details(query)
        
        print(f"Agentes detectados: {result['detected_agents']}")
        print(f"Requiere agregación: {result['requires_aggregation']}")
        print(f"\nRespuesta final:\n{result['final_answer']}")
        print("\n" + "="*60 + "\n")
