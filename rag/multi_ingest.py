"""
Script de Ingesta Multi-CV con NAMESPACES
=========================================

Este script procesa múltiples CVs y los almacena en Pinecone
usando un ÚNICO índice con namespaces separados por persona.

Uso:
    python rag/multi_ingest.py

Características:
- Un solo índice: 'cv-alumno'
- Un namespace por persona (abril, anthony, melanie, etc.)
- Eficiente para planes free de Pinecone (límite 5 índices)
"""

import os
import sys
import pdfplumber
from pathlib import Path
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

# Configuración
INDEX_NAME = "cv-alumno"  # Índice único compartido
DOCS_DIR = "docs"
CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def extraer_texto_pdf(pdf_path: Path) -> str:
    """Extrae texto de un archivo PDF."""
    texto = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            contenido = page.extract_text()
            if contenido:
                texto += contenido + "\n"
    return texto.strip()


def chunkear_texto(texto: str, chunk_size: int = CHUNK_SIZE, 
                    overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Divide el texto en chunks con overlap."""
    chunks = []
    start = 0
    
    while start < len(texto):
        end = start + chunk_size
        chunk = texto[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    
    return chunks


def encontrar_cvs(docs_dir: str) -> List[Tuple[str, Path]]:
    """
    Encuentra todos los CVs en el directorio docs.
    Retorna lista de tuplas (nombre_persona, ruta_pdf)
    """
    cvs = []
    docs_path = Path(docs_dir)
    
    if not docs_path.exists():
        print(f"❌ Error: No existe el directorio '{docs_dir}'")
        sys.exit(1)
    
    # Buscar PDFs en subdirectorios
    for item in docs_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Buscar PDF en esta carpeta
            pdfs = list(item.glob("*.pdf"))
            if pdfs:
                person_name = item.name
                cvs.append((person_name, pdfs[0]))
    
    return cvs


def crear_indice_si_no_existe(pc: Pinecone, index_name: str, dimension: int = 384):
    """Crea el índice principal si no existe."""
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    
    if index_name in existing_indexes:
        print(f"✅ El índice '{index_name}' ya existe")
        return
    
    print(f"🔄 Creando índice '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=dimension,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    print(f"✅ Índice '{index_name}' creado")


def ingestar_cv_namespace(person_name: str, pdf_path: Path, 
                          index, embedder: SentenceTransformer):
    """Procesa e ingesta un CV en el namespace correspondiente."""
    print(f"\n{'='*60}")
    print(f"📄 Procesando CV de: {person_name.title()}")
    print(f"{'='*60}")
    
    namespace = person_name.lower()
    
    try:
        # Extraer texto
        print("📖 Extrayendo texto del PDF...")
        texto = extraer_texto_pdf(pdf_path)
        print(f"   → {len(texto)} caracteres extraídos")
        
        if len(texto) < 40:
            print(f"⚠️  Texto muy corto, saltando...")
            return False
        
        # Chunkear
        print("✂️  Chunkeando texto...")
        chunks = chunkear_texto(texto)
        print(f"   → {len(chunks)} chunks generados")
        
        # Generar embeddings
        embeddings = [embedder.encode(chunk).tolist() for chunk in chunks]
        
        # Preparar vectores
        vectors = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            vectors.append({
                "id": f"{person_name}_{i}",
                "values": emb,
                "metadata": {
                    "texto": chunk,
                    "persona": person_name.lower()
                }
            })
        
        # Subir a Pinecone con NAMESPACE
        print(f"🚀 Subiendo a namespace '{namespace}'...")
        index.upsert(vectors=vectors, namespace=namespace)
        print(f"   ➜ {len(vectors)}/{len(vectors)} chunks subidos")
        print(f"✅ CV de {person_name.title()} ingestado correctamente")
        
        # Verificar
        try:
            stats = index.describe_index_stats()
            namespace_stats = stats.get('namespaces', {}).get(namespace, {})
            vector_count = namespace_stats.get('vector_count', 'N/A')
            print(f"   → Total vectores en namespace '{namespace}': {vector_count}")
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"❌ Error al procesar '{person_name}': {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Función principal."""
    print(f"\n{'='*60}")
    print("🚀 MULTI-INGEST con NAMESPACES")
    print(f"{'='*60}\n")
    
    # Validar API key
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("❌ Falta la variable de entorno PINECONE_API_KEY")
        sys.exit(1)
    
    # Inicializar Pinecone
    pc = Pinecone(api_key=api_key)
    print("✅ Cliente Pinecone inicializado")
    
    # Cargar modelo de embeddings
    print("📦 Cargando modelo de embeddings...")
    embedder = SentenceTransformer(MODEL_NAME)
    print(f"✅ Modelo cargado ({embedder.get_sentence_embedding_dimension()} dimensiones)")
    
    # Crear índice principal si no existe
    print(f"\n🔍 Verificando índice '{INDEX_NAME}'...")
    crear_indice_si_no_existe(pc, INDEX_NAME, dimension=384)
    
    # Conectar al índice
    index = pc.Index(INDEX_NAME)
    
    # Encontrar CVs
    print(f"\n🔍 Buscando CVs en '{DOCS_DIR}'...")
    cvs = encontrar_cvs(DOCS_DIR)
    
    if not cvs:
        print(f"❌ No se encontraron CVs en '{DOCS_DIR}'")
        print("💡 Asegúrate de tener carpetas con PDFs en el directorio docs/")
        sys.exit(1)
    
    print(f"✅ Se encontraron {len(cvs)} CVs:\n")
    for name, path in cvs:
        print(f"   • {name.title()} - {path.name}")
    
    # Procesar cada CV
    print(f"\n{'='*60}")
    print(f"Ingesta a índice '{INDEX_NAME}' con namespaces...")
    print(f"{'='*60}")
    
    exitosos = 0
    fallidos = 0
    
    for person_name, pdf_path in cvs:
        resultado = ingestar_cv_namespace(person_name, pdf_path, index, embedder)
        if resultado:
            exitosos += 1
        else:
            fallidos += 1
    
    # Resumen
    print(f"\n{'='*60}")
    print("📊 RESUMEN FINAL")
    print(f"{'='*60}")
    print(f"✅ Exitosos: {exitosos}")
    print(f"❌ Fallidos: {fallidos}")
    print(f"📝 Total: {len(cvs)}")
    print(f"\n💡 Índice usado: {INDEX_NAME}")
    print(f"💡 Namespaces: {', '.join([name for name, _ in cvs])}")
    print("\n🎉 Proceso completado!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
