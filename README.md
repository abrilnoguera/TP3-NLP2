# 🤖 Multi-Agent CV Assistant

Sistema inteligente de consulta de CVs que utiliza **agentes múltiples** con **LangGraph** para responder preguntas sobre los perfiles profesionales del equipo. Cada integrante tiene su propio agente con acceso a un índice RAG individual en Pinecone.

## 📋 Características

- ✅ **Router inteligente** con regex que detecta automáticamente a quién se refiere la consulta
- ✅ **Agente por persona** - cada integrante tiene su propio agente RAG
- ✅ **Agregación automática** cuando se consulta por múltiples personas
- ✅ **Agente default** cuando no se menciona a nadie específicamente
- ✅ **LangGraph** para orquestación de flujo de agentes
- ✅ **Interfaz Streamlit** moderna y responsive
- ✅ **Sistema extensible** - fácil agregar nuevos miembros

## 🏗️ Arquitectura

### Diagrama de Flujo

```
┌─────────────────────────────────┐
│    Usuario hace una pregunta    │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│   Conditional Edge (Router)     │
│   - Analiza la query con regex  │
│   - Detecta nombre(s) personas  │
│   - Default: Abril (alumno)     │
└───────────────┬─────────────────┘
                │
        ┌───────┴────────┬──────────────┐
        │                │              │
        ▼                ▼              ▼
   ┌─────────┐      ┌─────────┐   ┌──────────┐
   │ Agente  │      │ Agente  │   │  Agente  │
   │ Persona │      │ Persona │   │  Persona │
   │    1    │      │    2    │   │    N     │
   └────┬────┘      └────┬────┘   └────┬─────┘
        │                │              │
        │  (Cada agente tiene su       │
        │   propio RAG con índice      │
        │   Pinecone específico)       │
        │                │              │
        └────────┬───────┴──────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  Aggregator      │
        │  (Si múltiples)  │
        └────────┬─────────┘
                 │
                 ▼
        ┌─────────────────┐
        │   Respuesta     │
        │   final al      │
        │   usuario       │
        └─────────────────┘
```

### Componentes Principales

#### 1. Router (Conditional Edge)
- **Función**: Analizar la query y decidir qué agente(s) invocar
- **Tecnología**: Expresiones regulares (librería `re`)
- **Lógica**:
  - Busca nombres de personas en la query
  - Si no encuentra ninguno → Agente default (Abril)
  - Si encuentra uno → Ese agente específico
  - Si encuentra varios → Múltiples agentes

#### 2. Agentes Individuales
- Cada integrante tiene:
  - Su propio índice Pinecone: `cv-{nombre}`
  - Su propio metadata.json con datos estructurados
  - Lógica RAG personalizada para su CV

#### 3. Aggregator
- Combina respuestas cuando se consultan múltiples CVs
- Formatea la respuesta de manera coherente

#### 4. State Management
- LangGraph StateGraph para manejar el flujo
- Estado compartido entre nodos

## 📁 Estructura del Proyecto

```
TP3-NLP2/
├── agents/
│   ├── __init__.py
│   ├── router.py           # Conditional edge logic
│   ├── agent_factory.py    # Crea agentes dinámicamente
│   ├── cv_agent.py         # Clase base para agentes
│   └── multi_agent_app.py  # Aplicación principal con LangGraph
│
├── docs/
│   ├── abril/
│   │   ├── Abril Noguera - CV.pdf
│   │   └── metadata.json
│   ├── persona2/
│   │   ├── [Nombre] - CV.pdf
│   │   └── metadata.json
│   └── persona3/
│       ├── [Nombre] - CV.pdf
│       └── metadata.json
│
├── rag/
│   └── multi_ingest.py     # Ingesta múltiples Cvs
│
└── app.py                  # Streamlit app con multi-agente
```

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd TP3-NLP2
```

### 2. Crear entorno virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# Pinecone
PINECONE_API_KEY=tu-api-key
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# Groq (LLM)
GROQ_API_KEY=tu-api-key

# Configuración del sistema
DEFAULT_AGENT=abril
```

## 📝 Agregar Nuevos Integrantes

### Paso 1: Crear carpeta con CV

```bash
mkdir docs/nombre_persona
```

### Paso 2: Agregar archivos

Dentro de `docs/nombre_persona/`:

1. **PDF del CV** (obligatorio):
   - Nombre: `[Nombre Completo] - CV.pdf`
   - Ejemplo: `Juan Pérez - CV.pdf`

2. **metadata.json** (obligatorio):
```json
{
  "nombre": "Juan Pérez",
  "titulo": "Data Scientist",
  "profesion": "Data Scientist",
  "titulo_maximo_obtenido": "Licenciatura en...",
  "ubicacion": "Buenos Aires, Argentina",
  "email": "juan@example.com",
  "linkedin": "linkedin.com/in/juanperez",
  "nivel_ingles": "Avanzado",
  "seniority": "Senior",
  "experiencia_años": 5,
  "skills_clave": [
    "Python",
    "Machine Learning",
    "TensorFlow"
  ]
}
```

