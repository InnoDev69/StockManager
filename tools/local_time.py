from datetime import datetime
import pytz

ZONA = pytz.timezone("America/Argentina/Buenos_Aires")

def localDate():
    """Devuelve la fecha y hora actual en formato 'YYYY-MM-DD HH:MM:SS' para la zona horaria de Buenos Aires."""
    return datetime.now(ZONA).strftime("%Y-%m-%d %H:%M:%S")