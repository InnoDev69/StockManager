# Actualizador + licencias en Stockly: puesta en marcha

## 1. Qué trae
| Ruta | Qué es |
|---|---|
| `stockly_updater/` | Paquete compartido: cliente de GitHub, manifiesto firmado, instalador con rollback, el ayudante `update.exe` (`helper.py`), `update.spec`, `sign_release.py` (CI) y `bootstrap_keys.py` (claves) |
| `core/updater/` | Servicio de actualizaciones dentro de Stockly + rutas `/api/updates/status\|check\|apply` |
| `core/licensing/` | Licencias: manager, rutas `/api/license`, `instance.py` (se activan solas al haber clave pública y librería) |
| `core/version.py` | Fuente única de versión (el CI la reemplaza con el tag) |
| `templates/system/_license_updates.html`, `static/js/core/updates-tab.js` | Pestaña "Licencia y actualizaciones" de Ajustes (admin/root) |
| **Modificados** | `core/api/__init__.py`, `core/stockly.py`, `main.py`, `templates/system/settings.html`, `requirements.txt`, `build.spec`, `.github/workflows/build.yml` |

## 2. Aplicarlo al repo
```bash
git checkout -b feat/actualizador-licencias
git apply --check stockly-fase3.patch && git apply stockly-fase3.patch   # o --3way si hay conflictos
pip install -r requirements.txt
pip install -e ../stockly-license          # librería de licencias (tu copia local)
pytest stockly_updater core/updater core/licensing && pytest
```
Ojo: tu `.gitignore` ignora `tools/*`, `data/*` y `backup/*`; por eso las herramientas del actualizador viven en `stockly_updater/`. Antes de commitear mirá `git status`: no deben entrar `.env`, la BD ni backups.

## 3. Puesta en marcha (en este orden)
1. **Claves.** Desde la raíz del repo: `python -m stockly_updater.bootstrap_keys`
   - Crea las claves de licencias en `~/.stockly-license/keys` y las de releases en `~/.stockly-release-keys`.
   - Pega las dos claves **públicas** en `core/licensing/public_keys.py` y `stockly_updater/release_keys.py`.
   - Es seguro repetirlo: reutiliza claves existentes y no duplica nada.
   - Guardá una copia de ambos `private.key` en tu gestor de contraseñas.
2. **Librería de licencias en GitHub.** En el repo `stockly-license`: commit, `git tag -a v0.2.0 -m "Licencias personalizadas"`, `git push --tags`. Tiene que ser un repo privado `InnoDev69/stockly-license`.
3. **Secretos del repo StockManager** (Settings → Secrets and variables → Actions):
   - `RELEASE_SIGNING_KEY`: `gh secret set RELEASE_SIGNING_KEY < ~/.stockly-release-keys/private.key`
   - `LICENSE_LIB_TOKEN`: token fine-grained con permiso de lectura de *Contents* sobre `stockly-license`. Sin él, el release sale con las licencias desactivadas (la app funciona igual).
4. **Commit y push** de la rama; revisá que el CI pase.
5. **Release:** `git tag -a v1.9.0 -m "..."` y `git push --tags`. El CI compila Stockly y `update.exe`, hace el autochequeo, arma el zip (con `update.exe` y `version.json` adentro) y firma el release.
6. **Verificá el release en GitHub:** debe tener 3 archivos: `Stockly-windows-x64.zip`, `manifest.json` y `manifest.json.sig`.
7. **Clientes nuevos:** instalan el zip. Abren Ajustes → Licencia y actualizaciones, te pasan el código de equipo y vos emitís: `stockly-license issue --plan base --customer "Cliente" --machine XXXX-XXXX-XXXX-XXXX --out licencia.stk`. Personalizada: sumá `--feature multicaja=3 --updates-months 24 --plan-label "Convenio"`.
8. **Clientes actuales (v1.8.5):** no tienen el ayudante nuevo, así que esa primera actualización es con el actualizador viejo o a mano (probalo antes en una instalación de prueba). Conviene emitirles una licencia antes de publicar: sin licencia arrancan 30 días de prueba y después se les bloquean las actualizaciones (vender y exportar siguen funcionando).

## 4. Dónde vive cada cosa
| Qué | Dónde |
|---|---|
| Código de Stockly | Tu PC → GitHub `InnoDev69/StockManager` (público: el actualizador consulta la API sin autenticarse) |
| Librería `stockly-license` | GitHub (privado) + instalada en tu PC; con ella emitís licencias |
| Claves privadas, `plans.json`, `issued.jsonl` | Solo en tu PC (`~/.stockly-license/keys`, `~/.stockly-release-keys`) + gestor de contraseñas. **Nunca en git** |
| Claves públicas | En el código (`public_keys.py`, `release_keys.py`) |
| `RELEASE_SIGNING_KEY`, `LICENSE_LIB_TOKEN` | Secretos de GitHub Actions |
| Releases firmados | GitHub Releases (automático al subir un tag `vX.Y.Z`) |
| Instalación del cliente | Carpeta `stockly/` (`stockly.exe`, `update.exe`, `version.json`) |
| Datos del cliente (BD, licencia, prueba, cache) | `%APPDATA%\StockManager\data` o `~/.stock_manager/data`; no se tocan al actualizar |
| Servidor CasaOS | No interviene. Más adelante: servidor de licencias con activación online |

## 5. Cómo se actualiza (incluido el propio ayudante)
1. Stockly consulta GitHub (cache de 4 h con ETag), compara con `core/version.py` y mira `updates_until` de la licencia contra la fecha del release.
2. "Actualizar ahora" lanza `update --apply …` y cierra Stockly (cierre ordenado; si no cierra en 10 s, se fuerza).
3. El ayudante se copia a una carpeta temporal y se relanza desde ahí: así el `update.exe` instalado se reemplaza junto con todo lo demás.
4. Verifica la firma del manifiesto y el hash y tamaño del paquete; extrae de forma segura; reemplaza la carpeta dejando `stockly.old`; si algo falla, restaura sola. Reabre Stockly; en el arranque siguiente se borra `stockly.old`.
5. Sin firma, sin claves embebidas o con el paquete alterado: no instala y se conserva la instalación.

## 6. Límites y pendientes
- **El bloqueo por licencia es de cortesía:** el zip del release es público; quien sepa puede bajarlo a mano. Para un bloqueo real habría que servir los releases desde tu servidor.
- La seguridad depende de la clave privada de releases: solo como secreto del CI. Para rotarla, volvé a correr `bootstrap_keys` con otra carpeta de claves: la vieja queda en la lista hasta que todos actualicen.
- La carpeta de instalación necesita permisos de escritura (no sirve en `Program Files` sin administrador).
- El CI solo genera el paquete de Windows; el código ya soporta `.tar.gz` para Linux.
- **Ya existía (no lo toqué):** `build.spec` empaqueta `.env` y el CI lo crea con tus credenciales SMTP, así que esa contraseña viaja dentro de cada zip publicado. Conviene rotarla y sacar las credenciales del paquete. Además `settings_api.py` usa `require_permission("SETTINGS_MANAGE")` en mayúsculas pero `PERMS.SETTINGS_MANAGE` vale `"settings_manage"`.
- No se pudo probar en Windows real ni contra GitHub (mi entorno no tiene red): el primer release conviene probarlo en una instalación de prueba.
