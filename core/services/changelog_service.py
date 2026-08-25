# stockly/changelog_notice.py
import json
import ssl
import urllib.request

import certifi

from core.services import cache_service
from miscellaneous import logger

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

REPO_OWNER = "InnoDev69"
REPO_REPO = "StockManager"

def check_and_get_cache() -> list[str]:
    if cached := cache_service.get("changelogs"):
        logger.info("Changelogs obtenidos desde cache", source="CHANGELOG_SERVICE")
        return cached
    else:
        logger.info("No hay changelogs en cache", source="CHANGELOG_SERVICE")
        return None
    
def get_changelogs_from_github() -> list[str]:
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_REPO}/releases"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Stockly-App"},
    )
    with urllib.request.urlopen(req, timeout=8, context=SSL_CONTEXT) as resp:
        data = json.loads(resp.read().decode())
    changelogs = []
    for release in data:
        if "body" in release and release["body"]:
            changelogs.append(release["body"])
    cache_service.set("changelogs", changelogs, ttl=86400)  # cache por 24 horas
    logger.info("Changelogs obtenidos desde GitHub y cacheados", source="CHANGELOG_SERVICE")
    return changelogs

def fetch_changelog() -> list[str]:
    """Obtiene todos los changelogs de las releases de GitHub y devuelve una lista con todos los changelogs."""
    if cached := check_and_get_cache():
        return cached
    else:
        try:
            return get_changelogs_from_github()
        except Exception as e:
            logger.error(f"Error al obtener changelogs: {e}", source="CHANGELOG_SERVICE")
            return []