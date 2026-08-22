import base64

def encode_text(text: str) -> str:
    """
    Encodes a string using Base64 (often confused with hashing).
    
    Args:
        text (str): The original text to hide.
        
    Returns:
        str: The encoded Base64 string.
    """
    text_bytes = text.encode('utf-8')
    encoded_bytes = base64.b64encode(text_bytes)
    return encoded_bytes.decode('utf-8')


def decode_text(encoded_text: str) -> str:
    """
    Decodes a Base64 string back to the original text.
    
    Args:
        encoded_text (str): The Base64 string to decode.
        
    Returns:
        str: The original decoded text.
    """
    encoded_bytes = encoded_text.encode('utf-8')
    decoded_bytes = base64.b64decode(encoded_bytes)
    return decoded_bytes.decode('utf-8')

def safe_encode(data):
    """Codifica de forma segura, convirtiendo booleanos a texto para poder encriptarlos."""
    # IMPORTANTE: La validación de bool debe ir antes, porque en Python un bool también cuenta como número
    if isinstance(data, bool): 
        # Convertimos True a "True" y luego lo encriptamos
        return encode_text(str(data))
        
    elif isinstance(data, str):
        return encode_text(data)
        
    elif isinstance(data, dict):
        return {safe_encode(k): safe_encode(v) for k, v in data.items()}
        
    elif isinstance(data, list):
        return [safe_encode(item) for item in data]
        
    else:
        return data


def safe_decode(data):
    """Decodifica de forma segura, restaurando los textos 'True'/'False' a booleanos reales."""
    if isinstance(data, str):
        try:
            # 1. Intentamos desencriptar
            dec = decode_text(data)
            
            # 2. Si el resultado es la palabra True/False, devolvemos un booleano real
            if dec == "True": return True
            if dec == "False": return False
            
            return dec
        except Exception:
            # Si falló la desencriptación (era texto plano sin encriptar)
            # También revisamos si es la palabra True/False en texto plano
            if data == "True": return True
            if data == "False": return False
            return data
            
    elif isinstance(data, dict):
        return {safe_decode(k): safe_decode(v) for k, v in data.items()}
        
    elif isinstance(data, list):
        return [safe_decode(item) for item in data]
        
    else:
        # Si ya era un booleano real (por el bug anterior) o un número, lo devuelve intacto
        return data


if __name__ == "__main__":
    original_message = "False"
    print(f"Original: {original_message}")
    
    obfuscated_text = encode_text(original_message)
    print(f"Encoded:  {obfuscated_text}")
    
    recovered_text = decode_text(obfuscated_text)
    print(f"Decoded:  {recovered_text}")