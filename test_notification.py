#!/usr/bin/env python3
"""
Test direct notification endpoint to verify worker can notify API
"""

import httpx
import asyncio
import json


async def test_notification_endpoint():
    """Test the /internal/notify endpoint directly"""

    # URL del ALB
    alb_url = (
        "http://harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com:8000"
    )

    # Datos de prueba de notificación
    notification_data = {
        "type": "job_update",
        "data": {
            "job_id": "79074423-6b29-4984-a348-79257af7eeb5",
            "user_id": "test-user-123",
            "status": "COMPLETED",
            "result_url": "https://example.com/report.pdf",
            "updated_at": "2026-03-22T18:20:00.000000Z",
        },
    }

    print(f"Testing notification endpoint: {alb_url}/internal/notify")
    print(f"Notification data: {json.dumps(notification_data, indent=2)}")

    async with httpx.AsyncClient() as client:
        try:
            # Probar endpoint de notificación
            resp = await client.post(
                f"{alb_url}/internal/notify", json=notification_data, timeout=10.0
            )

            print(f"\nResponse status: {resp.status_code}")
            print(f"Response body: {resp.text}")

            if resp.status_code == 200:
                print("✅ Notification endpoint is working!")
                return True
            else:
                print(f"❌ Notification endpoint returned error: {resp.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error calling notification endpoint: {type(e).__name__}: {e}")
            return False


async def test_websocket_connection_simple():
    """Simple WebSocket connection test"""
    import websockets

    alb_dns = "harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZXhwIjoxNzc0MjA1MTc1LCJpYXQiOjE3NzQyMDMzNzV9.u2LqIpyzisOT9F45I_z8vJUGXtqaZGgISh1z81qkmR8"
    user_id = "test-user-123"

    ws_url = f"ws://{alb_dns}:8000/ws/jobs?user_id={user_id}&token={token}"

    print(f"\nTesting WebSocket connection: {ws_url}")

    try:
        async with websockets.connect(ws_url) as ws:
            print("✅ WebSocket connection established")

            # Listen for messages for 10 seconds
            print("Listening for messages for 10 seconds...")
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                print(f"📥 Message received: {msg}")
                return True
            except asyncio.TimeoutError:
                print("⚠️  No messages received in 10 seconds")
                return True  # Connection is still good

    except Exception as e:
        print(f"❌ WebSocket error: {type(e).__name__}: {e}")
        return False


async def main():
    """Run notification tests"""
    print("=" * 60)
    print("NOTIFICATION SYSTEM TEST")
    print("=" * 60)

    # Test 1: Direct notification endpoint
    print("\n1. Testing /internal/notify endpoint...")
    notify_ok = await test_notification_endpoint()

    # Test 2: WebSocket connection
    print("\n2. Testing WebSocket connection...")
    ws_ok = await test_websocket_connection_simple()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    if notify_ok and ws_ok:
        print("✅ Both notification endpoint and WebSocket are working!")
        print("\nPossible issues with worker notification:")
        print("1. Worker may not be calling /internal/notify")
        print("2. Worker may have errors processing the job")
        print("3. Job may still be processing (check status)")
    else:
        print("❌ Some components are not working correctly")

    return 0 if notify_ok and ws_ok else 1


if __name__ == "__main__":
    # Check dependencies
    try:
        import websockets
        import httpx
    except ImportError:
        print("Installing dependencies...")
        import subprocess

        subprocess.check_call(["pip", "install", "websockets", "httpx", "-q"])
        import websockets
        import httpx

    exit_code = asyncio.run(main())
    exit(exit_code)
