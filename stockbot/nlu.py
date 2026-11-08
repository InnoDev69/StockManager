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
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

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

# "900 ml" -> "900ml" (une número + unidad para que matchee igual que en el catálogo)
_UNIT_JOIN = re.compile(r"(?<=\d)\s+(?=(?:ml|cc|lt|lts|l|g|gr|grs|kg|kgs|mg)\b)")


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize(text: str) -> str:
    """minúsculas, sin tildes, sin signos de puntuación sobrantes."""
    text = text.lower().strip()
    text = strip_accents(text)
    text = re.sub(r"[^a-z0-9ñ{}\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _UNIT_JOIN.sub("", text)
    return text


def _has_digit(text: str) -> bool:
    return any(c.isdigit() for c in text)


class SpellCorrector:
    """Corrige palabras fuera de vocabulario contra el vocabulario de entrenamiento."""

    def __init__(self, vocabulary: List[str], score_cutoff: int = 72):
        self.vocabulary = sorted(set(vocabulary))
        self._vocab_set = set(self.vocabulary)
        self.score_cutoff = score_cutoff

    def correct_word(self, word: str) -> str:
        # Las palabras con números (900ml, 1l...) NO se corrigen: cambiarlas
        # convertiría un producto en otro (900ml -> 500ml).
        if word in self._vocab_set or len(word) <= 2 or _has_digit(word):
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
        Issue URL: https://github.com/InnoDev69/StockManager/issues/49
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


# ---------- productos ----------


@lru_cache(maxsize=4096)
def _product_tokens(name: str) -> Tuple[str, ...]:
    """Palabras significativas del nombre de un producto (normalizadas, sin stopwords)."""
    tokens: List[str] = []
    for t in normalize(name).split():
        if t not in STOPWORDS and t not in tokens:
            tokens.append(t)
    return tuple(tokens)


def _token_matches(token: str, word: str) -> bool:
    """Palabra del producto vs palabra del mensaje.

    - Iguales: match.
    - Con números (900ml, 5l): solo exacto, para no confundir variantes.
    - Resto: difuso, pero solo con palabras de 4+ letras (evita que "el" matchee "helado").
    """
    if token == word:
        return True
    if len(token) < 4 or len(word) < 4 or _has_digit(token) or _has_digit(word):
        return False
    return fuzz.ratio(token, word) >= 85


def find_products(
    text: str,
    product_catalog: List[str],
    min_confident_coverage: float = 0.6,
    max_candidates: int = 5,
) -> Tuple[List[str], bool, Set[int]]:
    """Busca productos del catálogo mencionados en `text` (ya normalizado).

    Devuelve (candidatos, seguro, índices_de_palabras_usadas).
    - seguro=True: hay un único ganador claro -> candidatos tiene 1 elemento.
    - seguro=False y 1 candidato: coincidencia débil (conviene confirmar).
    - seguro=False y varios candidatos: ambiguo (conviene preguntar cuál).
    - candidatos vacío: no se reconoció ningún producto.
    """
    words = text.split()
    scored = []
    for name in dict.fromkeys(product_catalog):  # sin duplicados exactos, conserva el orden
        tokens = _product_tokens(name)
        if not tokens:
            continue
        used: Set[int] = set()
        matched = 0
        for token in tokens:
            for i, w in enumerate(words):
                if _token_matches(token, w):
                    matched += 1
                    used.add(i)
                    break
        if matched:
            scored.append((matched, matched / len(tokens), name, used))

    if not scored:
        return [], False, set()

    best = max(s[0] for s in scored)
    top = [s for s in scored if s[0] == best]
    top.sort(key=lambda s: (-s[1], s[2]))
    full = [s for s in top if s[1] == 1.0]

    winner = None
    if len(top) == 1:
        winner = top[0]
    elif len(full) == 1:
        winner = full[0]  # ej: existe un producto llamado exactamente "Aceite"

    if winner is not None:
        return [winner[2]], winner[1] >= min_confident_coverage, winner[3]

    top = top[:max_candidates]
    used_all: Set[int] = set().union(*(s[3] for s in top))
    return [s[2] for s in top], False, used_all


def extract_entities(text: str, product_catalog: List[str]) -> Dict[str, Any]:
    """Extracción simple de entidades: productos (catálogo) + cantidad (número suelto).

    - "producto": nombre exacto del catálogo cuando hay un ganador claro.
    - "producto_candidatos": lista de nombres cuando es ambiguo o débil.
    """
    entities: Dict[str, Any] = {}
    words = text.split()
    used: Set[int] = set()

    if product_catalog:
        candidates, confident, used = find_products(text, product_catalog)
        if candidates:
            if confident:
                entities["producto"] = candidates[0]
            else:
                entities["producto_candidatos"] = candidates

    # cantidad: primer número suelto que NO sea parte del nombre de un producto
    for i, w in enumerate(words):
        if i not in used and w.isdigit():
            entities["cantidad"] = w
            break

    return entities