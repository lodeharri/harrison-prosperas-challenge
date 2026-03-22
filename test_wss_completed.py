#!/usr/bin/env python3
"""
Verificar si el job se completó después de la prueba WSS
"""

import requests
import time

ALB_URL = "http://harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com:8000"
JOB_ID = "fa5e4dcf-f738-4a4d-956e-2c627c4e71ed"
USER_ID = "wss_test_1774206524"

print("🔍 Verificando estado del job después de prueba WSS...")
print(f"Job ID: {JOB_ID}")

# Obtener token nuevo
print("\n1. Obteniendo nuevo token...")
resp = requests.post(f"{ALB_URL}/auth/token", json={"user_id": USER_ID}, timeout=10)
if resp.status_code == 200:
    token = resp.json()["access_token"]
    print("✅ Token obtenido")
else:
    print(f"❌ Error obteniendo token: {resp.status_code}")
    exit(1)

# Verificar estado del job
headers = {"Authorization": f"Bearer {token}"}
print("\n2. Verificando estado del job...")

for i in range(5):  # Intentar 5 veces con delay
    try:
        resp = requests.get(f"{ALB_URL}/jobs/{JOB_ID}", headers=headers, timeout=10)
        if resp.status_code == 200:
            job = resp.json()
            status = job["status"]
            print(f"   Intento {i+1}: Estado = {status}")
            
            if status == "COMPLETED":
                print(f"\n🎉 ¡JOB COMPLETADO EXITOSAMENTE!")
                print(f"   Resultado: {job.get('result_url', 'N/A')}")
                print(f"   Actualizado: {job.get('updated_at', 'N/A')}")
                break
            elif status == "FAILED":
                print(f"\n⚠️ Job falló")
                print(f"   Error: {job.get('error_message', 'N/A')}")
                break
        else:
            print(f"   Intento {i+1}: Error HTTP {resp.status_code}")
    except Exception as e:
        print(f"   Intento {i+1}: Error: {e}")
    
    if i < 4:
        time.sleep(10)  # Esperar 10 segundos entre intentos

print("\n📊 RESUMEN FINAL:")
print(f"   • Job ID: {JOB_ID}")
print(f"   • Estado final: {job.get('status', 'DESCONOCIDO') if 'job' in locals() else 'NO VERIFICADO'}")
print(f"   • Worker procesando: {'✅ SÍ' if job.get('status') in ['PROCESSING', 'COMPLETED'] else '❌ NO'}")
print(f"   • WebSocket WSS funcionando: ✅ SÍ (confirmado en prueba anterior)")
