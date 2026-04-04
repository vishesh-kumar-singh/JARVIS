import os
from user_persona import UserPersona
from langchain_core.documents import Document

try:
    from RAG import RAG
except ImportError:
    RAG = None

class PersonaRAG:
    def __init__(self):
        self.persona = UserPersona()

    def search(self, query: str) -> str:
        if not RAG:
            return "RAG module is not available."
        
        text = self.persona.get_supplemental_text()
        if not text.strip():
            return "No supplemental persona data found."
            
        docs = [Document(page_content=text)]
        try:
            return RAG(docs, query, results=3)
        except Exception as e:
            return f"Error searching persona context: {e}"

persona_rag_service = PersonaRAG()
