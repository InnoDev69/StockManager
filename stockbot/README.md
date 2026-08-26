# StocklyBot — Chatbot liviano para Stockly

Chatbot en español pensado para integrarse fácil a Stockly. **No usa un LLM
generativo**: combina corrección ortográfica difusa con clasificación de
intención por **similitud semántica** (embeddings de
`paraphrase-multilingual-MiniLM-L12-v2`, ~470MB, corre en CPU) y manejo de
contexto por sesión.

A diferencia de un enfoque léxico (TF-IDF), esto compara **significado**, no
palabras literales: "hay stock de zapatillas" y "tenés calzado disponible"
matchean aunque no compartan vocabulario. Es el punto justo entre "reglas
rígidas" y "LLM pesado": mucho más preciso y tolerante a reformulaciones que
un clasificador léxico, sin la latencia ni el peso de un modelo generativo.

## ¿Qué resuelve?

- Entiende oraciones con **errores de ortografía** y **reformulaciones /
  sinónimos** (similitud semántica, no coincidencia de palabras).
- **Pide reformular** o dice que no entiende cuando la confianza es baja.
- Cuando la confianza es media, **pregunta si entendió bien** antes de actuar.
- Tiene **contexto conversacional**: si preguntás "¿y el precio?" después de
  preguntar por un producto, resuelve solo con el producto anterior.
- Permite **registrar acciones reales** (consultar stock, crear pedidos, etc.)
  con un simple decorador.
- **Aprende** agregando frases de ejemplo nuevas (se embeben al instante, sin
  reiniciar el servidor ni reentrenar nada) y loguea las preguntas no
  reconocidas para revisión.

## Nota sobre lo que esto NO es

Sigue siendo un clasificador de intenciones con respuestas predefinidas/
plantillas — no genera texto libre ni "conversa" de forma abierta como un
LLM. Es la opción correcta si el bot solo necesita reconocer bien un set
conocido de preguntas y acciones (que es el caso de uso descripto). Si en
algún momento se necesita conversación abierta de verdad, ese es un salto de
arquitectura distinto (LLM local o por API), no una mejora incremental de
esto.

## Estructura

```
stockly_bot/
├── intents.json     # Intenciones + frases de ejemplo (acá se amplía el "conocimiento")
├── nlu.py            # Normalización, corrección ortográfica, clasificación, entidades
├── context.py         # Sesiones y contexto conversacional (en memoria)
├── bot.py              # Orquestador principal (StocklyBot)
├── app.py               # Ejemplo de integración con Flask
└── requirements.txt
```

## Instalación

```bash
cd stockly_bot
pip install -r requirements.txt
```

**Importante — primera ejecución**: la primera vez que se instancia
`StocklyBot`, `sentence-transformers` descarga el modelo de embeddings
(~470MB) desde Hugging Face y lo cachea localmente (por defecto en
`~/.cache/torch/sentence_transformers/`, o `~/.cache/huggingface/`, según
versión). Esa primera vez **requiere internet**. Después de esa descarga, el
bot funciona 100% offline — el modelo cacheado se reutiliza siempre.

Si vas a empaquetar la app con PyInstaller para distribuirla offline, hay que
**pre-descargar el modelo en la máquina de build** y empaquetar esa carpeta
de caché junto con el ejecutable (o apuntar `HF_HOME`/`TRANSFORMERS_CACHE` a
una carpeta local incluida en la distribución), para que el usuario final no
necesite internet ni siquiera la primera vez. Si querés, te armo ese script
de empaquetado.

## Uso básico (sin Flask)

```python
from stockly_bot.bot import StocklyBot

bot = StocklyBot(
    intents_path="intents.json",
    product_catalog=["zapatillas", "remeras", "pantalones", "camperas"],
)

@bot.register_action("consultar_stock")
def consultar_stock(entities, session):
    producto = entities.get("producto")
    stock = mi_backend.get_stock(producto)   # tu lógica real acá
    return f"Quedan {stock} unidades de {producto}."

resp = bot.ask("cuanto stock ai de sapatiyas", session_id="user-123")
print(resp["text"])   # -> corrige "sapatiyas" a "zapatillas" y responde
```

