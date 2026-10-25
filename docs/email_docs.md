# Documentación técnica de `email.py`

## 1. Visión General del Módulo

Implementa el envío de correo electrónico mediante SMTP sobre TLS implícito y expone una instancia global `email_sender` configurada desde variables de entorno.

El diseño combina **Service Object** (`EmailSender`) y una instancia compartida tipo **Singleton de módulo**. La configuración se carga al importar el módulo, con una ruta especial para bundles de PyInstaller.

## 2. Dependencias

### Biblioteca estándar

- `smtplib`: conexión, autenticación y envío SMTP.
- `email.mime.text.MIMEText`: construcción de mensajes de texto.
- `sys`: detección de bundles y acceso a `_MEIPASS`.
- `os`: variables de entorno y rutas.

### Terceros

- `python-dotenv.load_dotenv`.

### Internas

- `miscellaneous.logger.logger`.

## 3. API Pública

### `EmailSender`

```python
class EmailSender:
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
    ) -> None:
        """Configura un cliente SMTP.

        Args:
            smtp_server: Host SMTP.
            smtp_port: Puerto del servidor SMTP.
            username: Cuenta autenticada y dirección remitente.
            password: Credencial SMTP.
        """

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
    ) -> None:
        """Envía un correo de texto.

        Args:
            recipient_email: Dirección del destinatario.
            subject: Asunto del mensaje.
            body: Contenido textual.

        Returns:
            ``None``. Los errores se registran y no se propagan en la
            implementación actual.
        """
```

### `email_sender`

```python
email_sender: EmailSender
```

Se construye con `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME` y `SMTP_PASSWORD`.

## 4. Consideraciones de Ingeniería

- **Complejidad:** construcción del mensaje es `O(n)` en la longitud del cuerpo. La conexión y el envío dependen de red; el coste de CPU local es aproximadamente lineal en el tamaño del mensaje.
- **Rendimiento:** abre y autentica una conexión por correo. Para volumen alto conviene un pool, una cola asíncrona o un worker dedicado con reintentos y backoff.
- **Seguridad:** la contraseña se mantiene en memoria en el objeto global y no debe registrarse. La configuración debe provenir de un gestor de secretos. `SMTP_SSL` protege transporte, pero validar certificados y usar configuración explícita de TLS.
- **Configuración:** `int(os.getenv('SMTP_PORT'))` falla durante la importación si la variable falta o no es numérica. Es preferible validar configuración al arranque y producir un error operativo claro.
- **Errores:** se captura `Exception` y se oculta el fallo al llamador. Esto puede hacer que una notificación crítica parezca enviada. Recomiéndase una excepción de dominio, un resultado explícito o una política de reintentos.
- **API SMTP:** `SMTP_SSL` ya conecta durante la construcción en muchas versiones; llamar después a `connect` puede ser redundante o producir errores. Debe probarse con el servidor objetivo y simplificarse a una sola conexión.
- **Concurrencia:** compartir una instancia es seguro mientras cada envío use una conexión local, como ocurre aquí. El objeto no debe convertirse posteriormente en una conexión SMTP persistente sin sincronización.
- **Casos límite:** destinatarios o credenciales `None` fallarán al enviar; no se valida formato de email; `MIMEText` usa una codificación implícita. Deben validarse entradas y fijarse charset UTF-8 si se admiten caracteres internacionales.

## 5. Ejemplo de Uso

```python
from miscellaneous.email import email_sender

email_sender.send_email(
    recipient_email="admin@example.com",
    subject="Alerta de inventario",
    body="El producto SKU-001 alcanzó el stock mínimo.",
)
```
