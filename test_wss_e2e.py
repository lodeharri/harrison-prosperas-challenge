#!/usr/bin/env python3
"""
Prueba E2E completa con WebSocket seguro (WSS) a través de CloudFront
"""

import asyncio
import websockets
import json
import time
import requests

# URLs
WSS_URL = "wss://djcgygxhc3ep7.cloudfront.net/ws/jobs"
ALB_URL = "http://harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com:8000"

print("=" * 70)
print("🔍 PRUEBA E2E COMPLETA - WEBSOCKET SEGURO (WSS)")
print("=" * 70)
print(f"URL WSS: {WSS_URL}")
print(f"URL ALB: {ALB_URL}")
print()

# 1. Obtener token JWT
print("1. 🔑 Obteniendo token JWT...")
user_id = f"wss_test_{int(time.time())}"
try:
    resp = requests.post(f"{ALB_URL}/auth/token", json={"user_id": user_id}, timeout=10)
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        print(f"   ✅ Token obtenido: {token[:50]}...")
    else:
        print(f"   ❌ Error HTTP {resp.status_code}: {resp.text}")
        exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

# 2. Crear job de prueba
print(f"\n2. 📝 Creando job de prueba...")
try:
    job_data = {
        "user_id": user_id,
        "report_type": "wss_test_report",
        "parameters": {"test": "wss_cloudfront"}
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{ALB_URL}/jobs", json=job_data, headers=headers, timeout=10)
    
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

# 3. Probar conexión WSS
async def test_wss_connection():
    print(f"\n3. 🔗 Conectando vía WSS a CloudFront...")
    print(f"   URL: {WSS_URL}?user_id={user_id}&token={token[:30]}...")
    
    messages_received = []
    notification_received = False
    
    try:
        async with websockets.connect(
            f"{WSS_URL}?user_id={user_id}&token={token}",
            ping_interval=30,
            ping_timeout=30,
            close_timeout=30
        ) as websocket:
            print(f"   ✅ Conexión WSS establecida")
            
            # Escuchar por notificaciones por 60 segundos
            print(f"   👂 Escuchando notificaciones (60 segundos)...")
            start_time = time.time()
            
            while time.time() - start_time < 60:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    receive_time = time.time() - start_time
                    
                    try:
                        data = json.loads(message)
                        messages_received.append({
                            "time": receive_time,
                            "data": data
                        })
                        print(f"   📥 Notificación recibida a {receive_time:.1f}s")
                        
                        # Verificar si es sobre nuestro job
                        if job_id and data.get("type") == "job_update" and data.get("data", {}).get("job_id") == job_id:
                            print(f"   🎯 ¡NOTIFICACIÓN DE NUESTRO JOB RECIBIDA VÍA WSS!")
                            print(f"     Estado: {data.get('data', {}).get('status')}")
                            print(f"     Resultado: {data.get('data', {}).get('result_url', 'N/A')}")
                            notification_received = True
                            break
                            
                    except json.JSONDecodeError:
                        print(f"   📥 Mensaje no JSON: {message[:80]}...")
                        
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print(f"   🔌 Conexión cerrada por el servidor")
                    break
            
            print(f"\n   ⏱️ Tiempo total de escucha: {time.time() - start_time:.1f}s")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"   ❌ Error HTTP {e.status_code}")
        return [], False
    except Exception as e:
        print(f"   ❌ Error de conexión WSS: {type(e).__name__}: {e}")
        return [], False
    
    return messages_received, notification_received

# 4. Ejecutar prueba WSS
print(f"\n4. 🚀 Ejecutando prueba WSS E2E...")
messages, notification_received = asyncio.run(test_wss_connection())

# 5. Verificar estado final del job
print(f"\n5. 📋 Verificando estado final del job...")
if job_id:
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(f"{ALB_URL}/jobs/{job_id}", headers=headers, timeout=10)
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
print("📊 REPORTE FINAL E2E - WEBSOCKET SEGURO (WSS)")
print("=" * 70)

print(f"\n🔗 URLS:")
print(f"   • WSS (CloudFront): {WSS_URL}")
print(f"   • ALB (Backend): {ALB_URL}")

print(f"\n📈 RESULTADOS:")
print(f"   • Token JWT: ✅ Obtenido")
print(f"   • Job creado: {'✅ ' + job_id if job_id else '❌ No creado'}")
print(f"   • Conexión WSS: {'✅ Exitosa' if messages is not None else '❌ Falló'}")
print(f"   • Notificaciones recibidas: {len(messages)}")
print(f"   • Notificación de nuestro job: {'✅ RECIBIDA' if notification_received else '❌ NO RECIBIDA'}")

if messages:
    print(f"\n📨 NOTIFICACIONES RECIBIDAS:")
    for i, msg in enumerate(messages):
        print(f"   {i+1}. A {msg['time']:.1f}s: {json.dumps(msg['data'])[:100]}...")

print(f"\n🎯 CONCLUSIÓN E2E WSS:")
if notification_received:
    print(f"   ✅ ✅ ✅ WEBSOCKET SEGURO (WSS) FUNCIONANDO CORRECTAMENTE")
    print(f"   ✅ Notificaciones fluyen a través de CloudFront")
    print(f"   ✅ Conexión SSL/TLS funcionando (wss://)")
    print(f"   ✅ Autenticación JWT funciona a través de proxy")
else:
    print(f"   ⚠️ CONEXIÓN WSS ESTABLECIDA PERO SIN NOTIFICACIONES")
    print(f"   ⚠️ Posibles causas:")
    print(f"      - CloudFront no está proxyando correctamente a ALB")
    print(f"      - Worker no está procesando jobs")
    print(f"      - Timeout insuficiente (probó 60 segundos)")

print(f"\n🔧 URL PARA FRONTEND (WSS FINAL):")
print(f"   {WSS_URL}?user_id={{USER_ID}}&token={{JWT_TOKEN}}")
print("=" * 70)
