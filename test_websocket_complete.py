#!/usr/bin/env python3
"""
Script de prueba completo para WebSocket del sistema Reto Prosperas.

Este script prueba:
1. Obtención de token JWT de la API REST
2. Conexión WebSocket con autenticación
3. Envío y recepción de mensajes
4. Manejo de diferentes escenarios
"""

import asyncio
import json
import time
import aiohttp
import websockets
from typing import Dict, Any, Optional
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuración
API_BASE_URL = "http://localhost:8000"  # URL local de la API
WS_URL = (
    "ws://harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com:8000/ws/jobs"
)
TEST_USER_ID = "test_user_123"
TEST_USER_ID_2 = "test_user_456"


class WebSocketTester:
    """Clase para probar conexiones WebSocket."""

    def __init__(self, api_base_url: str, ws_url: str):
        self.api_base_url = api_base_url
        self.ws_url = ws_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_jwt_token(self, user_id: str) -> str:
        """Obtiene un token JWT de la API REST."""
        try:
            url = f"{self.api_base_url}/auth/token"
            payload = {"user_id": user_id}

            logger.info(f"Obteniendo token JWT para usuario: {user_id}")
            logger.info(f"URL: {url}")

            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    token = data.get("access_token")
                    if token:
                        logger.info(
                            f"Token obtenido exitosamente (longitud: {len(token)})"
                        )
                        logger.info(f"Token (primeros 50 chars): {token[:50]}...")
                        return token
                    else:
                        raise Exception("No se encontró access_token en la respuesta")
                else:
                    text = await response.text()
                    raise Exception(
                        f"Error al obtener token: {response.status} - {text}"
                    )
        except Exception as e:
            logger.error(f"Error obteniendo token JWT: {e}")
            raise

    async def test_websocket_connection(
        self, user_id: str, token: str, test_messages: Optional[list] = None
    ) -> Dict[str, Any]:
        """Prueba una conexión WebSocket con autenticación."""
        if test_messages is None:
            test_messages = [
                {"type": "ping", "message": "Test ping from client"},
                {"type": "echo", "message": "Test echo message"},
            ]

        results = {
            "connection_success": False,
            "authentication_success": False,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": [],
            "response_times": [],
            "received_messages": [],
        }

        # Construir URL completa con parámetros
        ws_full_url = f"{self.ws_url}?user_id={user_id}&token={token}"
        logger.info(f"Conectando a WebSocket: {ws_full_url}")

        try:
            start_time = time.time()

            async with websockets.connect(ws_full_url) as websocket:
                connect_time = time.time() - start_time
                results["connection_success"] = True
                results["connection_time_ms"] = round(connect_time * 1000, 2)
                logger.info(
                    f"Conexión establecida en {results['connection_time_ms']}ms"
                )

                # Esperar mensaje de bienvenida del servidor
                try:
                    welcome = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    welcome_data = json.loads(welcome)
                    results["welcome_message"] = welcome_data
                    results["messages_received"] += 1
                    logger.info(f"Mensaje de bienvenida recibido: {welcome_data}")
                except asyncio.TimeoutError:
                    logger.warning("No se recibió mensaje de bienvenida en 2 segundos")

                # Enviar mensajes de prueba
                for i, message in enumerate(test_messages):
                    try:
                        send_start = time.time()
                        await websocket.send(json.dumps(message))
                        send_time = time.time() - send_start

                        results["messages_sent"] += 1
                        logger.info(f"Mensaje {i + 1} enviado: {message}")

                        # Intentar recibir respuesta
                        try:
                            recv_start = time.time()
                            response = await asyncio.wait_for(
                                websocket.recv(), timeout=2.0
                            )
                            recv_time = time.time() - recv_start

                            response_data = json.loads(response)
                            results["messages_received"] += 1
                            results["response_times"].append(
                                {
                                    "message": message.get("type", f"message_{i + 1}"),
                                    "send_time_ms": round(send_time * 1000, 2),
                                    "receive_time_ms": round(recv_time * 1000, 2),
                                    "total_roundtrip_ms": round(
                                        (send_time + recv_time) * 1000, 2
                                    ),
                                }
                            )
                            results["received_messages"].append(response_data)
                            logger.info(f"Respuesta {i + 1} recibida: {response_data}")
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"No se recibió respuesta para mensaje {i + 1} en 2 segundos"
                            )

                    except Exception as e:
                        error_msg = f"Error enviando mensaje {i + 1}: {e}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)

                # Cerrar conexión correctamente
                await websocket.close()
                logger.info("Conexión cerrada correctamente")

        except websockets.exceptions.InvalidStatusCode as e:
            error_msg = f"Error de estado HTTP: {e.status_code}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        except websockets.exceptions.ConnectionClosedError as e:
            error_msg = f"Conexión cerrada con error: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Error de conexión WebSocket: {type(e).__name__}: {e}"
            logger.error(error_msg)
            results["errors"].append(error_msg)

        return results

    async def test_scenario_no_token(self, user_id: str):
        """Prueba conexión sin token (debe fallar)."""
        logger.info(f"\n{'=' * 60}")
        logger.info("PRUEBA: Conexión sin token (debe fallar)")
        logger.info(f"{'=' * 60}")

        ws_full_url = f"{self.ws_url}?user_id={user_id}"
        logger.info(f"Intentando conectar sin token: {ws_full_url}")

        try:
            async with websockets.connect(ws_full_url) as websocket:
                # No debería llegar aquí
                logger.error("ERROR: Se conectó sin token (esto no debería pasar)")
                await websocket.close()
                return {
                    "success": False,
                    "error": "Se conectó sin token (vulnerabilidad)",
                }
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 4001:
                logger.info(
                    f"✓ Correcto: Conexión rechazada con código {e.status_code} - {e.reason}"
                )
                return {"success": True, "expected_error": f"4001"}
            else:
                logger.warning(
                    f"✓ Conexión rechazada con código {e.status_code} (esperado 4001)"
                )
                return {
                    "success": True,
                    "unexpected_code": e.status_code,
                }
        except Exception as e:
            logger.info(f"✓ Conexión falló como se esperaba: {type(e).__name__}")
            return {"success": True, "error_type": type(e).__name__, "error": str(e)}

    async def test_scenario_invalid_token(self, user_id: str):
        """Prueba conexión con token inválido (debe fallar)."""
        logger.info(f"\n{'=' * 60}")
        logger.info("PRUEBA: Conexión con token inválido (debe fallar)")
        logger.info(f"{'=' * 60}")

        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0X3VzZXIiLCJleHAiOjE3MTAwMDAwMDB9.invalid_signature"
        ws_full_url = f"{self.ws_url}?user_id={user_id}&token={invalid_token}"
        logger.info(f"Intentando conectar con token inválido")

        try:
            async with websockets.connect(ws_full_url) as websocket:
                # No debería llegar aquí
                logger.error(
                    "ERROR: Se conectó con token inválido (esto no debería pasar)"
                )
                await websocket.close()
                return {"success": False, "error": "Se conectó con token inválido"}
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 4002:
                logger.info(
                    f"✓ Correcto: Conexión rechazada con código {e.status_code} - {e.reason}"
                )
                return {"success": True, "expected_error": f"4002 - {e.reason}"}
            else:
                logger.warning(
                    f"✓ Conexión rechazada con código {e.status_code} (esperado 4002)"
                )
                return {
                    "success": True,
                    "unexpected_code": e.status_code,
                    "reason": e.reason,
                }
        except Exception as e:
            logger.info(f"✓ Conexión falló como se esperaba: {type(e).__name__}")
            return {"success": True, "error_type": type(e).__name__, "error": str(e)}

    async def test_scenario_user_id_mismatch(self, user_id: str, token: str):
        """Prueba conexión con user_id que no coincide con token (debe fallar)."""
        logger.info(f"\n{'=' * 60}")
        logger.info("PRUEBA: User ID no coincide con token (debe fallar)")
        logger.info(f"{'=' * 60}")

        wrong_user_id = "wrong_user_999"
        ws_full_url = f"{self.ws_url}?user_id={wrong_user_id}&token={token}"
        logger.info(
            f"Token válido para: {user_id}, intentando conectar como: {wrong_user_id}"
        )

        try:
            async with websockets.connect(ws_full_url) as websocket:
                # No debería llegar aquí
                logger.error(
                    "ERROR: Se conectó con user_id incorrecto (esto no debería pasar)"
                )
                await websocket.close()
                return {"success": False, "error": "Se conectó con user_id incorrecto"}
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 4003:
                logger.info(
                    f"✓ Correcto: Conexión rechazada con código {e.status_code} - {e.reason}"
                )
                return {"success": True, "expected_error": f"4003 - {e.reason}"}
            else:
                logger.warning(f"✓ Conexión rechazada con código {e.status_code}")
                return {"success": True, "code": e.status_code, "reason": e.reason}
        except Exception as e:
            logger.info(f"✓ Conexión falló como se esperaba: {type(e).__name__}")
            return {"success": True, "error_type": type(e).__name__, "error": str(e)}


