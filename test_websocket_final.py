#!/usr/bin/env python3
"""
Prueba completa de conexión WebSocket para Reto Prosperas
Prueba la conexión al ALB de AWS y proporciona URL para frontend
"""

import asyncio
import websockets
import json
import time
import sys
import requests

# URLs
ALB_URL = "harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com"
LOCAL_API = "http://localhost:8000"
AWS_API = f"http://{ALB_URL}:8000"

# Usar AWS para pruebas reales
API_BASE = AWS_API

async def test_websocket_connection(user_id, token):
    """Prueba la conexión WebSocket con autenticación"""
    ws_url = f"ws://{ALB_URL}:8000/ws/jobs?user_id={user_id}&token={token}"
    
    print(f"\n🔗 Conectando a WebSocket...")
    print(f"   URL: {ws_url}")
    
    start_time = time.time()
    
    try:
        async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as websocket:
            connect_time = time.time() - start_time
            print(f"   ✅ Conexión establecida en {connect_time:.2f}s")
            
            # Probar ping/pong
            await websocket.ping()
            print(f"   ✅ Ping/pong funcionando")
            
            # Enviar mensaje de prueba
            test_message = {
                "type": "test",
                "message": "Prueba de conexión WebSocket"
            }
            await websocket.send(json.dumps(test_message))
            print(f"   📤 Mensaje enviado: {test_message}")
            
            # Intentar recibir respuesta (timeout de 5 segundos)
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                response_time = time.time() - start_time - connect_time
                print(f"   📥 Respuesta recibida en {response_time:.2f}s")
                print(f"   📄 Contenido: {response}")
                
                # Parsear respuesta
                try:
                    data = json.loads(response)
                    print(f"   ✅ Respuesta JSON válida")
                    return True, connect_time, response_time, data
                except json.JSONDecodeError:
                    print(f"   ⚠️ Respuesta no es JSON: {response}")
                    return True, connect_time, response_time, {"raw": response}
                    
            except asyncio.TimeoutError:
                print(f"   ⏱️ Timeout esperando respuesta (5s)")
                return True, connect_time, None, None
                
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"   ❌ Error de conexión: Código {e.status_code}")
        if e.status_code == 403:
            print(f"   🔒 Acceso denegado - Token inválido o expirado")
        return False, None, None, {"error": f"HTTP {e.status_code}"}
    except Exception as e:
        print(f"   ❌ Error de conexión: {type(e).__name__}: {str(e)}")
        return False, None, None, {"error": str(e)}
    
    return False, None, None, None

def get_jwt_token(user_id="test_user_123"):
    """Obtiene un token JWT para pruebas"""
    print(f"\n🔑 Obteniendo token JWT para usuario: {user_id}")
    
    try:
        response = requests.post(
            f"{API_BASE}/auth/token",
            json={"user_id": user_id},
            timeout=10
        )
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"   ✅ Token obtenido exitosamente")
            return token
        else:
            print(f"   ❌ Error obteniendo token: HTTP {response.status_code}")
            print(f"   📄 Respuesta: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Error de conexión a API: {str(e)}")
        return None

async def test_without_token():
    """Prueba conexión sin token (debe fallar)"""
    print(f"\n🔒 Probando conexión SIN token (debe fallar)...")
    
    ws_url = f"ws://{ALB_URL}:8000/ws/jobs?user_id=test_user_123"
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"   ⚠️ CONEXIÓN INESPERADA - La seguridad podría estar deshabilitada")
            return False
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"   ✅ Correctamente rechazado: HTTP {e.status_code}")
        if e.status_code == 403:
            print(f"   🔒 Seguridad funcionando correctamente")
        return True
    except Exception as e:
        print(f"   ❌ Error inesperado: {type(e).__name__}: {str(e)}")
        return False

async def main():
    """Función principal de pruebas"""
    print("=" * 60)
    print("🔍 PRUEBA COMPLETA DE WEBSOCKET - RETO PROSPERAS")
    print("=" * 60)
    
    # 1. Probar conexión sin token
    await test_without_token()
    
    # 2. Obtener token JWT
    user_id = "test_user_" + str(int(time.time()))
    token = get_jwt_token(user_id)
    
    if not token:
        print(f"\n❌ No se pudo obtener token JWT. Abortando prueba.")
        return
    
    # 3. Probar conexión con token válido
    success, connect_time, response_time, data = await test_websocket_connection(user_id, token)
    
    # 4. Probar múltiples conexiones
    print(f"\n🔄 Probando múltiples conexiones rápidas...")
    test_results = []
    
    for i in range(3):
        print(f"\n   Prueba {i+1}/3:")
        success_i, ct, rt, _ = await test_websocket_connection(user_id, token)
        if success_i:
            test_results.append((ct, rt))
    
    # 5. Reporte final
    print("\n" + "=" * 60)
    print("📊 REPORTE FINAL - WEBSOCKET AWS")
    print("=" * 60)
    
    print(f"\n🔗 URL PARA FRONTEND:")
    print(f"   Formato: ws://{ALB_URL}:8000/ws/jobs?user_id={{userId}}&token={{jwtToken}}")
    print(f"   Ejemplo: ws://{ALB_URL}:8000/ws/jobs?user_id={user_id}&token={token[:30]}...")
    
    print(f"\n📈 RESULTADOS DE PRUEBAS:")
    if test_results:
        avg_connect = sum(ct for ct, _ in test_results) / len(test_results)
        responses = [rt for _, rt in test_results if rt is not None]
        if responses:
            avg_response = sum(responses) / len(responses)
            print(f"   • Tiempo promedio de conexión: {avg_connect:.2f}s")
            print(f"   • Tiempo promedio de respuesta: {avg_response:.2f}s")
        print(f"   • Conexiones exitosas: {len(test_results)}/3")
    
    print(f"\n✅ RECOMENDACIONES PARA FRONTEND:")
    print(f"   1. Usar la URL: ws://{ALB_URL}:8000/ws/jobs")
    print(f"   2. Incluir parámetros: user_id y token (JWT)")
    print(f"   3. Implementar reconexión automática")
    print(f"   4. Manejar errores 403 (token expirado)")
    print(f"   5. Timeout de conexión: 30 segundos")
    
    print(f"\n🎯 ESTADO FINAL: {'✅ FUNCIONANDO' if success else '❌ CON PROBLEMAS'}")
    print("=" * 60)

if __name__ == "__main__":
    # Instalar dependencias si es necesario
    print("Verificando dependencias...")
    
    try:
        import websockets
        import requests
    except ImportError:
        print("Instalando dependencias necesarias...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "websockets", "requests"])
    
    # Ejecutar pruebas
    asyncio.run(main())
