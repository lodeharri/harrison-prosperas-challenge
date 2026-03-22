#!/usr/bin/env python3
"""WebSocket functionality test script."""

import asyncio
import json
import sys
import time
import websockets
import httpx

API_BASE = "https://geqa4nilp0.execute-api.us-east-1.amazonaws.com/prod"
WS_BASE = "ws://harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com:8000"
USER_ID = "test-user-123"

results = {
    "health_check": {"status": "PENDING", "details": ""},
    "auth_token": {"status": "PENDING", "details": ""},
    "websocket_connect": {"status": "PENDING", "details": ""},
    "websocket_ping": {"status": "PENDING", "details": ""},
    "create_job": {"status": "PENDING", "details": ""},
    "websocket_notification": {"status": "PENDING", "details": ""},
}


def print_result(name: str, passed: bool, details: str):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    results[name]["status"] = "PASS" if passed else "FAIL"
    results[name]["details"] = details
    print(f"\n{status}: {name}")
    print(f"   Details: {details}")


async def test_health():
    """Test 1: Health check endpoint."""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{API_BASE}/health", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                print_result(
                    "health_check",
                    True,
                    f"Status: {data.get('status')}, Dependencies: {data.get('dependencies')}",
                )
            else:
                print_result("health_check", False, f"HTTP {resp.status_code}")
        except Exception as e:
            print_result("health_check", False, str(e))


async def test_auth():
    """Test 2: Get JWT token."""
    print("\n" + "=" * 60)
    print("TEST 2: Authentication")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{API_BASE}/auth/token", json={"user_id": USER_ID}, timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token", "")
                print_result(
                    "auth_token", True, f"Token received (length: {len(token)} chars)"
                )
                return token
            else:
                print_result("auth_token", False, f"HTTP {resp.status_code}")
                return None
        except Exception as e:
            print_result("auth_token", False, str(e))
            return None


async def test_websocket(token: str):
    """Test 3: WebSocket connection with ping/pong."""
    print("\n" + "=" * 60)
    print("TEST 3: WebSocket Connection")
    print("=" * 60)

    ws_url = f"{WS_BASE}/ws/jobs?user_id={USER_ID}&token={token}"
    print(f"Connecting to: {ws_url[:80]}...")

    try:
        async with websockets.connect(ws_url) as ws:
            # Wait for connection to be accepted
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print(f"Received: {msg}")
                print_result("websocket_connect", True, "Connection accepted by server")
            except asyncio.TimeoutError:
                # Connection might not send a welcome message
                print_result(
                    "websocket_connect",
                    True,
                    "Connection established (no welcome message)",
                )

            # Test ping/pong
            print("\nSending 'ping' message...")
            await ws.send("ping")
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                if response == "pong":
                    print_result("websocket_ping", True, "Received 'pong' response")
                else:
                    print_result(
                        "websocket_ping", False, f"Unexpected response: {response}"
                    )
            except asyncio.TimeoutError:
                print_result("websocket_ping", False, "Timeout waiting for pong")

            return ws
    except websockets.exceptions.InvalidStatusCode as e:
        print_result("websocket_connect", False, f"Invalid status code: {e}")
        return None
    except Exception as e:
        print_result("websocket_connect", False, f"{type(e).__name__}: {e}")
        return None


async def test_create_job(token: str):
    """Test 4: Create a job."""
    print("\n" + "=" * 60)
    print("TEST 4: Create Job")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{API_BASE}/jobs",
                json={
                    "report_type": "sales_report",
                    "date_range": "2024-01-01_2024-01-31",
                    "format": "pdf",
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                job_id = data.get("job_id", "unknown")
                print_result(
                    "create_job",
                    True,
                    f"Job created: {job_id}, Status: {data.get('status')}",
                )
                return job_id
            else:
                print_result(
                    "create_job", False, f"HTTP {resp.status_code}: {resp.text}"
                )
                return None
        except Exception as e:
            print_result("create_job", False, str(e))
            return None


async def test_websocket_with_job(token: str, ws: websockets.WebSocketClientProtocol):
    """Test 5: WebSocket receives job notification."""
    print("\n" + "=" * 60)
    print("TEST 5: WebSocket Job Notification")
    print("=" * 60)

    job_id = await test_create_job(token)
    if not job_id:
        print_result("websocket_notification", False, "Could not create job")
        return

    print(f"\nWaiting for WebSocket notification (job_id: {job_id})...")
    print("Note: Worker processes jobs in 5-30 seconds...")

    # Wait for notification (up to 45 seconds to account for processing time)
    max_wait = 45
    start_time = time.time()
    notification_received = False

    while time.time() - start_time < max_wait:
        try:
            remaining = int(max_wait - (time.time() - start_time))
            msg = await asyncio.wait_for(ws.recv(), timeout=min(5.0, remaining))
            data = json.loads(msg)

            print(f"Received WebSocket message: {json.dumps(data, indent=2)}")

            if data.get("type") == "job_update":
                job_data = data.get("data", {})
                if job_data.get("job_id") == job_id:
                    status = job_data.get("status")
                    print_result(
                        "websocket_notification",
                        True,
                        f"Job {job_id} status update: {status}",
                    )
                    notification_received = True
                    break
        except asyncio.TimeoutError:
            # No message yet, check elapsed time
            elapsed = int(time.time() - start_time)
            print(f"  Waiting... ({elapsed}s elapsed, {max_wait - elapsed}s remaining)")
            continue
        except Exception as e:
            print(f"Error receiving: {e}")
            break

    if not notification_received:
        print_result(
            "websocket_notification",
            False,
            f"Timeout ({max_wait}s) - job may not have been processed yet",
        )

    return notification_received


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("WEBSOCKET FUNCTIONALITY TEST SUITE")
    print("=" * 60)

    # Test 1: Health
    await test_health()

    # Test 2: Auth
    token = await test_auth()
    if not token:
        print("\n❌ Cannot proceed without token")
        print_summary()
        return 1

    # Test 3: WebSocket connection
    ws = await test_websocket(token)

    # Test 4 & 5: Create job and verify WebSocket notification
    if ws:
        await test_websocket_with_job(token, ws)
        await ws.close()

    # Print summary
    print_summary()

    # Return 0 if all passed, 1 otherwise
    all_passed = all(r["status"] == "PASS" for r in results.values())
    return 0 if all_passed else 1


def print_summary():
    """Print test summary."""
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    total = len(results)

    for name, result in results.items():
        status = "✅" if result["status"] == "PASS" else "❌"
        print(f"{status} {name}: {result['details']}")

    print(f"\nTotal: {passed}/{total} tests passed")

    # Specific focus on WebSocket notification
    ws_notify = results.get("websocket_notification", {})
    if ws_notify["status"] == "PASS":
        print("\n🎉 WebSocket notification flow working correctly!")
    elif ws_notify["status"] == "FAIL":
        print("\n⚠️  WebSocket notification flow needs investigation")


if __name__ == "__main__":
    # Check websockets is available
    try:
        import websockets
    except ImportError:
        print("Installing websockets library...")
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "websockets", "-q"]
        )
        import websockets

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
