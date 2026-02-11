import re
import logging
from typing import List, Dict, Any
import hashlib

logger = logging.getLogger(__name__)

class KnowledgeManager:
    """
    Beheert het opdelen van tekst in chunks en het zoeken naar relevante informatie.
    Dit is de basis voor het RAG (Retrieval-Augmented Generation) systeem.
    """
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """
        Verdeelt tekst in kleinere, overlappende stukken (chunks).
        """
        if not text:
            return []
            
        # Opschonen van overbodige witruimte
        text = re.sub(r'\s+', ' ', text).strip()
        
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + self.chunk_size
            
            # Probeer te eindigen op een zin of alinea
            if end < text_len:
                # Zoek naar de laatste punt, vraagteken of uitroepteken in het window
                last_sentence_end = -1
                for char in ['. ', '? ', '! ', '\n']:
                    pos = text.rfind(char, start, end)
                    if pos > last_sentence_end:
                        last_sentence_end = pos
                
                if last_sentence_end != -1:
                    end = last_sentence_end + 1
            
            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap
            
            # Voorkom oneindige loops als chunk_overlap >= chunk_size
            if start >= end:
                start = end
                
        return [c for c in chunks if len(c) > 50] # Filter te kleine chunks

    def search_relevant_chunks(self, query: str, chunks: List[str], top_k: int = 5) -> List[str]:
        """
        Zoekt de meest relevante chunks voor een gegeven query.
        Gebruikt een simpele maar effectieve keyword-matching (TF-IDF stijl).
        """
        if not chunks:
            return []
            
        query_words = set(re.findall(r'\w+', query.lower()))
        if not query_words:
            return chunks[:top_k]
            
        scored_chunks = []
        for chunk in chunks:
            chunk_words = re.findall(r'\w+', chunk.lower())
            score = 0
            for word in query_words:
                # Bonus voor exacte matches
                count = chunk_words.count(word)
                if count > 0:
                    score += 1 + (count * 0.1) # Term frequency bonus
            
            if score > 0:
                scored_chunks.append((score, chunk))
        
        # Sorteer op score (hoogste eerst)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        return [chunk for score, chunk in scored_chunks[:top_k]]

    def get_content_hash(self, text: str) -> str:
        """Genereert een unieke hash voor content om dubbele verwerking te voorkomen."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

# Singleton instance
knowledge_manager = KnowledgeManager()
