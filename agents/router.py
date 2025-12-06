"""
Router - Conditional Edge Decision Maker
==========================================

Analiza la query del usuario y determina qué agente(s) debe(n) responder.
Usa expresiones regulares para detectar nombres de personas.
"""

import re
import os
from typing import List, Set
from pathlib import Path


class QueryRouter:
    """
    Router que analiza queries y decide qué agente(s) invocar.
    Usa regex para detectar nombres en la consulta.
    """
    
    def __init__(self, docs_dir: str = "docs", default_agent: str = None):
        """
        Inicializa el router.
        
        Args:
            docs_dir: Directorio donde están las carpetas de cada persona
            default_agent: Agente por defecto cuando no se detecta ningún nombre
        """
        self.docs_dir = Path(docs_dir)
        self.default_agent = default_agent or os.getenv("DEFAULT_AGENT", "abril")
        
        # Cargar nombres de personas disponibles desde las carpetas
        self.available_agents = self._discover_agents()
        
        # Crear patterns de regex para cada persona
        self.name_patterns = self._build_patterns()
    
    def _discover_agents(self) -> Set[str]:
        """
        Descubre automáticamente los agentes disponibles 
        buscando carpetas en docs/
        """
        agents = set()
        
        if not self.docs_dir.exists():
            return {self.default_agent}
        
        for item in self.docs_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                agents.add(item.name.lower())
        
        return agents if agents else {self.default_agent}
    
    def _build_patterns(self) -> dict:
        """
        Construye patrones de regex para detectar cada nombre.
        """
        patterns = {}
        
        for agent_name in self.available_agents:
            # Patrón que detecta el nombre completo o variaciones
            # Case insensitive, con word boundaries
            pattern = re.compile(
                r'\b' + re.escape(agent_name) + r'\b',
                re.IGNORECASE
            )
            patterns[agent_name] = pattern
        
        return patterns
    
    def route(self, query: str) -> List[str]:
        """
        Analiza la query y determina qué agente(s) debe(n) responder.
        
        Args:
            query: Pregunta del usuario
            
        Returns:
            Lista de nombres de agentes que deben responder
        """
        detected_agents = []
        
        # Buscar cada nombre en la query
        for agent_name, pattern in self.name_patterns.items():
            if pattern.search(query):
                detected_agents.append(agent_name)
        
        # Si no se detectó ninguno, usar el agente default
        if not detected_agents:
            detected_agents = [self.default_agent]
        
        return detected_agents
    
    def should_aggregate(self, agents: List[str]) -> bool:
        """
        Determina si se necesita agregar respuestas de múltiples agentes.
        
        Args:
            agents: Lista de agentes detectados
            
        Returns:
            True si hay más de un agente
        """
        return len(agents) > 1
    
    def get_routing_info(self, query: str) -> dict:
        """
        Obtiene información completa del routing para debugging.
        
        Args:
            query: Pregunta del usuario
            
        Returns:
            Diccionario con información del routing
        """
        agents = self.route(query)
        
        return {
            "query": query,
            "detected_agents": agents,
            "requires_aggregation": self.should_aggregate(agents),
            "default_used": agents == [self.default_agent] and not any(
                pattern.search(query) for pattern in self.name_patterns.values()
            ),
            "available_agents": list(self.available_agents)
        }


# Función helper para uso rápido
def route_query(query: str, docs_dir: str = "docs", default_agent: str = None) -> List[str]:
    """
    Función helper para routing rápido sin instanciar la clase.
    
    Args:
        query: Pregunta del usuario
        docs_dir: Directorio de documentos
        default_agent: Agente por defecto
        
    Returns:
        Lista de agentes que deben responder
    """
    router = QueryRouter(docs_dir=docs_dir, default_agent=default_agent)
    return router.route(query)


if __name__ == "__main__":
    # Tests de ejemplo
    router = QueryRouter(docs_dir="docs", default_agent="abril")
    
    print("=== Test del Router ===\n")
    
    test_queries = [
        "¿Qué experiencia tiene Abril en Machine Learning?",
        "¿Cuál es el background de juan?",
        "Compara la experiencia de Abril y María en Python",
        "¿Qué skills tiene el equipo?",  # Sin nombre específico
        "Háblame sobre carlos y sus proyectos",
    ]
    
    for query in test_queries:
        info = router.get_routing_info(query)
        print(f"Query: {query}")
        print(f"  → Agentes: {info['detected_agents']}")
        print(f"  → Default usado: {info['default_used']}")
        print(f"  → Requiere agregación: {info['requires_aggregation']}")
        print()
