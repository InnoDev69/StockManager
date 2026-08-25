import sqlite3

from miscellaneous import logger
from flask import jsonify
from core.bd.bdErrors import DatabaseError

class APIError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def handle_db_error(error:Exception, context: str = "") -> tuple:
    """Convierte excepciones BD en respuestas HTTP amigables"""
    error_str = str(error).lower()
    
    # Manejo específico para errores definidos en bdErrors.py
    if isinstance(error, DatabaseError):
        db_error_msg = str(error)
        
        if "unique constraint" in db_error_msg.lower():
            msg = "Ya existe un registro con ese valor"
            logger.warning(f"UNIQUE constraint violation {context}: {error}")
            return jsonify({"error": msg}), 409
        
        if "foreign key" in db_error_msg.lower():
            msg = "Referencia inválida: el registro relacionado no existe"
            logger.warning(f"Foreign key violation {context}: {error}")
            return jsonify({"error": msg}), 400
        
        logger.error(f"Database error {context}: {error}", exc_info=True)
        return jsonify({"error": "Error en la base de datos"}), 500
    
    # Violación de restricción UNIQUE
    if isinstance(error, sqlite3.IntegrityError) and "unique" in error_str:
        msg = "Ya existe un registro con ese valor"
        logger.warning(f"UNIQUE constraint violation {context}: {error}")
        return jsonify({"error": msg}), 409
    
    # Violación de foreign key
    if isinstance(error, sqlite3.IntegrityError) and "foreign key" in error_str:
        msg = "Referencia inválida: el registro relacionado no existe"
        logger.warning(f"Foreign key violation {context}: {error}")
        return jsonify({"error": msg}), 400
    
    # Error operacional (BD no accesible, etc)
    if isinstance(error, sqlite3.OperationalError):
        logger.error(f"Operational error {context}: {error}", exc_info=True)
        return jsonify({"error": "Error en la base de datos"}), 500
    
    # Error genérico de algún otro tipo
    logger.error(f"Unexpected error {context}: {error}", exc_info=True)
    return jsonify({"error": "Error interno del servidor"}), 500