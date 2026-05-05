from data.limits import Limits
from data.roles import ROLES

class ValidationError(Exception):
    """Excepción para errores de validación."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class Validator:
    """
    Validador modular para campos de entrada.
    
    Uso:
        Validator.validate_string("nombre", value, Limits.ITEM_NAME_MAX)
        Validator.validate_number("cantidad", value, max_val=Limits.ITEM_QUANTITY_MAX)
    """
    
    @staticmethod
    def validate_string(field: str, value: str, max_length: int, required: bool = True) -> str:
        """
        Valida un campo de texto.
        
        Args:
            field: Nombre del campo (para mensajes de error)
            value: Valor a validar
            max_length: Longitud máxima permitida
            required: Si el campo es obligatorio
        
        Returns:
            str: Valor limpio (stripped)
        
        Raises:
            ValidationError: Si la validación falla
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
        Valida un campo numérico.
        
        Args:
            field: Nombre del campo
            value: Valor a validar
            min_val: Valor mínimo permitido
            max_val: Valor máximo permitido
            allow_float: Si permite decimales
            required: Si es obligatorio
        
        Returns:
            int|float: Valor validado
        
        Raises:
            ValidationError: Si la validación falla
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
    """Validador específico para productos."""
    
    @staticmethod
    def validate(barrs_code, description, name, quantity, min_quantity, price, expiration_date, status) -> dict:
        """
        Valida todos los campos de un producto.
        
        Returns:
            dict: Campos validados y limpios
        
        Raises:
            ValidationError: Si algún campo no es válido
        """
        return {
            "barrs_code": Validator.validate_string(
                "Código de barras", barrs_code, 
                Limits.ITEM_BARCODE_MAX, required=True
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
            "expiration_date": Validator.validate_string(
                "Fecha de expiración", expiration_date, 
                Limits.ITEM_EXPIRATION_DATE_MAX, required=False
            ),
            "status": Validator.validate_number(
                "Estado", status, 
                0, max_val=1, required=True
            ),
        }


class UserValidator:
    """Validador específico para usuarios."""
    
    @staticmethod
    def validate_custom(**fields) -> dict:
        """
        Valida solo los campos que vienen.
        
        Uso:
            UserValidator.validate(username="y", password="pass")
            UserValidator.validate(email="x@y.com", role="admin")
        """
        
        validated = {}
        for field, value in fields.items():
            if field.lower() == "username":
                validated["username"] = Validator.validate_string(
                    "Usuario", value, 
                    Limits.USER_USERNAME_MAX, required=True
                )
            elif field.lower() == "password":
                validated["password"] = Validator.validate_string(
                    "Contraseña", value, 
                    Limits.USER_PASSWORD_MAX, required=True
                )
            elif field.lower() == "email":
                validated["email"] = UserValidator.validate_email(value)
            elif field.lower() == "role":
                validated["role"] = RoleValidator.validate_name(value)
            else:
                raise ValidationError(field, "Campo no reconocido")
        return validated
    
    @staticmethod
    def validate_email(email) -> str:
        """Valida el formato de un email."""
        email = Validator.validate_string("Email", email, Limits.USER_EMAIL_MAX)
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValidationError("Email", "Formato de email inválido")
        return email
    
    @staticmethod
    def validate(username, password, email, role=ROLES.VENDOR) -> dict:
        """
        Valida todos los campos de un usuario.
        
        Returns:
            dict: Campos validados y limpios
        
        Raises:
            ValidationError: Si algún campo no es válido
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
            "role": RoleValidator.validate_name(role),
        }
        
class RoleValidator:
    """Validador específico para roles."""
    namespaces = [ROLES.ROOT, ROLES.ADMIN, ROLES.VENDOR]
    permissions = {
        "root": "all",
        "admin": "manage_items, manage_users, view_metrics",
        "vendedor": "record_sales, view_own_metrics"
    }

    @staticmethod
    def validate_name(name) -> str:
        """Valida el nombre de un rol."""
        if name.lower() not in RoleValidator.namespaces:
            raise ValidationError("Nombre del rol", "Rol no válido")
        return name
    
    @staticmethod
    def validate_permissions(permissions) -> str:
        """Valida los permisos de un rol."""
        return Validator.validate_string(
            "Permisos", permissions, 
            Limits.ROLE_PERMISSIONS_MAX, required=True
        )

    @staticmethod
    def validate(name, permissions) -> dict:
        """
        Valida todos los campos de un rol.
        
        Returns:
            dict: Campos validados y limpios
        
        Raises:
            ValidationError: Si algún campo no es válido
        """
        return {
            "name": RoleValidator.validate_name(name),
            "permissions": Validator.validate_string(
                "Permisos", permissions, 
                Limits.ROLE_PERMISSIONS_MAX, required=True
            ),
        }