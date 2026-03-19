#!/usr/bin/env python3
"""
Test WebSocket notifications end-to-end.
"""

import asyncio
import json
import sys
import time


async def test_websocket_full_flow():
    """Test the complete flow: auth -> create job -> websocket notification."""

    # Imports
    import websockets
    import httpx

    BASE_URL = "http://localhost:8000"
    WS_URL = "ws://localhost:8000"
    USER_ID = f"test-ws-{int(time.time())}"

    print("=" * 60)
    print("WEBSOCKET END-TO-END TEST")
    print("=" * 60)

    # Step 1: Get JWT Token
    print("\n[1] Getting JWT token...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/token", json={"user_id": USER_ID})
        if resp.status_code != 200:
            print(f"❌ Auth failed: {resp.status_code} - {resp.text}")
            return False

        token = resp.json()["access_token"]
        print(f"✅ Token obtained: {token[:30]}...")

    # Step 2: Connect to WebSocket
    print("\n[2] Connecting to WebSocket...")
    # Note: Route is /ws/jobs?user_id={user_id}&token={token}
    ws_url = f"{WS_URL}/ws/jobs?user_id={USER_ID}&token={token}"

    try:
        async with websockets.connect(ws_url) as ws:
            print(f"✅ WebSocket connected to {ws_url}")

            # Send ping to verify connection
            await ws.send("ping")
            print("   Sent: ping")

            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"   Received: {response}")

            if response != "pong":
                print(f"⚠️ Unexpected response to ping: {response}")

            # Step 3: Create a job
            print("\n[3] Creating a job...")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BASE_URL}/jobs",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "report_type": "sales_report",
                        "date_range": "month",
                        "format": "pdf",
                    },
                )

                if resp.status_code not in [200, 201]:
                    print(f"❌ Job creation failed: {resp.status_code} - {resp.text}")
                    return False

                job_data = resp.json()
                job_id = job_data["job_id"]
                print(f"✅ Job created: {job_id}")
                print(f"   Initial status: {job_data['status']}")

            # Step 4: Wait for job update notifications
            print("\n[4] Waiting for job update notifications...")
            print("   (This may take 5-30 seconds for the worker to process)")

            deadline = time.time() + 45  # 45 seconds max

            while time.time() < deadline:
                try:
                    message = await asyncio.wait_for(
                        ws.recv(), timeout=deadline - time.time()
                    )
                    data = json.loads(message)
                    print(f"\n📨 Notification received!")
                    print(f"   Type: {data.get('type')}")
                    print(f"   Data: {json.dumps(data.get('data', {}), indent=4)}")

                    if data.get("type") == "job_update":
                        job_status = data["data"].get("status")
                        if job_status in ["COMPLETED", "FAILED"]:
                            print(f"\n✅ Job finished with status: {job_status}")
                            await ws.close()
                            return True

                except asyncio.TimeoutError:
                    break

            print("⚠️ Timeout waiting for job update")
            return False

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_websocket_full_flow())
    sys.exit(0 if result else 1)
