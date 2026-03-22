#!/usr/bin/env python3
"""WebSocket functionality test - proper timing version."""

import asyncio
import json
import sys
import time
import websockets
import httpx

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"
USER_ID = "test-user"

results = {}


def print_result(name: str, passed: bool, details: str):
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    results[name] = {"status": "PASS" if passed else "FAIL", "details": details}
    print(f"\n{status}: {name}")
    print(f"   Details: {details}")


async def ws_listener(ws, results_dict, stop_event):
    """Listen for WebSocket messages."""
    notifications = []
    try:
        while not stop_event.is_set():
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                data = json.loads(msg)
                print(f"\n📨 WebSocket received: {json.dumps(data, indent=2)}")
                notifications.append(data)

                # Check if this is the notification we're waiting for
                if data.get("type") == "job_update":
                    results_dict["received"] = True
                    results_dict["notification"] = data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error receiving: {e}")
                break
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket closed by server")
    finally:
        results_dict["all_notifications"] = notifications
        stop_event.set()


async def main():
    """Run WebSocket notification test with proper timing."""
    print("\n" + "=" * 60)
    print("WEBSOCKET NOTIFICATION TIMING TEST")
    print("=" * 60)

    results_dict = {"received": False, "notification": None, "all_notifications": []}

    # Step 1: Get token
    print("\n[1] Getting JWT token...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API_BASE}/auth/token", json={"user_id": USER_ID}, timeout=5.0
        )
        token = resp.json()["access_token"]
        print(f"    Token obtained: {token[:40]}...")

    # Step 2: Connect WebSocket FIRST
    print("\n[2] Connecting WebSocket (BEFORE creating job)...")
    ws_url = f"{WS_BASE}/ws/jobs?user_id={USER_ID}&token={token}"

    try:
        ws = await websockets.connect(ws_url)
        print("    WebSocket connected!")
    except Exception as e:
        print(f"    ❌ Failed to connect: {e}")
        return 1

    # Step 3: Start listener in background
    stop_event = asyncio.Event()
    listener_task = asyncio.create_task(ws_listener(ws, results_dict, stop_event))

    # Give listener time to start
    await asyncio.sleep(0.5)
    print("    Listener started, waiting for notifications...")

    # Step 4: Now create the job
    print("\n[3] Creating job (AFTER WebSocket is connected)...")
    async with httpx.AsyncClient() as client:
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
        job_data = resp.json()
        job_id = job_data.get("job_id")
        print(f"    Job created: {job_id}")
        print(f"    Status: {job_data.get('status')}")

    # Step 5: Wait for notifications (worker processes in 5-30s)
    print("\n[4] Waiting for worker to process job...")
    print("    (Worker processes in 5-30 seconds)")

    max_wait = 40
    start = time.time()

    while time.time() - start < max_wait:
        if results_dict["received"]:
            break
        elapsed = int(time.time() - start)
        print(f"    Waiting... {elapsed}s elapsed")
        await asyncio.sleep(5)

    # Step 6: Check results
    print("\n[5] Checking results...")

    if results_dict["received"]:
        notification = results_dict["notification"]
        job_data = notification.get("data", {})
        print_result(
            "notification_received",
            True,
            f"Job {job_data.get('job_id')} updated to status: {job_data.get('status')}",
        )
    else:
        print_result(
            "notification_received",
            False,
            f"No notification received after {int(time.time() - start)}s. "
            f"Got {len(results_dict['all_notifications'])} messages total.",
        )
        if results_dict["all_notifications"]:
            print("    Received messages:")
            for msg in results_dict["all_notifications"]:
                print(f"      - {msg}")

    # Cleanup
    print("\n[6] Cleanup...")
    stop_event.set()
    await ws.close()
    await listener_task

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = all(r["status"] == "PASS" for r in results.values())

    for name, result in results.items():
        icon = "✅" if result["status"] == "PASS" else "❌"
        print(f"{icon} {name}: {result['details']}")

    if all_passed:
        print("\n🎉 WebSocket notification flow is working!")
        return 0
    else:
        print("\n⚠️  WebSocket notification needs investigation")
        return 1


if __name__ == "__main__":
    try:
        import websockets
    except ImportError:
        import subprocess

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "websockets", "-q"]
        )
        import websockets

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