`bot.ask(...)` devuelve siempre un dict:

```python
{
  "text": "Quedan 12 unidades de zapatillas.",
  "intent": "consultar_stock",
  "confidence": 0.76,
  "entities": {"producto": "zapatillas"},
  "session_id": "user-123",
  "needs_confirmation": False
}
```

## Uso con Flask

```bash
python app.py
```

```bash
curl -X POST http://localhost:5000/chat \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user-123", "message": "cuanto stock hay de zapatillas"}'
```

Para integrarlo a tu app Flask existente, en vez de correr `app.py` como
servidor aparte, simplemente:

1. Copiá la carpeta `stockly_bot/` dentro de tu proyecto.
2. En tu `app.py` (o donde tengas tus rutas), importá y registrá el blueprint,
   o directamente instanciá `StocklyBot` como en el ejemplo y agregá tu propio
   endpoint `/chat` (ver `app.py` como referencia — son ~15 líneas).
3. Reemplazá las funciones de ejemplo (`consultar_stock`, `crear_pedido`,
   etc.) por llamadas a tu backend/ORM real.

## Cómo ampliar el "conocimiento" del bot

Editar `intents.json` y agregar más frases de ejemplo dentro de la intención
correspondiente. Cuantas más variantes reales de tus usuarios agregues, mejor
clasifica. También podés agregar intenciones nuevas siguiendo el mismo
formato:

```json
{
  "name": "cancelar_pedido",
  "examples": ["cancela el pedido {producto}", "anula mi pedido de {producto}"],
  "action": "cancelar_pedido",
  "required_entities": ["producto"]
}
```

y registrar su acción con `@bot.register_action("cancelar_pedido")`.

### Aprendizaje en caliente (sin editar el JSON)

```python
bot.add_training_phrase("consultar_stock", "me decis si hay {producto}")
```

Esto reentrena el clasificador al instante (es liviano, no hace falta
reiniciar el proceso). Usalo, por ejemplo, desde un panel de admin donde
revisás las preguntas que quedaron en `unrecognized.jsonl` (las que el bot no
entendió) y las asignás a la intención correcta.

## Ajuste de umbrales de confianza

En `StocklyBot(...)`:

- `threshold_high` (default 0.62): por encima, responde con confianza.
- `threshold_low` (default 0.40): por debajo, pide reformular directamente.
- Entre ambos: pregunta "¿es correcto?" antes de ejecutar la acción.

Estos valores están calibrados para similitud coseno de embeddings
(típicamente entre 0.3 y 0.9 para frases relacionadas). Son un punto de
partida razonable; conviene ajustarlos mirando los logs reales de
conversaciones (`unrecognized.jsonl` y los `confidence` que devuelve
`bot.ask`). Si el bot pide confirmación de más ("¿es correcto?") con
preguntas que en realidad entendía bien, bajar `threshold_high` un poco.

## Notas de diseño / próximos pasos posibles

- El contexto y las sesiones están en memoria (`ContextManager`). Para
  producción con múltiples workers/instancias, reemplazar por Redis
  (la interfaz de `Session`/`ContextManager` se puede mantener igual).
- La extracción de entidades sigue siendo por gazetteer + regex (simple y
  rápida, no necesita embeddings). Si el catálogo de productos crece mucho,
  se puede mejorar con búsqueda difusa más sofisticada, pero para catálogos
  de hasta unos miles de productos esto funciona bien e instantáneo.
- El modelo de embeddings (`embedding_model` en `StocklyBot(...)`) es
  intercambiable. Si en algún momento se necesita más precisión y el
  hardware lo permite, se puede probar un modelo multilingüe más grande sin
  tocar el resto de la arquitectura.
- Si en el futuro se necesita conversación abierta real (no solo clasificar
  entre intenciones conocidas), ese es un cambio de arquitectura distinto:
  sumar un LLM local pequeño (ej. Qwen2.5-1.5B cuantizado, vía
  `llama-cpp-python`) que reciba el historial de la conversación y decida
  cuándo llamar a una función (tool calling) y cuándo responder texto libre.
  Es más pesado en cómputo/latencia que este enfoque, así que conviene
  evaluarlo solo si la precisión semántica actual no alcanza.
