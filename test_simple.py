#!/usr/bin/env python3
"""
Script simple para probar WebSocket y API
"""

import requests
import json
import time

# URLs
API_URL = "https://geqa4nilp0.execute-api.us-east-1.amazonaws.com/prod"
WS_URL = (
    "ws://harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com:8000/ws/jobs"
)


def test_api():
    """Probar API endpoints básicos"""
    print("=== PRUEBAS DE API ===")

    # 1. Health check
    print("1. Health check:")
    try:
        resp = requests.get(f"{API_URL}/health", timeout=10)
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.text}")
    except Exception as e:
        print(f"   Error: {e}")

    # 2. Obtener token
    print("\n2. Obtener token JWT:")
    try:
        resp = requests.post(
            f"{API_URL}/auth/token", json={"user_id": "test-user-123"}, timeout=10
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            token_data = resp.json()
            token = token_data.get("access_token")
            print(f"   Token obtenido: {token[:30]}...")
            return token
        else:
            print(f"   Error: {resp.text}")
    except Exception as e:
        print(f"   Error: {e}")

    return None


def test_job_creation(token):
    """Probar creación de job"""
    print("\n=== CREACIÓN DE JOB ===")

    headers = {"Authorization": f"Bearer {token}"}
    job_data = {
        "report_type": "sales_summary",
        "date_range": {"start": "2024-01-01", "end": "2024-01-31"},
        "format": "csv",
    }

    try:
        print("Creando job...")
        resp = requests.post(
            f"{API_URL}/jobs", json=job_data, headers=headers, timeout=10
        )
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            job = resp.json()
            print(f"Job creado exitosamente:")
            print(f"  Job ID: {job.get('job_id')}")
            print(f"  Status: {job.get('status')}")
            print(f"  Created at: {job.get('created_at')}")
            return job.get("job_id")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Error creando job: {e}")

    return None


def test_job_list(token):
    """Listar jobs del usuario"""
    print("\n=== LISTADO DE JOBS ===")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(f"{API_URL}/jobs", headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("jobs", [])
            total = data.get("total", 0)
            print(f"Total jobs: {total}")

            for i, job in enumerate(jobs[:5]):  # Mostrar primeros 5
                print(f"\nJob {i + 1}:")
                print(f"  ID: {job.get('job_id')}")
                print(f"  Status: {job.get('status')}")
                print(f"  Type: {job.get('report_type')}")
                print(f"  Created: {job.get('created_at')}")
                if job.get("status") == "COMPLETED":
                    print(f"  Result URL: {job.get('result_url', 'N/A')}")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Error listando jobs: {e}")


def test_worker_status():
    """Verificar si el worker está activo"""
    print("\n=== VERIFICACIÓN DE WORKER ===")

    # Verificar jobs recientes
    print("1. Verificando jobs recientes...")

    # Primero obtener token
    try:
        resp = requests.post(
            f"{API_URL}/auth/token", json={"user_id": "test-user-123"}, timeout=10
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"}

            # Listar jobs
            resp = requests.get(f"{API_URL}/jobs", headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get("jobs", [])

                print(f"Jobs encontrados: {len(jobs)}")

                # Analizar estados
                status_counts = {}
                for job in jobs:
                    status = job.get("status", "UNKNOWN")
                    status_counts[status] = status_counts.get(status, 0) + 1

                print("Distribución de estados:")
                for status, count in status_counts.items():
                    print(f"  {status}: {count}")

                # Verificar si hay jobs en PROCESSING
                processing_jobs = [j for j in jobs if j.get("status") == "PROCESSING"]
                if processing_jobs:
                    print(f"\n⚠️  Hay {len(processing_jobs)} job(s) en PROCESSING")
                    print("   El worker podría estar ocupado")
                else:
                    print("\n✓ No hay jobs en PROCESSING")

            else:
                print(f"Error listando jobs: {resp.status_code}")
        else:
            print(f"Error obteniendo token: {resp.status_code}")
    except Exception as e:
        print(f"Error verificando worker: {e}")


def main():
    """Función principal"""
    print("🚀 PRUEBAS DEL SISTEMA RETO PROSPERAS")
    print(f"API: {API_URL}")
    print(f"WebSocket: {WS_URL}")
    print("=" * 60)

    # Probar API
    token = test_api()

    if token:
        # Listar jobs existentes
        test_job_list(token)

        # Verificar estado del worker
        test_worker_status()

        # Crear nuevo job automáticamente
        print("\n" + "=" * 60)
        print("Creando nuevo job para prueba...")
        job_id = test_job_creation(token)
        if job_id:
            print(f"\n✅ Job creado: {job_id}")
            print("\nPara probar WebSocket manualmente:")
            print(f"1. Conectar a: {WS_URL}?user_id=test-user-123&token={token}")
            print(f"2. Esperar notificación para job: {job_id}")
            print("\nEl worker procesa jobs cada ~30 segundos")

            # También mostrar cómo probar con wscat
            print("\nComando para probar con wscat:")
            print(f"wscat -c '{WS_URL}?user_id=test-user-123&token={token}'")

    print("\n" + "=" * 60)
    print("✅ Pruebas completadas")


if __name__ == "__main__":
    main()
