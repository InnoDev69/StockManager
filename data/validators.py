"""
Validadores de entrada para protección contra datos inválidos.

Este módulo implementa validación exhaustiva de todos los datos de entrada
antes de procesarlos o almacenarlos en la base de datos. La validación temprana
previene errores, inconsistencias y posibles vulnerabilidades de seguridad.

Las validaciones se aplican en el backend independientemente de la validación
del frontend, siguiendo el principio de "never trust user input".
"""
from data.limits import Limits


class ValidationError(Exception):
    """
    Excepción lanzada cuando la validación de un campo falla.
    
    Atributos adicionales permiten identificar qué campo falló y construir
    mensajes de error específicos para el usuario.
    
    Attributes:
        field (str): Nombre del campo que falló la validación
        message (str): Descripción del error
    
    Example:
        >>> raise ValidationError("email", "Formato de email inválido")
    """
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class Validator:
    """
    Validador genérico con métodos estáticos para tipos comunes de datos.
    
    Centraliza la lógica de validación para evitar duplicación de código
    y asegurar reglas consistentes en toda la aplicación.
    
    Example:
        >>> cleaned = Validator.validate_string("nombre", user_input, 50)
        >>> quantity = Validator.validate_number("cantidad", qty_str, min_val=1)
    """
    
    @staticmethod
    def validate_string(field: str, value: str, max_length: int, required: bool = True) -> str:
        """
        Valida y limpia un campo de texto.
        
        Args:
            field (str): Nombre del campo (para mensajes de error)
            value (str): Valor a validar
            max_length (int): Longitud máxima permitida en caracteres
            required (bool): Si True, el campo no puede estar vacío
        
        Returns:
            str: Valor limpio con espacios en blanco eliminados, o None si no es required
        
        Raises:
            ValidationError: Si el valor es inválido según las reglas
        
        Note:
            Aplica strip() automáticamente para eliminar espacios sobrantes.
            Valores None son permitidos solo si required=False.
        """
        if value is None:
            if required:
                raise ValidationError(field, "El campo es obligatorio")
            return None
        
        if not isinstance(value, str):
            raise ValidationError(field, "Debe ser texto")
        
        value = value.strip()
        
        if required and not value:
            raise ValidationError(field, "El campo es obligatorio")
        
        if len(value) > max_length:
            raise ValidationError(field, f"Máximo {max_length} caracteres (tiene {len(value)})")
        
        return value
    
    @staticmethod
    def validate_number(field: str, value, min_val: float = 0, max_val: float = None, 
                        allow_float: bool = False, required: bool = True):
        """
        Valida y convierte un campo numérico.
        
        Args:
            field (str): Nombre del campo (para mensajes de error)
            value: Valor a validar (puede ser str, int o float)
            min_val (float): Valor mínimo permitido (inclusive)
            max_val (float): Valor máximo permitido (inclusive), None = sin límite
            allow_float (bool): Si True permite decimales, False solo enteros
            required (bool): Si True, el campo no puede ser None
        
        Returns:
            int|float: Valor numérico validado y convertido al tipo apropiado
        
        Raises:
            ValidationError: Si el valor no es numérico o está fuera de rango
        
        Example:
            >>> price = Validator.validate_number("precio", "19.99", 
            ...     min_val=0, max_val=10000, allow_float=True)
            >>> price
            19.99
        """
        if value is None:
            if required:
                raise ValidationError(field, "El campo es obligatorio")
            return None
        
        try:
            value = float(value) if allow_float else int(value)
        except (ValueError, TypeError):
            tipo = "número" if allow_float else "número entero"
            raise ValidationError(field, f"Debe ser un {tipo}")
        
        if value < min_val:
            raise ValidationError(field, f"El valor mínimo es {min_val}")
        
        if max_val is not None and value > max_val:
            raise ValidationError(field, f"El valor máximo es {max_val}")
        
        return value


class ItemValidator:
    """
    Validador especializado para productos del inventario.
    
    Encapsula las reglas de negocio específicas de los productos
    (códigos de barras, precios, cantidades, etc.).
    """
    
    @staticmethod
    def validate(barrs_code, description, name, quantity, min_quantity, price, status) -> dict:
        """
        Valida todos los campos de un producto simultáneamente.
        
        Args:
            barrs_code (str): Código de barras del producto
            description (str): Descripción del producto
            name (str): Nombre del producto (obligatorio)
            quantity (int): Cantidad en stock
            min_quantity (int): Stock mínimo para alertas
            price (float): Precio de venta
            status (int): Estado del producto (0=inactivo, 1=activo)
        
        Returns:
            dict: Diccionario con todos los campos validados y limpios
        
        Raises:
            ValidationError: Si algún campo no pasa la validación
                            (contiene field y message para UX)
        
        Example:
            >>> try:
            ...     clean = ItemValidator.validate("123", "Laptop", "HP", 10, 2, 599.99, 1)
            ... except ValidationError as e:
            ...     print(f"Error en {e.field}: {e.message}")
        """
        return {
            "barrs_code": Validator.validate_string(
                "Código de barras", barrs_code, 
                Limits.ITEM_BARCODE_MAX, required=False
            ),
            "description": Validator.validate_string(
                "Descripción", description, 
                Limits.ITEM_DESCRIPTION_MAX, required=False
            ),
            "name": Validator.validate_string(
                "Nombre", name, 
                Limits.ITEM_NAME_MAX, required=True
            ),
            "quantity": Validator.validate_number(
                "Cantidad", quantity, 
                min_val=0, max_val=Limits.ITEM_QUANTITY_MAX
            ),
            "min_quantity": Validator.validate_number(
                "Cantidad mínima", min_quantity, 
                min_val=0, max_val=Limits.ITEM_MIN_QUANTITY_MAX
            ),
            "price": Validator.validate_number(
                "Precio", price, 
                min_val=0, max_val=Limits.ITEM_PRICE_MAX, allow_float=True
            ),
            "status": Validator.validate_number(
                "Estado", status, 
                0, max_val=1, required=True
            ),
        }


class UserValidator:
    """
    Validador especializado para usuarios del sistema.
    
    Aplica reglas de negocio para credenciales, roles y datos de perfil.
    """
    
    @staticmethod
    def validate(username, password, email, role="user") -> dict:
        """
        Valida todos los campos de un usuario simultáneamente.
        
        Args:
            username (str): Nombre de usuario (único en BD)
            password (str): Contraseña en texto plano o hash
            email (str): Correo electrónico
            role (str): Rol del usuario (default: "user")
        
        Returns:
            dict: Diccionario con todos los campos validados y limpios
        
        Raises:
            ValidationError: Si algún campo no pasa la validación
        
        Note:
            Esta función NO hashea la contraseña, eso debe hacerse
            en la capa de lógica de negocio antes de guardar en BD.
        """
        return {
            "username": Validator.validate_string(
                "Usuario", username, 
                Limits.USER_USERNAME_MAX, required=True
            ),
            "password": Validator.validate_string(
                "Contraseña", password, 
                Limits.USER_PASSWORD_MAX, required=True
            ),
            "email": Validator.validate_string(
                "Email", email, 
                Limits.USER_EMAIL_MAX, required=True
            ),
            "role": Validator.validate_string(
                "Rol", role, 
                Limits.USER_ROLE_MAX, required=True
            ),
        }