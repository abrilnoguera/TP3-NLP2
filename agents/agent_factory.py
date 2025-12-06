"""
Agent Factory - Fábrica de Agentes
====================================

Crea y gestiona instancias de agentes dinámicamente.
"""

from typing import Dict, List
from pathlib import Path
from agents.cv_agent import CVAgent


class AgentFactory:
    """
    Fábrica que crea y cachea agentes para cada persona del equipo.
    """
    
    def __init__(self, docs_base_dir: str = "docs"):
        """
        Inicializa la fábrica.
        
        Args:
            docs_base_dir: Directorio base con las carpetas de CVs
        """
        self.docs_base_dir = docs_base_dir
        self._agents_cache: Dict[str, CVAgent] = {}
        self.available_persons = self._discover_persons()
    
    def _discover_persons(self) -> List[str]:
        """
        Descubre automáticamente las personas disponibles
        buscando carpetas en docs/
        """
        docs_path = Path(self.docs_base_dir)
        
        if not docs_path.exists():
            return []
        
        persons = []
        for item in docs_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                persons.append(item.name.lower())
        
        return sorted(persons)
    
    def get_agent(self, person_name: str) -> CVAgent:
        """
        Obtiene (o crea) un agente para una persona específica.
        Los agentes se cachean para no recrearlos.
        
        Args:
            person_name: Nombre de la persona
            
        Returns:
            Instancia de CVAgent
            
        Raises:
            ValueError: Si la persona no existe
        """
        person_name = person_name.lower()
        
        # Validar que existe
        if person_name not in self.available_persons:
            raise ValueError(
                f"Persona '{person_name}' no encontrada. "
                f"Disponibles: {', '.join(self.available_persons)}"
            )
        
        # Retornar del cache si ya existe
        if person_name in self._agents_cache:
            return self._agents_cache[person_name]
        
        # Crear nuevo agente y cachear
        agent = CVAgent(person_name, docs_base_dir=self.docs_base_dir)
        self._agents_cache[person_name] = agent
        
        return agent
    
    def get_multiple_agents(self, person_names: List[str]) -> Dict[str, CVAgent]:
        """
        Obtiene múltiples agentes a la vez.
        
        Args:
            person_names: Lista de nombres de personas
            
        Returns:
            Diccionario {nombre: agente}
        """
        return {name: self.get_agent(name) for name in person_names}
    
    def get_all_agents(self) -> Dict[str, CVAgent]:
        """
        Obtiene agentes para todas las personas disponibles.
        
        Returns:
            Diccionario {nombre: agente}
        """
        return self.get_multiple_agents(self.available_persons)
    
    def list_available_persons(self) -> List[str]:
        """
        Lista todas las personas disponibles.
        
        Returns:
            Lista de nombres
        """
        return self.available_persons.copy()
    
    def clear_cache(self):
        """Limpia el cache de agentes."""
        self._agents_cache.clear()
    
    def get_info(self) -> dict:
        """
        Información sobre el factory para debugging.
        
        Returns:
            Dict con información
        """
        return {
            "docs_base_dir": self.docs_base_dir,
            "available_persons": self.available_persons,
            "cached_agents": list(self._agents_cache.keys()),
            "total_persons": len(self.available_persons),
            "total_cached": len(self._agents_cache)
        }


# Instancia global singleton (opcional)
_global_factory = None


def get_factory(docs_base_dir: str = "docs") -> AgentFactory:
    """
    Obtiene la instancia global del factory (singleton pattern).
    
    Args:
        docs_base_dir: Directorio base de documentos
        
    Returns:
        Instancia de AgentFactory
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = AgentFactory(docs_base_dir)
    return _global_factory


if __name__ == "__main__":
    # Tests
    print("=== Test del Agent Factory ===\n")
    
    factory = AgentFactory(docs_base_dir="docs")
    print(f"Factory Info: {factory.get_info()}\n")
    
    print(f"Personas disponibles: {factory.list_available_persons()}\n")
    
    if factory.available_persons:
        # Test obtener un agente
        first_person = factory.available_persons[0]
        print(f"Obteniendo agente para '{first_person}'...")
        agent = factory.get_agent(first_person)
        print(f"Agente creado: {agent.get_info()}\n")
        
        # Test cache
        print("Obteniendo el mismo agente (debe venir del cache)...")
        agent2 = factory.get_agent(first_person)
        print(f"¿Es el mismo objeto? {agent is agent2}\n")
        
        print(f"Factory después del cache: {factory.get_info()}\n")
