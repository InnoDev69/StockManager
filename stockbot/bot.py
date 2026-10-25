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

Si el catálogo cambia en runtime (productos nuevos), llamar a
bot.set_product_catalog(nuevo_catalogo).

Aprendizaje: cuando el bot duda de la intención y el usuario confirma con "sí",
la frase (con {producto} en lugar del nombre) se anota en learned_pending.jsonl.
Al llegar a `promote_after` confirmaciones de la misma frase, se agrega a
intents.json. Los rechazos se registran en unrecognized.jsonl (rejected_intent)
para revisarlos a mano; nunca entrenan.

Contexto: si falta un dato obligatorio (ej. el producto), el bot lo pregunta y
queda esperando la respuesta (_pending_slot) en lugar de tratarla como una
consulta nueva.
"""
import json
import os
import random
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from .context import ContextManager
    from .nlu import (
        DEFAULT_EMBEDDING_MODEL,
        STOPWORDS,
        IntentClassifier,
        SpellCorrector,
        extract_entities,
        find_products,
        normalize,
    )
except ImportError:
    from context import ContextManager
    from nlu import (
        DEFAULT_EMBEDDING_MODEL,
        STOPWORDS,
        IntentClassifier,
        SpellCorrector,
        extract_entities,
        find_products,
        normalize,
    )

# Respuestas por defecto cuando el bot no entiende / duda
FALLBACK_LOW = [
    "No estoy seguro de haber entendido eso. ¿Podrías reformularlo?",
    "Perdón, no llegué a entender bien tu consulta. ¿Me lo explicás de otra forma?",
]
FALLBACK_MID_TEMPLATE = "Creo que preguntás sobre \"{intent}\", pero no estoy del todo seguro. ¿Es correcto?"

# Prefijos de palabras que indican una consulta de stock puntual.
# Se comparan contra el inicio de cada palabra (ej: "disponib" -> disponible/disponibles/disponibilidad).
STOCK_KEYWORD_PREFIXES = (
    "stock",
    "existencia",
    "unidad",
    "disponib",
)

# Para elegir entre candidatos: "el primero", "la segunda", etc.
ORDINALS = {
    "primero": 1, "primera": 1,
    "segundo": 2, "segunda": 2,
    "tercero": 3, "tercera": 3,
    "cuarto": 4, "cuarta": 4,
    "quinto": 5, "quinta": 5,
}

# Para cortar una pregunta pendiente ("¿de qué producto?").
CANCEL_WORDS = {"cancelar", "cancela", "olvidalo", "dejalo", "nada", "ninguno", "ninguna"}

# Intentos máximos de completar un dato faltante antes de abandonar.
MAX_SLOT_ATTEMPTS = 2


class StocklyBot:
    def __init__(
        self,
        intents_path: str,
        product_catalog: Optional[List[str]] = None,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        threshold_high: float = 0.62,
        threshold_low: float = 0.40,
        unrecognized_log_path: Optional[str] = "unrecognized.jsonl",
        learned_log_path: Optional[str] = "learned_pending.jsonl",
        promote_after: int = 3,
    ):
        """
        threshold_high: por encima de esto, el bot responde con confianza.
        threshold_low: por debajo de esto, el bot pide reformular directamente.
        Entre ambos: el bot infiere pero pide confirmación ("¿es correcto?").

        learned_log_path: archivo donde se anotan las frases confirmadas por
            usuarios (None desactiva el aprendizaje por confirmación).
        promote_after: cuántas confirmaciones de la misma frase hacen falta
            para agregarla a intents.json.

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
        self.learned_log_path = learned_log_path
        self.promote_after = max(1, promote_after)

        self.intents: List[dict] = []
        self.intents_by_name: Dict[str, dict] = {}
        self._raw_config: dict = {}
        self.classifier = IntentClassifier(model_name=self.embedding_model)
        self.spell_corrector: Optional[SpellCorrector] = None
        self.vocab: set = set()
        self._example_set: set = set()  # ejemplos de entrenamiento normalizados
        self.context = ContextManager()
        self.actions: Dict[str, Callable] = {}

        # protege intents.json, el clasificador y los archivos de aprendizaje
        self._io_lock = threading.RLock()

        # estado pendiente por sesión
        self._pending_confirmation: Dict[str, dict] = {}  # "¿es correcto?"
        self._pending_choice: Dict[str, dict] = {}  # "¿cuál de estos productos?"
        self._pending_slot: Dict[str, dict] = {}  # "¿de qué producto?"

        self._load_intents()

    # ---------- carga / entrenamiento ----------

    def _load_intents(self):
        with self._io_lock:
            data = json.loads(Path(self.intents_path).read_text(encoding="utf-8"))
            self._raw_config = data
            self.intents = data["intents"]  # misma lista que _raw_config["intents"]
            self.intents_by_name = {i["name"]: i for i in self.intents}
            self.classifier.fit(self.intents)
            self._rebuild_vocab()

    def _rebuild_vocab(self):
        vocab = set()
        examples = set()
        for intent in self.intents:
            for ex in intent["examples"]:
                clean = normalize(re.sub(r"\{[^}]+\}", " ", ex))
                examples.add(clean)
                for w in clean.split():
                    vocab.add(w)
        for p in self.product_catalog:
            for w in normalize(p).split():
                vocab.add(w)
        self.vocab = vocab
        self._example_set = examples
        self.spell_corrector = SpellCorrector(list(vocab))

    def set_product_catalog(self, product_catalog: List[str]):
        """Actualiza el catálogo (productos nuevos/borrados) sin reentrenar el clasificador."""
        self.product_catalog = list(product_catalog)
        self._rebuild_vocab()

    def add_training_phrase(self, intent_name: str, phrase: str, persist: bool = False) -> bool:
        """Aprendizaje incremental: agrega un ejemplo nuevo a una intención existente.

        persist=True además lo guarda en intents.json (escritura atómica).
        Devuelve True si se agregó, False si ya existía o la frase está vacía.
        """
        if intent_name not in self.intents_by_name:
            raise ValueError(f"Intención desconocida: {intent_name}")

        phrase = phrase.strip()
        if not phrase:
            return False

        with self._io_lock:
            examples = self.intents_by_name[intent_name]["examples"]
            key = normalize(phrase)
            if any(normalize(e) == key for e in examples):
                return False

            examples.append(phrase)
            self.classifier.add_example(intent_name, phrase)
            self._rebuild_vocab()
            if persist:
                self._save_intents()
        return True

    def _save_intents(self):
        """Escribe intents.json de forma atómica (temporal + os.replace).

        Conserva las demás claves de nivel superior del archivo.
        """
        path = Path(self.intents_path)
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent or Path(".")), prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._raw_config, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

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

        # 1a. si había una confirmación pendiente, resolverla primero
        pending = self._pending_confirmation.pop(session_id, None)
        if pending is not None:
            if self._is_affirmative(text):
                # solo se aprende cuando el bot dudaba de la INTENCIÓN
                if pending.get("learn_text"):
                    self._record_confirmation(
                        pending["intent"], pending["learn_text"], session_id
                    )
                return self._execute_intent(
                    pending["intent"], pending["entities"], pending["score"], raw_text, session
                )
            elif self._is_negative(text):
                if pending.get("learn_text"):
                    self._log_unrecognized(
                        pending.get("original_text", ""),
                        [],
                        rejected_intent=pending["intent"],
                        score=pending["score"],
                    )
                return self._reject(raw_text, session, session_id)
            # si no es ni sí ni no, se sigue procesando el mensaje normalmente

        # 1b. si había una elección de producto pendiente, resolverla
        choice = self._pending_choice.pop(session_id, None)
        if choice is not None:
            picked = self._pick_candidate(text, choice["candidates"])
            if picked:
                entities = {**choice["entities"], "producto": picked}
                return self._execute_intent(
                    choice["intent"], entities, choice["score"], raw_text, session
                )
            if self._is_negative(text):
                return self._reject(raw_text, session, session_id)
            # no eligió ninguno: se sigue procesando el mensaje normalmente

        # 1c. si el bot estaba esperando un dato faltante (ej. el producto), completarlo
        slot = self._pending_slot.pop(session_id, None)
        if slot is not None:
            result = self._fill_slot(text, slot, session)
            if result is not None:
                return result
            # None = el mensaje es otra consulta distinta: se procesa normalmente

        # 2. normalizar + corregir ortografía
        normalized = normalize(raw_text)
        corrected = self.spell_corrector.correct(normalized) if self.spell_corrector else normalized

        # 3. extraer entidades (antes de clasificar, para poder usarlas en reglas)
        entities = extract_entities(corrected, self.product_catalog)
        candidates = entities.pop("producto_candidatos", [])

        # 3b. mensaje que es solo un producto ("azucar"): el clasificador no sirve
        # con una palabra suelta, así que se resuelve con el contexto
        if self._is_product_only(corrected):
            result = self._handle_product_only(entities, candidates, raw_text, session)
            if result is not None:
                return result

        # 4. clasificar intención
        intent_name, score, ranked = self.classifier.predict(corrected)

        # 4b. regla explícita: palabra de stock + producto mencionado -> consultar_stock
        has_product = bool(entities.get("producto") or candidates)
        if (
            has_product
            and self._mentions_stock(corrected)
            and "consultar_stock" in self.intents_by_name
        ):
            intent_name = "consultar_stock"
            score = max(score, self.threshold_high)

        # 5. decidir según umbral de confianza.
        # Una palabra suelta solo cuenta como intención si coincide EXACTAMENTE con un
        # ejemplo de entrenamiento (sin corrección ortográfica): el score de embeddings
        # para palabras sueltas no es confiable ("azucar" -> despedida).
        single_unknown = (
            len(corrected.split()) == 1 and normalized not in self._example_set
        )
        if intent_name is None or score < self.threshold_low or single_unknown:
            reply = random.choice(FALLBACK_LOW)
            self._log_unrecognized(raw_text, ranked)
            session.push_turn(raw_text, None, entities, reply)
            return self._response(reply, None, score, entities, session_id)

        # 5b. intenciones que necesitan producto: nunca adivinar en silencio
        required = self.intents_by_name[intent_name].get("required_entities", [])
        if "producto" in required and "producto" not in entities:
            if candidates:
                return self._ask_which_product(
                    intent_name, entities, score, candidates, raw_text, session
                )
            if "producto" in session.slots and self._has_unknown_words(corrected):
                return self._confirm_reused_product(
                    intent_name, entities, score, raw_text, session
                )

        if score < self.threshold_high:
            # confianza media: pedir confirmación antes de ejecutar.
            # Esta es la única rama de la que el bot aprende si el usuario confirma.
            self._pending_confirmation[session_id] = {
                "intent": intent_name,
                "entities": entities,
                "score": score,
                "original_text": raw_text,
                "learn_text": self._make_learnable(corrected, entities.get("producto")),
            }
            product = entities.get("producto")

            if intent_name == "consultar_stock" and product:
                reply = f"¿Querés que consulte el stock de {product}?"
            elif intent_name == "consultar_precio" and product:
                reply = f"¿Querés que consulte el precio de {product}?"
            else:
                reply = FALLBACK_MID_TEMPLATE.format(
                    intent=self._friendly_intent_name(intent_name)
                )
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
            return self._ask_missing(intent_name, entities, score, missing[0], raw_text, session)

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

    # ---------- datos faltantes (slot filling) ----------

    def _ask_missing(self, intent_name, entities, score, key, raw_text, session):
        """Falta un dato obligatorio: preguntarlo y quedar esperando la respuesta."""
        sid = session.session_id
        self._pending_slot[sid] = {
            "intent": intent_name,
            "entities": entities,
            "score": score,
            "missing": key,
            "attempts": 0,
        }
        if key == "producto":
            # si el usuario escribió palabras que no existen en el vocabulario,
            # lo más probable es que haya nombrado un producto que no está cargado
            wrote_unknown = (
                not self._is_affirmative(raw_text)
                and self._has_unknown_words(normalize(raw_text))
            )
            if wrote_unknown:
                reply = "No encontré ese producto en el catálogo. ¿Cómo se llama exactamente?"
            else:
                reply = "¿De qué producto?"
        else:
            reply = f"¿Me decís {key}?"
        session.push_turn(raw_text, intent_name, entities, reply)
        return self._response(reply, intent_name, score, entities, sid, needs_confirmation=True)

    def _fill_slot(self, text: str, slot: dict, session) -> Optional[dict]:
        """Interpreta el mensaje como respuesta al dato faltante.

        Devuelve la respuesta, o None si el mensaje es claramente otra consulta
        (en cuyo caso ask() lo procesa normalmente y la espera se descarta).
        """
        sid = session.session_id
        norm = normalize(text)

        if self._is_negative(text) or norm in CANCEL_WORDS:
            reply = "Listo, lo dejamos ahí. ¿Necesitás otra cosa?"
            session.push_turn(text, None, {}, reply)
            return self._response(reply, None, 0.0, {}, sid)

        corrected = self.spell_corrector.correct(norm) if self.spell_corrector else norm
        found = extract_entities(corrected, self.product_catalog)
        cands = found.pop("producto_candidatos", [])
        key = slot["missing"]

        if found.get(key):
            entities = {**slot["entities"], key: found[key]}
            return self._execute_intent(slot["intent"], entities, slot["score"], text, session)

        if key == "producto" and cands:
            return self._ask_which_product(
                slot["intent"], slot["entities"], slot["score"], cands, text, session
            )

        # ¿es otra consulta con sentido propio? -> procesarla normalmente
        intent_name, score, _ = self.classifier.predict(corrected)
        useful = [w for w in corrected.split() if w not in STOPWORDS]
        if intent_name and score >= self.threshold_high and len(useful) >= 2:
            return None

        slot["attempts"] += 1
        if slot["attempts"] >= MAX_SLOT_ATTEMPTS:
            reply = (
                "No pude encontrarlo. Probá escribiendo el nombre como figura "
                "en el sistema, o pedime \"listar productos\"."
            )
            session.push_turn(text, None, {}, reply)
            return self._response(reply, None, 0.0, {}, sid)

        self._pending_slot[sid] = slot
        if key == "producto":
            reply = f"No encontré \"{text.strip()}\" en el catálogo. ¿Probás con otro nombre?"
        else:
            reply = f"No pude entender {key}. ¿Me lo repetís?"
        session.push_turn(text, slot["intent"], slot["entities"], reply)
        return self._response(
            reply, slot["intent"], slot["score"], slot["entities"], sid, needs_confirmation=True
        )

    # ---------- mensaje que es solo un producto ----------

    def _is_product_only(self, corrected: str) -> bool:
        """True si el mensaje se reduce a nombrar un producto (sin otras palabras útiles)."""
        if not self.product_catalog:
            return False
        cands, _, used = find_products(corrected, self.product_catalog)
        if not cands:
            return False
        leftover = [
            w for i, w in enumerate(corrected.split())
            if i not in used and w not in STOPWORDS
        ]
        return not leftover

    def _handle_product_only(self, entities, candidates, raw_text, session) -> Optional[dict]:
        """Resuelve "azucar" a secas usando el último intent de la sesión.

        - Si el último intent necesitaba producto: lo repite con este producto.
        - Si no: pregunta qué querer hacer con el producto.
        - Devuelve None si no se puede resolver (sigue el flujo normal).
        """
        sid = session.session_id
        product = entities.get("producto")
        last_name = session.last_intent
        last = self.intents_by_name.get(last_name) if last_name else None

        if last and "producto" in last.get("required_entities", []):
            if product:
                return self._execute_intent(last_name, entities, self.threshold_high, raw_text, session)
            if candidates:
                return self._ask_which_product(
                    last_name, entities, self.threshold_high, candidates, raw_text, session
                )

        if product:
            options = [
                self._friendly_intent_name(i["name"])
                for i in self.intents
                if "producto" in i.get("required_entities", [])
            ]
            reply = f"¿Qué querés saber de {product}?"
            if options:
                reply += f" Puedo: {', '.join(options)}."
            session.push_turn(raw_text, None, entities, reply)
            return self._response(reply, None, 0.0, entities, sid)

        return None

    # ---------- aprendizaje por confirmación ----------

    @staticmethod
    def _make_learnable(corrected: str, product: Optional[str]) -> str:
        """Convierte la frase en un ejemplo reutilizable: el producto pasa a {producto}."""
        text = corrected
        if product:
            product_norm = normalize(product)
            if product_norm and product_norm in text:
                text = text.replace(product_norm, "{producto}")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _record_confirmation(self, intent_name: str, phrase: str, session_id: str):
        """Anota una frase confirmada y la promueve a intents.json al llegar al umbral."""
        if not self.learned_log_path:
            return
        # descartar frases demasiado cortas o sin contenido útil
        useful = [w for w in phrase.split() if w not in STOPWORDS]
        if len(useful) < 2 or intent_name not in self.intents_by_name:
            return

        with self._io_lock:
            entry = {
                "intent": intent_name,
                "phrase": phrase,
                "session_id": session_id,
                "ts": time.time(),
            }
            try:
                with open(self.learned_log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                return

            count = 0
            try:
                with open(self.learned_log_path, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            e = json.loads(line)
                        except ValueError:
                            continue
                        if e.get("intent") == intent_name and e.get("phrase") == phrase:
                            count += 1
            except OSError:
                return

            if count >= self.promote_after:
                try:
                    self.add_training_phrase(intent_name, phrase, persist=True)
                except OSError:
                    pass

    # ---------- desambiguación de productos ----------

    def _ask_which_product(self, intent_name, entities, score, candidates, raw_text, session):
        """Hay varios productos posibles (o uno solo con coincidencia débil): preguntar."""
        sid = session.session_id
        if len(candidates) == 1:
            product = candidates[0]
            self._pending_confirmation[sid] = {
                "intent": intent_name,
                "entities": {**entities, "producto": product},
                "score": score,
            }
            reply = f"¿Te referís a {product}?"
        else:
            self._pending_choice[sid] = {
                "intent": intent_name,
                "entities": entities,
                "score": score,
                "candidates": candidates,
            }
            lines = "\n".join(f"{i}. {c}" for i, c in enumerate(candidates, 1))
            reply = (
                "Encontré varios productos que coinciden:\n"
                f"{lines}\n"
                "¿Cuál querés? (respondé con el número o el nombre)"
            )
        session.push_turn(raw_text, intent_name, entities, reply)
        return self._response(reply, intent_name, score, entities, sid, needs_confirmation=True)

    def _confirm_reused_product(self, intent_name, entities, score, raw_text, session):
        """No se reconoció producto en el mensaje pero hay palabras desconocidas:
        no usar el último producto en silencio, confirmarlo."""
        sid = session.session_id
        product = session.slots["producto"]
        self._pending_confirmation[sid] = {
            "intent": intent_name,
            "entities": {**entities, "producto": product},
            "score": score,
        }
        reply = (
            "No reconocí ningún producto en tu mensaje. "
            f"¿Querés que use {product}, el último que consultaste?"
        )
        session.push_turn(raw_text, intent_name, entities, reply)
        return self._response(reply, intent_name, score, entities, sid, needs_confirmation=True)

    def _pick_candidate(self, text: str, candidates: List[str]) -> Optional[str]:
        """Interpreta la respuesta del usuario a '¿cuál querés?': número, ordinal o nombre."""
        t = normalize(text)
        if t.isdigit() and 1 <= int(t) <= len(candidates):
            return candidates[int(t) - 1]
        for w in t.split():
            n = ORDINALS.get(w)
            if n and n <= len(candidates):
                return candidates[n - 1]
        found, _, _ = find_products(t, candidates)
        return found[0] if len(found) == 1 else None

    def _has_unknown_words(self, text: str) -> bool:
        """True si el texto tiene palabras que no están en el vocabulario (ni son solo números)."""
        return any(
            w not in self.vocab and w not in STOPWORDS and not w.isdigit()
            for w in text.split()
        )

    def _reject(self, raw_text: str, session, session_id: str) -> dict:
        reply = "Entendido, ¿podrías contarme de otra forma qué necesitás?"
        session.push_turn(raw_text, None, {}, reply)
        return self._response(reply, None, 0.0, {}, session_id)

    # ---------- utilidades ----------

    @staticmethod
    def _mentions_stock(text: str) -> bool:
        """True si alguna palabra del texto empieza con un prefijo de STOCK_KEYWORD_PREFIXES."""
        return any(
            word.startswith(prefix)
            for word in text.split()
            for prefix in STOCK_KEYWORD_PREFIXES
        )

    @staticmethod
    def _is_affirmative(text: str) -> bool:
        t = normalize(text)
        return t in ["si", "dale", "correcto", "exacto", "asi es", "yes"]

    @staticmethod
    def _is_negative(text: str) -> bool:
        t = normalize(text)
        # "no" solo como palabra completa (antes matcheaba dentro de "anotame", "unos"...)
        return "no" in t.split() or any(p in t for p in ["para nada", "incorrecto"])

    @staticmethod
    def _friendly_intent_name(intent_name: str) -> str:
        return intent_name.replace("_", " ")

    def _log_unrecognized(
        self,
        text: str,
        ranked: list,
        rejected_intent: Optional[str] = None,
        score: Optional[float] = None,
    ):
        """Registra consultas para revisión manual.

        Sin rejected_intent: el bot no entendió (confianza baja).
        Con rejected_intent: el bot entendió mal (el usuario dijo que no).
        """
        if not self.unrecognized_log_path:
            return
        entry = {
            "text": text,
            "top_candidates": ranked[:3],
            "ts": time.time(),
        }
        if rejected_intent is not None:
            entry["rejected_intent"] = rejected_intent
            entry["score"] = round(float(score or 0.0), 3)
        try:
            with self._io_lock:
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