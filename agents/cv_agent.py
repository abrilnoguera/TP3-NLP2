"""
CV Agent - Agente individual para cada CV
==========================================

Cada instancia representa a una persona del equipo y maneja
las consultas sobre su CV usando RAG.
"""

import os
import json
from typing import List, Dict, Any
from datetime import datetime, date
from pathlib import Path

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class CVAgent:
    """
    Agente individual que responde preguntas sobre un CV específico.
    Cada agente tiene su propio índice Pinecone y metadata.
    """
    
    def __init__(self, person_name: str, docs_base_dir: str = "docs"):
        """
        Inicializa un agente para una persona específica.
        
        Args:
            person_name: Nombre de la persona (nombre de la carpeta en docs/)
            docs_base_dir: Directorio base donde están los CVs
        """
        self.person_name = person_name.lower()
        self.docs_dir = Path(docs_base_dir) / self.person_name
        
        # Validar que existe la carpeta
        if not self.docs_dir.exists():
            raise ValueError(f"No existe el directorio: {self.docs_dir}")
        
        # Configuración - Usar UN SOLO índice con namespaces
        self.index_name = "cv-alumno"  # Índice compartido (reutilizado)
        self.namespace = self.person_name  # Namespace único por persona
        self.embed_model_name = "sentence-transformers/all-MiniLM-L6-v2"
        
        # Cargar metadata
        self.metadata = self._load_metadata()
        
        # Inicializar clientes (lazy loading)
        self._pinecone = None
        self._index = None
        self._embedder = None
        self._groq = None
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Carga el metadata.json de la persona."""
        metadata_path = self.docs_dir / "metadata.json"
        
        if not metadata_path.exists():
            return {"nombre": self.person_name.title(), "email": "no-disponible"}
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        # Calcular edad si existe fecha_nacimiento
        if "fecha_nacimiento" in meta:
            meta["edad"] = self._calcular_edad(meta["fecha_nacimiento"])
        
        return meta
    
    def _calcular_edad(self, fecha_str: str) -> int:
        """Calcula la edad a partir de una fecha de nacimiento."""
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        hoy = date.today()
        return hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
    
    @property
    def pinecone(self):
        """Lazy loading del cliente Pinecone."""
        if self._pinecone is None:
            api_key = os.getenv("PINECONE_API_KEY")
            if not api_key:
                raise ValueError("PINECONE_API_KEY no configurada")
            self._pinecone = Pinecone(api_key=api_key)
        return self._pinecone
    
    @property
    def index(self):
        """Lazy loading del índice Pinecone."""
        if self._index is None:
            self._index = self.pinecone.Index(self.index_name)
        return self._index
    
    @property
    def embedder(self):
        """Lazy loading del modelo de embeddings."""
        if self._embedder is None:
            self._embedder = SentenceTransformer(self.embed_model_name)
        return self._embedder
    
    @property
    def groq(self):
        """Lazy loading del cliente Groq."""
        if self._groq is None:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY no configurada")
            self._groq = Groq(api_key=api_key)
        return self._groq
    
    def embed(self, text: str) -> List[float]:
        """Genera embedding para un texto."""
        return self.embedder.encode(text).tolist()
    
    def retrieve(self, question: str, top_k: int = 5) -> List[str]:
        """
        Recupera chunks relevantes del CV usando RAG con namespace.
        
        Args:
            question: Pregunta del usuario
            top_k: Número de chunks a recuperar
            
        Returns:
            Lista de textos relevantes del CV
        """
        try:
            res = self.index.query(
                vector=self.embed(question),
                top_k=top_k,
                include_metadata=True,
                namespace=self.namespace  # Usar namespace específico
            )
            return [m["metadata"].get("texto", "") for m in res.get("matches", [])]
        except Exception as e:
            print(f"Error en retrieve para {self.person_name}: {e}")
            return []
    
    def _metadata_to_text(self) -> str:
        """Convierte metadata a texto para el prompt."""
        lines = ["INFORMACIÓN FIJA DEL CV:"]
        for k, v in self.metadata.items():
            k_fmt = k.replace("_", " ").capitalize()
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v)
            lines.append(f"- {k_fmt}: {v}")
        return "\n".join(lines)
    
    def _build_prompt(self, question: str, chunks: List[str]) -> str:
        """
        Construye el prompt para el LLM.
        
        Args:
            question: Pregunta del usuario
            chunks: Chunks recuperados del CV
            
        Returns:
            Prompt formateado
        """
        metadata_txt = self._metadata_to_text()
        email = self.metadata.get("email", "no-disponible")
        nombre = self.metadata.get("nombre", self.person_name.title())
        
        chunks_txt = "\n\n---\n\n".join(chunks) if chunks else "No se recuperó información relevante."
        
        return f"""
Eres un asistente que responde preguntas sobre el perfil profesional de {nombre}.
Respondé con un tono natural, profesional y claro. No copies texto literal del CV.

REGLAS:
1. La metadata tiene prioridad absoluta.
2. Los chunks solo sirven para complementar, sin copiar.
3. Si algo NO está ni en metadata ni en chunks, respondé EXACTAMENTE:
   "No tengo esa información, pero podés escribir a {email} para consultas adicionales."
4. Está prohibido calcular edad bajo cualquier forma. Si aparece "edad" en metadata, usala. Si no, decí que no está disponible.
5. No expliques reglas ni describas cómo funcionás.
6. Siempre referite a la persona en tercera persona o usando su nombre.

METADATA:
{metadata_txt}

CHUNKS DEL CV:
{chunks_txt}

PREGUNTA:
{question}
        """.strip()
    
    def answer(self, question: str) -> str:
        """
        Genera una respuesta a la pregunta sobre este CV.
        
        Args:
            question: Pregunta del usuario
            
        Returns:
            Respuesta generada por el LLM
        """
        # Recuperar contexto relevante
        chunks = self.retrieve(question)
        
        # Construir prompt
        prompt = self._build_prompt(question, chunks)
        
        # Generar respuesta con Groq
        try:
            resp = self.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": f"Sos un asistente profesional que responde sobre {self.metadata.get('nombre', self.person_name.title())}."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"Error al generar respuesta para {self.person_name}: {str(e)}"
    
    def get_info(self) -> Dict[str, Any]:
        """
        Retorna información del agente para debugging.
        
        Returns:
            Dict con información del agente
        """
        return {
            "person_name": self.person_name,
            "index_name": self.index_name,
            "docs_dir": str(self.docs_dir),
            "metadata_keys": list(self.metadata.keys()),
            "nombre_completo": self.metadata.get("nombre", "N/A"),
            "email": self.metadata.get("email", "N/A"),
        }


if __name__ == "__main__":
    # Test del agente
    print("=== Test del CV Agent ===\n")
    
    try:
        agent = CVAgent("abril", docs_base_dir="docs")
        print(f"Agente creado: {agent.get_info()}\n")
        
        test_question = "¿Qué experiencia tiene en Machine Learning?"
        print(f"Pregunta: {test_question}")
        print(f"Respuesta: {agent.answer(test_question)}\n")
        
    except Exception as e:
        print(f"Error en test: {e}")
