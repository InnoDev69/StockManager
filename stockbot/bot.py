"""
StocklyBot: chatbot liviano para Stockly.

Uso básico:
    from stockly_bot.bot import StocklyBot

    bot = StocklyBot(
        intents_path="intents.json",
        product_catalog=["zapatillas", "remeras", "pantalones", "camperas"],
    )

    @bot.register_action("consultar_stock")
    def consultar_stock(entities, session):
        producto = entities.get("producto")
        stock = mi_backend.get_stock(producto)  # tu lógica real
        return f"Quedan {stock} unidades de {producto}."

    respuesta = bot.ask("cuanto stock hay de zapatillas", session_id="user-123")
    print(respuesta["text"])
"""
import json
import random
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from .context import ContextManager
    from .nlu import (
        DEFAULT_EMBEDDING_MODEL,
        IntentClassifier,
        SpellCorrector,
        extract_entities,
        normalize,
    )
except ImportError:
    from context import ContextManager
    from nlu import (
        DEFAULT_EMBEDDING_MODEL,
        IntentClassifier,
        SpellCorrector,
        extract_entities,
        normalize,
    )

# Respuestas por defecto cuando el bot no entiende / duda
FALLBACK_LOW = [
    "No estoy seguro de haber entendido eso. ¿Podrías reformularlo?",
    "Perdón, no llegué a entender bien tu consulta. ¿Me lo explicás de otra forma?",
]
FALLBACK_MID_TEMPLATE = "Creo que preguntás sobre \"{intent}\", pero no estoy del todo seguro. ¿Es correcto?"


