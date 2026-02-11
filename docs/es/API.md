# Documentación de la API

## Introducción

La API REST de StockManager proporciona endpoints JSON para todas las operaciones de inventario, ventas y estadísticas. Está diseñada principalmente para ser consumida por el frontend de la aplicación, pero puede ser utilizada por clientes externos que mantengan una sesión válida.

**Base Path:** `/api`

**Formato:** JSON (requests y responses)

**Autenticación:** Basada en sesiones de Flask (cookies)

## Autenticación y Autorización

### Autenticación

La mayoría de endpoints requieren una sesión activa de usuario. La autenticación se valida mediante el helper `require_auth()` que verifica la presencia de `session["user_id"]`.

**Excepción:** `GET /api/health` no requiere autenticación.

**Respuesta sin autenticación:**
```json
{
  "error": "No autorizado"
}
```
**Status Code:** `401 Unauthorized`

### Autorización por Roles

Algunos endpoints están restringidos por rol de usuario:

- **Administrador (`admin`)**: Acceso completo a todas las operaciones
- **Vendedor (`user`)**: Solo lectura de productos y registro de ventas

Para más detalles sobre roles, consulta [SECURITY_ROLES.md](SECURITY_ROLES.md).

## Códigos de Estado HTTP

| Código | Significado |
|--------|-------------|
| `200` | Operación exitosa |
| `201` | Recurso creado exitosamente |
| `400` | Petición inválida (validación fallida) |
| `401` | No autenticado (sesión inválida) |
| `403` | Permiso denegado (rol insuficiente) |
| `404` | Recurso no encontrado |
| `500` | Error interno del servidor |

## Endpoints Principales

Ver la [documentación completa de endpoints](API_old.md) para detalles adicionales, o consultar los docstrings en [api/API.py](../../api/API.py) directamente en el código fuente.

### Health Check

- **GET /api/health** - Verificación de estado del servidor (no requiere auth)

### Productos

- **GET /api/products_all** - Lista todos los productos (incluye deshabilitados)
- **GET /api/products** - Lista productos activos
- **GET /api/products/<id>** - Obtiene un producto por ID
- **POST /api/products** - Crea nuevo producto (requiere rol admin)
- **PUT /api/products/<id>** - Actualiza producto (requiere rol admin)
- **DELETE /api/products/<id>** - Deshabilita producto (requiere rol admin)

### Ventas

- **POST /api/sales** - Registra venta simple por código de barras
- **POST /api/sales/bulk** - Registra venta múltiple
- **GET /api/sales** - Lista historial de ventas
- **GET /api/sales/<id>** - Obtiene detalles de venta

### Estadísticas

- **GET /api/stats** - Estadísticas del dashboard
- **GET /api/metrics** - Métricas detalladas de negocio

### Búsqueda

- **GET /api/items?q=<term>** - Búsqueda rápida para autocompletado

## Ejemplos de Uso

### JavaScript (Frontend)

```javascript
// Obtener productos
fetch('/api/products?search=laptop')
  .then(r => r.json())
  .then(data => console.log(data));

// Registrar venta
fetch('/api/sales', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    barcode: '123456',
    quantity: 2
  })
})
.then(r => r.json())
.then(data => console.log(data));
```

### Python (Requests)

```python
import requests

session = requests.Session()
session.post('http://localhost:5000/login', data={
    'user': 'admin',
    'password': 'password'
})

response = session.get('http://localhost:5000/api/products')
products = response.json()
```

### cURL

```bash
# Health check
curl http://localhost:5000/api/health

# Obtener productos (con sesión)
curl -b cookies.txt http://localhost:5000/api/products
```

## Notas de Desarrollo

1. **Sesiones:** La API usa sesiones de Flask con cookies
2. **Validación:** Todos los inputs son validados exhaustivamente
3. **Transacciones:** Las ventas son atómicas (todo o nada)
4. **Testing:** Usa DevTools del navegador para inspeccionar requests/responses
5. **Documentación Completa:** Consulta los docstrings en el código fuente para detalles exactos de cada endpoint
