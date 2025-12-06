"""
Multi-Agent CV Assistant
=========================

Aplicación Streamlit que usa el sistema multi-agente para
responder preguntas sobre los CVs del equipo.
"""

import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

from agents.multi_agent_system import get_multi_agent_system

load_dotenv()


# ======================================================
# CONFIGURACIÓN
# ======================================================

DEFAULT_AGENT = os.getenv("DEFAULT_AGENT", "abril")
DOCS_DIR = "docs"


# ======================================================
# FUNCIONES AUXILIARES
# ======================================================

def get_person_info(person_name: str) -> dict:
    """Obtiene información básica de una persona desde su carpeta."""
    import json
    
    person_dir = Path(DOCS_DIR) / person_name.lower()
    metadata_path = person_dir / "metadata.json"
    foto_path = person_dir / "foto.jpg"
    
    info = {
        "nombre": person_name.title(),
        "titulo": "Integrante del equipo",
        "email": "no-disponible",
        "foto": None
    }
    
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            info.update({
                "nombre": meta.get("nombre", person_name.title()),
                "titulo": meta.get("titulo", meta.get("profesion", "Integrante del equipo")),
                "email": meta.get("email", "no-disponible")
            })
    
    if foto_path.exists():
        info["foto"] = str(foto_path)
    
    return info


def get_all_team_members():
    """Obtiene lista de todos los miembros del equipo."""
    docs_path = Path(DOCS_DIR)
    
    if not docs_path.exists():
        return []
    
    members = []
    for item in docs_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            members.append(item.name.lower())
    
    return sorted(members)


# ======================================================
# STATE
# ======================================================

def init_state():
    """Inicializa el estado de la sesión."""
    if "history" not in st.session_state:
        st.session_state.history = []
    
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0
    
    if "submitted" not in st.session_state:
        st.session_state.submitted = None
    
    if "system" not in st.session_state:
        st.session_state.system = get_multi_agent_system(
            docs_base_dir=DOCS_DIR,
            default_agent=DEFAULT_AGENT
        )
    
    if "show_debug" not in st.session_state:
        st.session_state.show_debug = False


def submit():
    """Callback para el submit del input."""
    st.session_state.submitted = st.session_state[f"user_input_{st.session_state.input_key}"]


def bump_input_key():
    """Incrementa el key del input para resetear el campo."""
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0
    st.session_state.input_key += 1


# ======================================================
# UI
# ======================================================

def render_sidebar():
    """Renderiza la barra lateral con información del equipo."""
    st.sidebar.title("🤖 Multi-Agent CV System")
    st.sidebar.markdown("---")
    
    # Información del sistema
    system = st.session_state.system
    system_info = system.get_system_info()
    
    st.sidebar.subheader("👥 Equipo")
    members = system_info.get("available_agents", [])
    
    if members:
        for member in members:
            is_default = member == system_info.get("default_agent")
            icon = "⭐" if is_default else "👤"
            st.sidebar.write(f"{icon} {member.title()}")
    else:
        st.sidebar.info("No hay miembros configurados")
    
    st.sidebar.markdown("---")
    
    # Agente por defecto
    st.sidebar.subheader("⚙️ Configuración")
    st.sidebar.write(f"**Agente default:** {system_info.get('default_agent', 'N/A').title()}")
    st.sidebar.caption("Cuando no se menciona a nadie específicamente")
    
    st.sidebar.markdown("---")
    
    # Debug toggle
    st.session_state.show_debug = st.sidebar.checkbox(
        "🔍 Mostrar info de routing",
        value=st.session_state.show_debug
    )
    
    st.sidebar.markdown("---")
    
    # Instrucciones
    with st.sidebar.expander("💡 Cómo usar"):
        st.markdown("""
        **Ejemplos de preguntas:**
        
        - "¿Qué experiencia tienes en ML?" 
          *(consulta al agente default)*
        
        - "¿Qué sabe Juan de Python?"
          *(consulta específica a Juan)*
        
        - "Compara la experiencia de María y Pedro"
          *(consulta múltiple con agregación)*
        
        - "¿Cuáles son las skills del equipo?"
          *(sin mencionar nombres específicos)*
        """)


