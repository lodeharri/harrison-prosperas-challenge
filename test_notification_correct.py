#!/usr/bin/env python3
"""
Test direct notification endpoint with correct format
"""

import httpx
import asyncio
import json
from datetime import datetime


async def test_notification_endpoint_correct():
    """Test the /internal/notify endpoint with correct format"""

    # URL del ALB
    alb_url = (
        "http://harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com:8000"
    )

    # Datos de prueba de notificación - FORMATO CORRECTO
    notification_data = {
        "user_id": "test-user-123",
        "job_id": "79074423-6b29-4984-a348-79257af7eeb5",
        "status": "COMPLETED",
        "result_url": "https://example.com/report.pdf",
        "updated_at": datetime.utcnow().isoformat(),
        "report_type": "sales_report",
    }

    print(f"Testing notification endpoint: {alb_url}/internal/notify")
    print(f"Notification data (correct format):")
    print(json.dumps(notification_data, indent=2))

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


async def test_websocket_and_notify():
    """Test WebSocket connection and send notification"""
    import websockets

    alb_dns = "harris-APISe-SXjHEuWutfXb-1725140785.us-east-1.elb.amazonaws.com"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZXhwIjoxNzc0MjA1MTc1LCJpYXQiOjE3NzQyMDMzNzV9.u2LqIpyzisOT9F45I_z8vJUGXtqaZGgISh1z81qkmR8"
    user_id = "test-user-123"

    ws_url = f"ws://{alb_dns}:8000/ws/jobs?user_id={user_id}&token={token}"

    print(f"\nTesting WebSocket connection: {ws_url}")

    try:
        async with websockets.connect(ws_url) as ws:
            print("✅ WebSocket connection established")

            # Send notification via HTTP
            print("\nSending notification via HTTP POST...")
            notify_ok = await test_notification_endpoint_correct()

            if notify_ok:
                # Listen for WebSocket notification
                print("\nListening for WebSocket notification...")
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    print(f"📥 WebSocket message received: {msg}")

                    # Parse message
                    data = json.loads(msg)
                    if data.get("type") == "job_update":
                        print(f"✅ Received job_update notification!")
                        print(f"   Job ID: {data.get('data', {}).get('job_id')}")
                        print(f"   Status: {data.get('data', {}).get('status')}")
                        return True
                    else:
                        print(
                            f"⚠️  Received unexpected message type: {data.get('type')}"
                        )
                        return False

                except asyncio.TimeoutError:
                    print("⚠️  No WebSocket notification received in 10 seconds")
                    print("   This could mean:")
                    print("   1. WebSocket manager is not broadcasting")
                    print("   2. Notification endpoint is not triggering WebSocket")
                    print("   3. Connection issue")
                    return False
            else:
                print("❌ Cannot test WebSocket without successful notification")
                return False

    except Exception as e:
        print(f"❌ WebSocket error: {type(e).__name__}: {e}")
        return False


async def check_job_status():
    """Check current job status"""

    api_url = "https://geqa4nilp0.execute-api.us-east-1.amazonaws.com/prod"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiZXhwIjoxNzc0MjA1MTc1LCJpYXQiOjE3NzQyMDMzNzV9.u2LqIpyzisOT9F45I_z8vJUGXtqaZGgISh1z81qkmR8"
    job_id = "79074423-6b29-4984-a348-79257af7eeb5"

    print(f"\nChecking job status: {job_id}")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{api_url}/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )

            if resp.status_code == 200:
                data = resp.json()
                print(f"✅ Job status: {data.get('status')}")
                print(f"   Created: {data.get('created_at')}")
                print(f"   Updated: {data.get('updated_at')}")
                return data.get("status")
            else:
                print(f"❌ Failed to get job status: {resp.status_code}")
                return None

        except Exception as e:
            print(f"❌ Error checking job status: {e}")
            return None


async def main():
    """Run comprehensive notification tests"""
    print("=" * 60)
    print("COMPREHENSIVE NOTIFICATION SYSTEM TEST")
    print("=" * 60)

    # Check current job status
    status = await check_job_status()

    if status == "PROCESSING":
        print("\n⚠️  Job is still PROCESSING. Worker may still be working on it.")
        print("   This could explain why no WebSocket notification was received.")
    elif status == "COMPLETED":
        print("\n✅ Job is already COMPLETED.")
        print("   WebSocket notification should have been sent.")
    elif status == "PENDING":
        print("\n⚠️  Job is still PENDING.")
        print("   Worker may not have picked it up yet.")

    # Test notification endpoint
    print("\n" + "=" * 60)
    print("TESTING NOTIFICATION FLOW")
    print("=" * 60)

    success = await test_websocket_and_notify()

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    if success:
        print("✅ COMPLETE NOTIFICATION FLOW IS WORKING!")
        print("\n🎉 WebSocket via ALB is fully functional!")
        print("   - WebSocket connection: ✅")
        print("   - Notification endpoint: ✅")
        print("   - WebSocket broadcast: ✅")
    else:
        print("❌ Notification flow has issues")
        print("\n🔍 Troubleshooting steps:")
        print("1. Check if worker is running: aws ecs describe-services")
        print("2. Check worker logs (if CloudWatch is configured)")
        print("3. Verify API_BASE_URL in worker config")
        print("4. Test /internal/notify endpoint manually")

    return 0 if success else 1


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
