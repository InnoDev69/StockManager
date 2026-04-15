#!/usr/bin/env python3
"""
Script para generar 50 ventas de prueba usando la API REST.
Uso: python3 generate_sales.py
"""

import requests
import random
import sys
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "http://localhost:5000"
USERNAME = "Dummy"
PASSWORD = "123456"
NUM_SALES = 50

class SalesGenerator:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        
        # Configurar sesión con reintentos
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Retry strategy
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.username = username
        self.password = password
        self.products = []
        
    def test_connection(self):
        """Verifica que el servidor esté accesible."""
        print("🔌 Verificando conexión al servidor...")
        try:
            response = self.session.get(f"{self.base_url}/", timeout=5)
            print(f"✓ Servidor accesible: {self.base_url}")
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def login(self):
        """Inicia sesión en la aplicación."""
        print("🔐 Iniciando sesión...")
        
        try:
            # Primero: GET al login para obtener cookies/tokens iniciales
            login_page = self.session.get(f"{self.base_url}/login", timeout=5)
            print(f"   GET /login: {login_page.status_code}")
            
            # Segundo: POST con credenciales
            login_url = f"{self.base_url}/login"
            payload = {
                "user": self.username,
                "password": self.password
            }
            
            response = self.session.post(
                login_url, 
                data=payload,
                allow_redirects=True,
                timeout=5
            )
            print(f"   POST /login: {response.status_code}")
            print(f"   Cookies establecidas: {len(self.session.cookies)}")
            
            # Tercero: Verificar cada cookie
            for cookie in self.session.cookies:
                print(f"      - {cookie.name}: {cookie.value[:20]}...")
            
            # Cuarto: Intentar acceso a endpoint protegido
            test_url = f"{self.base_url}/api/stats"
            test_response = self.session.get(test_url, timeout=5)
            print(f"   GET /api/stats: {test_response.status_code}")
            
            # Verificar que sea JSON y no HTML
            content_type = test_response.headers.get('Content-Type', '')
            is_json = 'application/json' in content_type
            print(f"   Content-Type: {content_type[:50]}...")
            
            if test_response.status_code == 200 and is_json:
                print(f"✓ Sesión iniciada como: {self.username}")
                return True
            elif test_response.status_code == 401:
                print(f"❌ Unauthorized (401) - Credenciales inválidas")
                return False
            else:
                print(f"❌ Status {test_response.status_code}, no es JSON")
                return False
                
        except Exception as e:
            print(f"❌ Error en login: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_products(self):
        """Obtiene la lista de productos del sistema."""
        print("📦 Obteniendo productos...")
        
        try:
            response = self.session.get(f"{self.base_url}/api/products", timeout=10)
            print(f"   Status: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type')}")
            print(f"   Tamaño: {len(response.text)} caracteres")
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}")
                return False
            
            # Detectar si es HTML
            if 'text/html' in response.headers.get('Content-Type', ''):
                print(f"❌ Recibí HTML (sesión perdida o no autenticado)")
                print(f"   Primeros 200 caracteres: {response.text[:200]}")
                return False
            
            # Parsear JSON
            data = response.json()
            self.products = data.get("data", [])
            
            if self.products:
                print(f"✓ Se encontraron {len(self.products)} productos")
                print(f"\n   Primer producto (estructura):")
                first_product = self.products[0]
                for key, value in first_product.items():
                    print(f"      {key}: {value} ({type(value).__name__})")
                return True
            else:
                print(f"❌ 'data' vacío o no existe")
                return False
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON inválido: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_sale(self, product, verbose=False):
        """Crea una venta para un producto específico."""
        sales_url = f"{self.base_url}/api/sales"
        
        # Revisado: prevenir randint(1, 0) cuando stock < 1
        stock = product.get("stock", 3)
        max_quantity = min(3, stock) if stock > 0 else 1
        
        try:
            quantity = random.randint(1, max_quantity)
        except ValueError as e:
            if verbose:
                print(f"      ❌ Error en random.randint(1, {max_quantity}): {e}")
                print(f"      Stock del producto: {stock}")
            return False, {"error": f"randint error: stock={stock}"}
        
        payment_method = random.choice(["Efectivo", "Transferencia"])
        
        payload = {
            "barcode": product.get("barcode"),
            "quantity": quantity,
            "payment_method": payment_method
        }
        
        try:
            if verbose:
                print(f"      Payload dict: {payload}")
                print(f"      Payload JSON: {json.dumps(payload)}")
            
            response = self.session.post(
                sales_url,
                json=payload,
                timeout=5
            )
            
            if verbose:
                print(f"      Status: {response.status_code}")
                try:
                    print(f"      Response: {response.json()}")
                except:
                    print(f"      Response: {response.text[:100]}")
            
            if response.status_code == 201:
                return True, response.json()
            else:
                try:
                    error_info = response.json()
                except:
                    error_info = {"error": f"HTTP {response.status_code}: {response.text[:100]}"}
                return False, error_info
        except Exception as e:
            if verbose:
                print(f"      Exception: {e}")
            return False, {"error": str(e)}
    
    def generate_sales(self, num_sales):
        """Genera N ventas aleatorias."""
        if not self.test_connection():
            return False
        
        if not self.login():
            return False
        
        if not self.get_products():
            return False
        
        if not self.products:
            print("❌ No hay productos")
            return False
        
        print(f"\n🔄 Generando {num_sales} ventas...")
        print("-" * 70)
        
        sales_created = 0
        sales_failed = 0
        errors = {}
        
        for i in range(num_sales):
            product = random.choice(self.products)
            # Verbose output para los primeros 3 intentos
            verbose = (i < 3)
            success, error_info = self.create_sale(product, verbose=verbose)
            
            if success:
                sales_created += 1
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"  [{i+1:2d}/{num_sales}] ✓ {product.get('name')}")
            else:
                sales_failed += 1
                error_msg = error_info.get("error", "Unknown error")
                if error_msg not in errors:
                    errors[error_msg] = 0
                errors[error_msg] += 1
                
                if verbose:
                    print(f"  [{i+1:2d}/{num_sales}] ✗ {product.get('name')} - {error_msg}")
        
        print("-" * 70)
        print(f"\n✅ Completado: {sales_created}/{num_sales} ventas creadas")
        print(f"❌ Fallidas: {sales_failed}")
        
        if errors:
            print("\n📋 Errores encontrados:")
            for error, count in errors.items():
                print(f"   - {error}: {count}x")
        
        print("-" * 70)
        
        return sales_created > 0

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║        Generador de Ventas - Stock Manager                     ║")
    print("╚════════════════════════════════════════════════════════════════╝\n")
    
    confirm = input("¿Usar configuración por defecto? (s/n) [s]: ").strip().lower()
    
    if confirm == 'n':
        url = input(f"URL [{BASE_URL}]: ").strip() or BASE_URL
        user = input(f"Usuario [{USERNAME}]: ").strip() or USERNAME
        passwd = input("Contraseña: ").strip() or PASSWORD
        try:
            num = int(input(f"Ventas [{NUM_SALES}]: ") or NUM_SALES)
        except:
            num = NUM_SALES
    else:
        url, user, passwd, num = BASE_URL, USERNAME, PASSWORD, NUM_SALES
    
    print()
    generator = SalesGenerator(url, user, passwd)
    return 0 if generator.generate_sales(num) else 1

if __name__ == "__main__":
    sys.exit(main())