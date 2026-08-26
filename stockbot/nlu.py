"""
Motor de NLU liviano para Stockly.

No usa un LLM generativo: combina corrección ortográfica difusa (rapidfuzz)
con clasificación de intención por SIMILITUD SEMÁNTICA (embeddings de
sentence-transformers) en vez de TF-IDF. Esto entiende sinónimos, frases
reformuladas y errores de tipeo mucho mejor que un enfoque léxico, y sigue
corriendo perfectamente en CPU (el modelo de embeddings pesa ~470MB y una
inferencia toma milisegundos, no segundos).
"""
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

import numpy as np
from rapidfuzz import process, fuzz
from sentence_transformers import SentenceTransformer

# Modelo de embeddings multilingüe, liviano, pensado para correr en CPU.
# Se descarga una sola vez (~470MB) y queda cacheado localmente en
# ~/.cache/torch/sentence_transformers/ (o donde indique HF_HOME).
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Palabras muy frecuentes en español que no aportan a la clasificación.
STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "en", "y", "o", "a", "que", "con", "por", "para", "es", "son",
    "me", "te", "se", "mi", "tu", "su", "lo", "al", "esta", "este",
}


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """minúsculas, sin tildes, sin signos de puntuación sobrantes."""
    text = text.lower().strip()
    text = strip_accents(text)
    text = re.sub(r"[^a-z0-9ñ{}\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class SpellCorrector:
    """Corrige palabras fuera de vocabulario contra el vocabulario de entrenamiento."""

    def __init__(self, vocabulary: List[str], score_cutoff: int = 72):
        self.vocabulary = sorted(set(vocabulary))
        self.score_cutoff = score_cutoff

    def correct_word(self, word: str) -> str:
        if word in self.vocabulary or len(word) <= 2:
            return word
        match = process.extractOne(
            word, self.vocabulary, scorer=fuzz.WRatio, score_cutoff=self.score_cutoff
        )
        return match[0] if match else word

    def correct(self, text: str) -> str:
        words = text.split()
        return " ".join(self.correct_word(w) for w in words)


class IntentClassifier:
    """Clasificador de intención basado en embeddings semánticos + similitud coseno.

    A diferencia de TF-IDF (que compara palabras literales), esto compara
    SIGNIFICADO: "hay stock de zapatillas" y "tenés calzado disponible" van a
    quedar cerca en el espacio de embeddings aunque no compartan vocabulario.
    """

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.embeddings: Optional[np.ndarray] = None
        self.example_intents: List[str] = []
        self.examples: List[str] = []

    def _ensure_model(self):
        if self.model is None:
            # Carga perezosa: el modelo se descarga/carga una sola vez, la
            # primera vez que hace falta (no al importar el módulo).
            self.model = SentenceTransformer(self.model_name)

    def fit(self, intents: List[dict]):
        self._ensure_model()
        self.examples = []
        self.example_intents = []
        for intent in intents:
            for ex in intent["examples"]:
                clean = normalize(re.sub(r"\{[^}]+\}", " ", ex))
                self.examples.append(clean)
                self.example_intents.append(intent["name"])

        self.embeddings = self.model.encode(
            self.examples, convert_to_numpy=True, normalize_embeddings=True
        )

    def add_example(self, intent_name: str, phrase: str):
        """Agrega un ejemplo nuevo sin recalcular todo (aprendizaje incremental barato:
        solo se embebe la frase nueva y se concatena)."""
        self._ensure_model()
        clean = normalize(re.sub(r"\{[^}]+\}", " ", phrase))
        new_emb = self.model.encode(
            [clean], convert_to_numpy=True, normalize_embeddings=True
        )
        self.examples.append(clean)
        self.example_intents.append(intent_name)
        if self.embeddings is None:
            self.embeddings = new_emb
        else:
            self.embeddings = np.vstack([self.embeddings, new_emb])

    def predict(self, text: str) -> Tuple[Optional[str], float, List[Tuple[str, float]]]:
        if self.model is None or self.embeddings is None or not self.examples:
            return None, 0.0, []
        vec = self.model.encode([text], convert_to_numpy=True, normalize_embeddings=True)
        # Embeddings ya normalizados -> el producto punto ES la similitud coseno.
        sims = self.embeddings @ vec[0]

        # score máximo por intención (no promedio, para no diluir con ejemplos poco relacionados)
        best_by_intent: Dict[str, float] = {}
        for intent_name, score in zip(self.example_intents, sims):
            if score > best_by_intent.get(intent_name, -1):
                best_by_intent[intent_name] = float(score)

        ranked = sorted(best_by_intent.items(), key=lambda x: x[1], reverse=True)
        if not ranked:
            return None, 0.0, []
        top_intent, top_score = ranked[0]
        return top_intent, top_score, ranked


def extract_entities(text: str, product_catalog: List[str]) -> Dict[str, str]:
    """Extracción simple de entidades por gazetteer (productos) + regex (cantidades)."""
    entities: Dict[str, str] = {}

    # cantidad: primer número encontrado
    qty_match = re.search(r"\b(\d+)\b", text)
    if qty_match:
        entities["cantidad"] = qty_match.group(1)

    # producto: fuzzy match contra el catálogo, probando ventanas de 1 a 3 palabras
    if product_catalog:
        words = text.split()
        best_score = 0
        best_product = None
        for size in (3, 2, 1):
            for i in range(len(words) - size + 1):
                chunk = " ".join(words[i : i + size])
                match = process.extractOne(
                    chunk, product_catalog, scorer=fuzz.WRatio, score_cutoff=70
                )
                if match and match[1] > best_score:
                    best_score = match[1]
                    best_product = match[0]
        if best_product:
            entities["producto"] = best_product

    return entities