3. **foto.jpg** (opcional):
   - Foto del integrante para mostrar en la UI

### Paso 3: Ingestar el CV

```bash
python rag/multi_ingest.py
```

Esto:
- Detecta automáticamente todos los CVs en `docs/`
- Crea un índice Pinecone para cada persona: `cv-nombre`
- Genera embeddings y los sube

### Paso 4: Listo! 🎉

El sistema detectará automáticamente al nuevo integrante. No se necesita configuración adicional.

## 💻 Uso

### Ejecutar la aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá en `http://localhost:8501`

### Ejemplos de consultas

#### Consulta individual (agente específico)
```
"¿Qué experiencia tiene Abril en Machine Learning?"
```
→ Usa el agente de Abril

#### Consulta sin nombre (agente default)
```
"¿Qué habilidades tenés en Python?"
```
→ Usa el agente default (configurado en .env)

#### Consulta múltiple (agregación)
```
"Compara la experiencia de Abril y Juan en NLP"
```
→ Consulta ambos agentes y agrega las respuestas

#### Consulta general
```
"¿Cuáles son las skills del equipo?"
```
→ Usa agente default (o se puede configurar para consultar a todos)

## 🔧 Componentes Técnicos

### Router (Conditional Edge)

Ubicación: `agents/router.py`

- Analiza la query con **regex** para detectar nombres
- Retorna lista de agentes a consultar
- Define el agente default si no detecta ningún nombre

```python
from agents.router import QueryRouter

router = QueryRouter(docs_dir="docs", default_agent="abril")
agents = router.route("¿Qué sabe Juan de Python?")
# → ['juan']
```

### CV Agent

Ubicación: `agents/cv_agent.py`

- Agente individual para cada persona
- Tiene su propio índice Pinecone: `cv-{nombre}`
- Maneja RAG específico del CV
- Carga metadata automáticamente

```python
from agents.cv_agent import CVAgent

agent = CVAgent("abril", docs_base_dir="docs")
answer = agent.answer("¿Qué experiencia tienes en ML?")
```

### Multi-Agent System (LangGraph)

Ubicación: `agents/multi_agent_system.py`

Orquesta el flujo completo:

1. **route_node**: Detecta agentes necesarios
2. **conditional_edge**: Single vs Multi-agent
3. **single_agent_node** o **multi_agent_node**: Consulta agentes
4. **aggregate_node**: Agrega respuestas múltiples

```python
from agents.multi_agent_system import get_multi_agent_system

system = get_multi_agent_system()
answer = system.query("¿Qué experiencia tiene el equipo?")
```

## 📊 Tecnologías

- **LangGraph** - Orquestación de agentes
- **LangChain** - Framework base
- **Groq** - LLM (Llama 3.1)
- **Pinecone** - Vector database (1 índice por persona)
- **Sentence Transformers** - Embeddings
- **Streamlit** - Frontend
- **Python regex** - Router/detector de nombres

## 🧪 Testing

### Test del Router

```bash
cd agents
python router.py
```

### Test del CV Agent

```bash
cd agents
python cv_agent.py
```

### Test del Sistema Completo

```bash
cd agents
python multi_agent_system.py
```

## 📹 Demo

El proyecto incluye una demo en video mostrando:

1. ✅ Consulta individual (agente específico)
2. ✅ Consulta sin nombre (agente default)
3. ✅ Consulta múltiple con comparación
4. ✅ Sistema de routing en acción

Ver: `demo/Demo CV Agent.mp4`

## 🐛 Troubleshooting

### Error: "Persona no encontrada"

- Verificar que existe la carpeta `docs/nombre_persona`
- Verificar que hay un PDF en esa carpeta
- Ejecutar `python rag/multi_ingest.py` para ingestar

### Error: "PINECONE_API_KEY no configurada"

- Verificar archivo `.env` en la raíz
- Verificar que las variables estén correctamente escritas

### Error al ingestar CV

- Verificar que el PDF tiene texto extraíble (no es imagen escaneada)
- Verificar permisos de lectura en la carpeta `docs/`

### Índices antiguos en Pinecone

Para limpiar índices:

```python
from pinecone import Pinecone
import os

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

# Listar índices
for index in pc.list_indexes():
    print(index.name)

# Eliminar índice específico
pc.delete_index("cv-nombre")
```

## 📚 Referencias

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Pinecone Documentation](https://docs.pinecone.io/)
- [Groq API](https://console.groq.com/docs)
- [Streamlit Documentation](https://docs.streamlit.io/)