def render_chat_message(msg: dict):
    """Renderiza un mensaje del chat."""
    if msg["role"] == "user":
        st.markdown(f"""
        <div style='background:#334155; padding:14px 18px; border-radius:12px;
                    margin-bottom:10px; text-align:right; border:1px solid #475569;
                    color:#e2e8f0;'>
            {msg['content']}
        </div>
        """, unsafe_allow_html=True)
    else:
        # Mensaje del asistente
        st.markdown(f"""
        <div style='background:#1e293b; padding:14px 18px; border-radius:12px;
                    margin-bottom:10px; border:1px solid #334155;
                    color:#e2e8f0;'>
            {msg['content']}
        </div>
        """, unsafe_allow_html=True)
        
        # Mostrar debug info si está habilitado
        if st.session_state.show_debug and "debug_info" in msg:
            with st.expander("🔍 Routing Info"):
                debug = msg["debug_info"]
                st.json({
                    "Agentes detectados": debug.get("detected_agents", []),
                    "Requiere agregación": debug.get("requires_aggregation", False),
                    "Default usado": debug.get("routing_info", {}).get("default_used", False)
                })


def main():
    """Función principal de la aplicación."""
    
    st.set_page_config(
        layout="wide",
        page_title="Multi-Agent CV Assistant",
        page_icon="🤖"
    )
    
    init_state()
    
    # CSS Global
    st.markdown("""
    <style>
    body { background-color: #0f172a; }
    
    .main-header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 12px;
        margin-bottom: 30px;
        border: 1px solid #475569;
    }
    
    .main-title {
        font-size: 36px;
        color: #e2e8f0;
        margin-bottom: 10px;
        font-weight: bold;
    }
    
    .main-subtitle {
        font-size: 18px;
        color: #38bdf8;
        margin-top: 8px;
    }
    
    .main-description {
        color: #94a3b8;
        font-size: 15px;
        margin-top: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    render_sidebar()
    
    # Header principal
    st.markdown("""
    <div class='main-header'>
        <div class='main-title'>🤖 Multi-Agent CV Assistant</div>
        <div class='main-subtitle'>Sistema Inteligente de Consulta de CVs</div>
        <div class='main-description'>
            Consulta información sobre los CVs del equipo. El sistema detecta automáticamente
            a quién te referís y puede comparar múltiples perfiles.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Área del chat
    chat_container = st.container()
    
    with chat_container:
        # Renderizar historial
        for msg in st.session_state.history:
            render_chat_message(msg)
    
    # Input del usuario
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([5, 1])
    
    with col1:
        st.text_input(
            "Pregunta:",
            key=f"user_input_{st.session_state.input_key}",
            placeholder="Ej: ¿Qué experiencia tiene el equipo en Machine Learning?",
            label_visibility="collapsed",
            on_change=submit
        )
    
    with col2:
        sent = st.button("Enviar", use_container_width=True)
        if sent:
            st.session_state.submitted = st.session_state.get(
                f"user_input_{st.session_state.input_key}", ""
            )
    
    # Procesar pregunta
    if st.session_state.submitted:
        pregunta = st.session_state.submitted.strip()
        st.session_state.submitted = None
        
        if pregunta:
            with st.spinner("🤖 Procesando con el sistema multi-agente..."):
                # Obtener respuesta con detalles
                system = st.session_state.system
                result = system.query_with_details(pregunta)
                
                answer = result.get("final_answer", "Error: No se pudo generar respuesta")
            
            # Guardar en historial
            st.session_state.history.append({
                "role": "user",
                "content": pregunta
            })
            
            st.session_state.history.append({
                "role": "assistant",
                "content": answer,
                "debug_info": result
            })
            
            # Limpiar input y rerun
            bump_input_key()
            st.rerun()
    
    # Footer
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center; color:#64748b; font-size:13px;'>"
        "© 2025 — Multi-Agent CV System · Powered by LangGraph + Groq + Pinecone"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
