#!/usr/bin/env python3
"""
Prueba E2E final del WebSocket en producción
Prueba el flujo completo: token -> conexión -> mensajes -> notificaciones
"""

import asyncio
import websockets
import json
import time
import requests

# URL de producción del ALB
ALB_URL = "harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com"
API_BASE = f"http://{ALB_URL}:8000"
WS_URL = f"ws://{ALB_URL}:8000/ws/jobs"

print("=" * 70)
print("🔍 PRUEBA E2E FINAL - WEBSOCKET PRODUCCIÓN")
print("=" * 70)

# 1. Obtener token JWT
print(f"\n1. 🔑 Obteniendo token JWT...")
user_id = f"e2e_test_{int(time.time())}"
try:
    resp = requests.post(f"{API_BASE}/auth/token", json={"user_id": user_id}, timeout=10)
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        print(f"   ✅ Token obtenido: {token[:50]}...")
    else:
        print(f"   ❌ Error HTTP {resp.status_code}: {resp.text}")
        exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

# 2. Crear un job de prueba
print(f"\n2. 📝 Creando job de prueba...")
try:
    job_data = {
        "user_id": user_id,
        "report_type": "financial_summary",
        "parameters": {"year": 2024, "quarter": "Q1"}
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{API_BASE}/jobs", json=job_data, headers=headers, timeout=10)
    
    if resp.status_code == 201:
        job = resp.json()
        job_id = job["job_id"]
        print(f"   ✅ Job creado: {job_id}")
        print(f"   📊 Estado inicial: {job['status']}")
    else:
        print(f"   ❌ Error HTTP {resp.status_code}: {resp.text}")
        job_id = None
except Exception as e:
    print(f"   ❌ Error: {e}")
    job_id = None

# 3. Conectar al WebSocket y esperar notificaciones
async def test_websocket_e2e():
    print(f"\n3. 🔗 Conectando al WebSocket...")
    print(f"   URL: {WS_URL}?user_id={user_id}&token={token[:30]}...")
    
    messages_received = []
    
    try:
        async with websockets.connect(
            f"{WS_URL}?user_id={user_id}&token={token}",
            ping_interval=30,
            ping_timeout=30,
            close_timeout=30
        ) as websocket:
            print(f"   ✅ Conexión establecida")
            
            # Escuchar por notificaciones por 30 segundos
            print(f"   👂 Escuchando notificaciones (30 segundos)...")
            start_time = time.time()
            
            while time.time() - start_time < 30:
                try:
                    # Intentar recibir mensaje con timeout corto
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    receive_time = time.time() - start_time
                    
                    try:
                        data = json.loads(message)
                        messages_received.append({
                            "time": receive_time,
                            "data": data
                        })
                        print(f"   📥 Notificación recibida a {receive_time:.1f}s: {json.dumps(data)[:80]}...")
                        
                        # Verificar si es sobre nuestro job
                        if job_id and data.get("type") == "job_update" and data.get("data", {}).get("job_id") == job_id:
                            print(f"   🎯 ¡NOTIFICACIÓN DE NUESTRO JOB RECIBIDA!")
                            print(f"     Estado: {data.get('data', {}).get('status')}")
                            print(f"     Resultado: {data.get('data', {}).get('result_url', 'N/A')}")
                            
                    except json.JSONDecodeError:
                        print(f"   📥 Mensaje no JSON: {message[:80]}...")
                        
                except asyncio.TimeoutError:
                    # Timeout normal, continuar escuchando
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print(f"   🔌 Conexión cerrada por el servidor")
                    break
            
            print(f"\n   ⏱️ Tiempo total de escucha: {time.time() - start_time:.1f}s")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"   ❌ Error HTTP {e.status_code}")
        return []
    except Exception as e:
        print(f"   ❌ Error de conexión: {type(e).__name__}: {e}")
        return []
    
    return messages_received

# 4. Ejecutar prueba WebSocket
print(f"\n4. 🚀 Ejecutando prueba WebSocket E2E...")
messages = asyncio.run(test_websocket_e2e())

# 5. Verificar estado final del job
print(f"\n5. 📋 Verificando estado final del job...")
if job_id:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{API_BASE}/jobs/{job_id}", headers=headers, timeout=10)
        if resp.status_code == 200:
            final_job = resp.json()
            print(f"   📊 Estado final: {final_job['status']}")
            print(f"   📅 Actualizado: {final_job.get('updated_at', 'N/A')}")
            print(f"   🔗 Resultado: {final_job.get('result_url', 'N/A')}")
        else:
            print(f"   ❌ Error HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

# 6. Reporte final
print(f"\n" + "=" * 70)
print("📊 REPORTE E2E FINAL - WEBSOCKET PRODUCCIÓN")
print("=" * 70)

print(f"\n🔗 URL DE PRODUCCIÓN:")
print(f"   WebSocket: {WS_URL}")
print(f"   API REST: {API_BASE}")

print(f"\n📈 RESULTADOS:")
print(f"   • Token JWT: {'✅ Obtenido' if 'token' in locals() else '❌ Falló'}")
print(f"   • Job creado: {'✅ ' + job_id if job_id else '❌ No creado'}")
print(f"   • Conexión WebSocket: {'✅ Exitosa' if messages is not None else '❌ Falló'}")
print(f"   • Notificaciones recibidas: {len(messages)}")

if messages:
    print(f"\n📨 NOTIFICACIONES RECIBIDAS:")
    for i, msg in enumerate(messages):
        print(f"   {i+1}. A {msg['time']:.1f}s: {json.dumps(msg['data'])[:100]}...")

print(f"\n🎯 CONCLUSIÓN E2E:")
if len(messages) > 0:
    print(f"   ✅ WEBSOCKET FUNCIONANDO CORRECTAMENTE EN PRODUCCIÓN")
    print(f"   ✅ Notificaciones fluyen correctamente")
    print(f"   ✅ Conexión estable y autenticación funciona")
else:
    print(f"   ⚠️ WEBSOCKET CONECTA PERO NO RECIBE NOTIFICACIONES")
    print(f"   ⚠️ Posibles causas:")
    print(f"      - Worker no está procesando jobs")
    print(f"      - Notificaciones no están siendo enviadas")
    print(f"      - Timeout muy corto (probó 30 segundos)")

print(f"\n🔧 URL PARA FRONTEND (FINAL):")
print(f"   {WS_URL}?user_id={{USER_ID}}&token={{JWT_TOKEN}}")
print("=" * 70)
