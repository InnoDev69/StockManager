# Documentación técnica de `security.py`

## 1. Visión General del Módulo

Ofrece codificación/decodificación Base64 para texto y funciones recursivas para transformar strings, diccionarios y listas. `safe_decode` intenta mantener compatibilidad con datos que pueden estar codificados o en texto plano y convierte literalmente `True`/`False` a booleanos.

El patrón es un **Transformador recursivo de estructuras**. Base64 es ofuscación/codificación, no cifrado ni hashing.

## 2. Dependencias

### Biblioteca estándar

- `base64`: codificación y decodificación Base64.

No hay dependencias de terceros ni internas.

## 3. API Pública

### `encode_text`

```python
def encode_text(text: str) -> str:
    """Codifica texto UTF-8 en Base64.

    Args:
        text: Texto de entrada.

    Returns:
        Cadena Base64.

    Raises:
        AttributeError: Si el valor no implementa `encode`.
        UnicodeEncodeError: Si el texto no puede codificarse como UTF-8.
    """
```

### `decode_text`

```python
def decode_text(encoded_text: str) -> str:
    """Decodifica Base64 a texto UTF-8.

    Args:
        encoded_text: Cadena Base64.

    Returns:
        Texto original.

    Raises:
        UnicodeDecodeError: Si los bytes no son UTF-8.
        binascii.Error: Si Base64 es inválido, sujeto al modo permisivo de
            `base64.b64decode`.
    """
```

### `safe_encode` y `safe_decode`

```python
def safe_encode(data: Any) -> Any: ...
def safe_decode(data: Any) -> Any: ...
```

Recorren booleanos, strings, diccionarios y listas. Preservan otros tipos. `safe_encode` codifica claves de diccionario; `safe_decode` puede convertir claves a tipos distintos, lo que debe considerarse al serializar.

## 4. Consideraciones de Ingeniería

- **Complejidad:** para una estructura con `n` bytes/elementos, ambas funciones son `O(n)` en tiempo y memoria, más la expansión Base64 aproximada de 4/3 para strings.
- **Seguridad crítica:** Base64 no proporciona confidencialidad, integridad ni autenticación. No debe usarse para contraseñas, tokens sensibles o secretos. Usar hashing con sal para contraseñas y AEAD (por ejemplo, Fernet o AES-GCM) para cifrado.
- **Validación:** `decode_text` no usa `validate=True`; puede aceptar caracteres no Base64 y producir resultados inesperados. La entrada externa debe validarse estrictamente.
- **Errores:** `safe_decode` captura cualquier excepción y trata el valor como texto plano. Esto hace la API tolerante, pero puede ocultar corrupción o ataques de datos ambiguos.
- **Ambigüedad:** cualquier texto Base64 válido puede decodificarse accidentalmente; un valor plano como `"True"` cambia a booleano. Debe existir un formato versionado o marcador de encoding.
- **Concurrencia:** no usa estado global mutable y es reentrante.
- **Casos límite:** estructuras cíclicas provocan recursión infinita; diccionarios con claves transformadas pueden colisionar; profundidad extrema puede superar el límite de recursión; tuplas, sets y objetos personalizados se preservan sin transformar.

## 5. Ejemplo de Uso

```python
from miscellaneous.security import decode_text, encode_text, safe_decode, safe_encode

encoded = encode_text("Inventario seguro")
print(decode_text(encoded))

payload = {"active": True, "name": "SKU-001", "tags": ["sale"]}
restored = safe_decode(safe_encode(payload))
print(restored)
```