async def main():
    """Función principal de prueba."""
    print("\n" + "=" * 80)
    print("PRUEBA COMPLETA DE WEBSOCKET - RETO PROSPERAS")
    print("=" * 80)

    # Verificar si la API local está funcionando
    print("\n1. Verificando API local...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/health") as response:
                if response.status == 200:
                    print("✓ API local está funcionando")
                else:
                    print(f"⚠ API local responde con código {response.status}")
    except Exception as e:
        print(f"✗ No se puede conectar a API local: {e}")
        print("Asegúrate de que el backend esté ejecutándose localmente")
        return

    # Ejecutar pruebas
    async with WebSocketTester(API_BASE_URL, WS_URL) as tester:
        print("\n2. Obteniendo tokens JWT...")
        try:
            token1 = await tester.get_jwt_token(TEST_USER_ID)
            token2 = await tester.get_jwt_token(TEST_USER_ID_2)
            print(f"✓ Tokens obtenidos para usuarios: {TEST_USER_ID}, {TEST_USER_ID_2}")
        except Exception as e:
            print(f"✗ Error obteniendo tokens: {e}")
            return

        print("\n3. Ejecutando pruebas de escenarios negativos...")

        # Prueba sin token
        no_token_result = await tester.test_scenario_no_token(TEST_USER_ID)

        # Prueba con token inválido
        invalid_token_result = await tester.test_scenario_invalid_token(TEST_USER_ID)

        # Prueba con user_id que no coincide
        mismatch_result = await tester.test_scenario_user_id_mismatch(
            TEST_USER_ID, token1
        )

        print("\n4. Ejecutando prueba principal de conexión WebSocket...")

        # Mensajes de prueba
        test_messages = [
            {
                "type": "ping",
                "message": "Test ping from client",
                "timestamp": time.time(),
            },
            {"type": "echo", "message": "Test echo message", "timestamp": time.time()},
            {"type": "subscribe", "job_id": "test_job_123", "timestamp": time.time()},
        ]

        # Prueba principal
        main_result = await tester.test_websocket_connection(
            user_id=TEST_USER_ID, token=token1, test_messages=test_messages
        )

        print("\n5. Generando reporte final...")
        print("\n" + "=" * 80)
        print("REPORTE FINAL DE PRUEBA WEBSOCKET")
        print("=" * 80)

        # URL exacta para frontend
        print(f"\n📋 URL EXACTA PARA FRONTEND:")
        print(
            f"   Formato: ws://ALB-DNS:8000/ws/jobs?user_id={{userId}}&token={{jwtToken}}"
        )
        print(f"   Ejemplo: {WS_URL}?user_id={TEST_USER_ID}&token={token1[:50]}...")

        # Resumen de pruebas
        print(f"\n📊 RESUMEN DE PRUEBAS:")
        print(
            f"   • Conexión sin token: {'✓ RECHAZADA' if no_token_result.get('success') else '✗ PERMITIDA'}"
        )
        print(
            f"   • Token inválido: {'✓ RECHAZADA' if invalid_token_result.get('success') else '✗ PERMITIDA'}"
        )
        print(
            f"   • User ID no coincide: {'✓ RECHAZADA' if mismatch_result.get('success') else '✗ PERMITIDA'}"
        )

        # Resultados de conexión principal
        print(f"\n🔗 CONEXIÓN PRINCIPAL:")
        print(
            f"   • Éxito de conexión: {'✓ SÍ' if main_result['connection_success'] else '✗ NO'}"
        )
        if main_result.get("connection_time_ms"):
            print(f"   • Tiempo de conexión: {main_result['connection_time_ms']}ms")
        print(f"   • Mensajes enviados: {main_result['messages_sent']}")
        print(f"   • Mensajes recibidos: {main_result['messages_received']}")

        # Tiempos de respuesta
        if main_result["response_times"]:
            print(f"\n⏱ TIEMPOS DE RESPUESTA:")
            for rt in main_result["response_times"]:
                print(
                    f"   • {rt['message']}: {rt['total_roundtrip_ms']}ms (envío: {rt['send_time_ms']}ms, recepción: {rt['receive_time_ms']}ms)"
                )

        # Errores
        if main_result["errors"]:
            print(f"\n⚠ ERRORES ENCONTRADOS:")
            for error in main_result["errors"]:
                print(f"   • {error}")
        else:
            print(f"\n✅ No se encontraron errores en la conexión principal")

        # Mensajes recibidos
        if main_result["received_messages"]:
            print(f"\n📨 MENSAJES RECIBIDOS:")
            for i, msg in enumerate(main_result["received_messages"]):
                print(
                    f"   {i + 1}. {json.dumps(msg, indent=2).replace(chr(10), chr(10) + '     ')}"
                )

        # Recomendaciones
        print(f"\n💡 RECOMENDACIONES PARA FRONTEND:")
        print(f"   1. URL: Usar el formato exacto mostrado arriba")
        print(f"   2. Autenticación: Siempre incluir user_id y token JWT válido")
        print(
            f"   3. Manejo de errores: Implementar reconexión automática para códigos 4001-4003"
        )
        print(f"   4. Timeout: Configurar timeout de conexión de 10-15 segundos")
        print(
            f"   5. Heartbeat: Considerar enviar ping periódico para mantener conexión activa"
        )

        print(f"\n" + "=" * 80)
        print("PRUEBA COMPLETADA")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