class StocklyBot:
    def __init__(
        self,
        intents_path: str,
        product_catalog: Optional[List[str]] = None,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        threshold_high: float = 0.62,
        threshold_low: float = 0.40,
        unrecognized_log_path: Optional[str] = "unrecognized.jsonl",
    ):
        """
        threshold_high: por encima de esto, el bot responde con confianza.
        threshold_low: por debajo de esto, el bot pide reformular directamente.
        Entre ambos: el bot infiere pero pide confirmación ("¿es correcto?").

        Nota: estos umbrales están calibrados para similitud coseno de
        embeddings (típicamente 0.3-0.9), no para TF-IDF. Conviene ajustarlos
        mirando los scores reales que devuelve bot.ask(...) con consultas de
        usuarios reales — arrancar conservador (umbrales altos) y bajar de a
        poco si el bot pide confirmación de más.

        La primera vez que se instancia, se descarga el modelo de embeddings
        (~470MB, una sola vez, se cachea localmente). Requiere internet la
        primera vez; después funciona 100% offline.
        """
        self.intents_path = intents_path
        self.product_catalog = product_catalog or []
        self.embedding_model = embedding_model
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self.unrecognized_log_path = unrecognized_log_path

        self.intents: List[dict] = []
        self.intents_by_name: Dict[str, dict] = {}
        self.classifier = IntentClassifier(model_name=self.embedding_model)
        self.spell_corrector: Optional[SpellCorrector] = None
        self.context = ContextManager()
        self.actions: Dict[str, Callable] = {}

        # estado pendiente de confirmación por sesión: {session_id: intent_name}
        self._pending_confirmation: Dict[str, dict] = {}

        self._load_intents()

    # ---------- carga / entrenamiento ----------

    def _load_intents(self):
        data = json.loads(Path(self.intents_path).read_text(encoding="utf-8"))
        self.intents = data["intents"]
        self.intents_by_name = {i["name"]: i for i in self.intents}
        self.classifier.fit(self.intents)

        vocab = set()
        for intent in self.intents:
            for ex in intent["examples"]:
                for w in normalize(ex).split():
                    vocab.add(w)
        for p in self.product_catalog:
            for w in normalize(p).split():
                vocab.add(w)
        self.spell_corrector = SpellCorrector(list(vocab))

    def add_training_phrase(self, intent_name: str, phrase: str):
        """Aprendizaje incremental: agrega un ejemplo nuevo a una intención existente."""
        if intent_name not in self.intents_by_name:
            raise ValueError(f"Intención desconocida: {intent_name}")
        self.intents_by_name[intent_name]["examples"].append(phrase)
        self.classifier.add_example(intent_name, phrase)

    def reload(self):
        """Recarga intents.json desde disco (por si se editó/ampliaron ejemplos)."""
        self._load_intents()

    # ---------- acciones ----------

    def register_action(self, intent_name: str):
        """Decorador para registrar la función que ejecuta una intención con 'action'."""

        def decorator(func: Callable):
            self.actions[intent_name] = func
            return func

        return decorator

    # ---------- núcleo conversacional ----------

    def ask(self, text: str, session_id: str = "default") -> dict:
        session = self.context.get_session(session_id)
        raw_text = text

        # 1. si había una confirmación pendiente, resolverla primero
        pending = self._pending_confirmation.get(session_id)
        if pending is not None:
            del self._pending_confirmation[session_id]
            if self._is_affirmative(text):
                return self._execute_intent(
                    pending["intent"], pending["entities"], pending["score"], raw_text, session
                )
            elif self._is_negative(text):
                reply = "Entendido, ¿podrías contarme de otra forma qué necesitás?"
                session.push_turn(raw_text, None, {}, reply)
                return self._response(reply, None, 0.0, {}, session_id)
            # si no es ni sí ni no, se sigue procesando el mensaje normalmente

        # 2. normalizar + corregir ortografía
        normalized = normalize(raw_text)
        corrected = self.spell_corrector.correct(normalized) if self.spell_corrector else normalized

        # 3. clasificar intención
        intent_name, score, ranked = self.classifier.predict(corrected)

        # 4. extraer entidades
        entities = extract_entities(corrected, self.product_catalog)

        # 5. decidir según umbral de confianza
        if intent_name is None or score < self.threshold_low:
            reply = random.choice(FALLBACK_LOW)
            self._log_unrecognized(raw_text, ranked)
            session.push_turn(raw_text, None, entities, reply)
            return self._response(reply, None, score, entities, session_id)

        if score < self.threshold_high:
            # confianza media: pedir confirmación antes de ejecutar
            self._pending_confirmation[session_id] = {
                "intent": intent_name,
                "entities": entities,
                "score": score,
            }
            reply = FALLBACK_MID_TEMPLATE.format(intent=self._friendly_intent_name(intent_name))
            session.push_turn(raw_text, intent_name, entities, reply)
            return self._response(reply, intent_name, score, entities, session_id, needs_confirmation=True)

        # confianza alta: ejecutar directamente
        return self._execute_intent(intent_name, entities, score, raw_text, session)

    def _execute_intent(self, intent_name: str, entities: dict, score: float, raw_text: str, session):
        intent = self.intents_by_name[intent_name]
        required = intent.get("required_entities", [])
        entities = session.resolve_missing_entities(entities, required)

        missing = [r for r in required if r not in entities]
        if missing:
            reply = f"Falta que me digas {', '.join(missing)}. ¿Me lo confirmás?"
            session.push_turn(raw_text, intent_name, entities, reply)
            return self._response(reply, intent_name, score, entities, session.session_id)

        action_result_text = None
        action_fn = self.actions.get(intent.get("action"))
        if action_fn:
            action_result_text = action_fn(entities, session)

        if action_result_text:
            reply = action_result_text
        elif intent.get("responses"):
            template = random.choice(intent["responses"])
            reply = template.format(**{**entities})
        else:
            reply = "Listo."

        session.push_turn(raw_text, intent_name, entities, reply)
        return self._response(reply, intent_name, score, entities, session.session_id)

    # ---------- utilidades ----------

    @staticmethod
    def _is_affirmative(text: str) -> bool:
        t = normalize(text)
        return any(w in t for w in ["si", "dale", "correcto", "exacto", "asi es", "yes"])

    @staticmethod
    def _is_negative(text: str) -> bool:
        t = normalize(text)
        return any(w in t for w in ["no", "para nada", "incorrecto", "eso no"])

    @staticmethod
    def _friendly_intent_name(intent_name: str) -> str:
        return intent_name.replace("_", " ")

    def _log_unrecognized(self, text: str, ranked: list):
        if not self.unrecognized_log_path:
            return
        entry = {
            "text": text,
            "top_candidates": ranked[:3],
            "ts": time.time(),
        }
        try:
            with open(self.unrecognized_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    @staticmethod
    def _response(
        text: str,
        intent: Optional[str],
        score: float,
        entities: dict,
        session_id: str,
        needs_confirmation: bool = False,
    ) -> dict:
        return {
            "text": text,
            "intent": intent,
            "confidence": round(float(score), 3),
            "entities": entities,
            "session_id": session_id,
            "needs_confirmation": needs_confirmation,
        }
