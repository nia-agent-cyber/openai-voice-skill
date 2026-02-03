#!/usr/bin/env python3
"""
Example: Making Outbound Calls with OpenAI Voice Server

This demonstrates how to use the outbound calling API.
"""

import httpx
import asyncio
import json

# Server configuration
SERVER_URL = "http://localhost:8080"

def mask_phone_number(phone: str) -> str:
    """Mask phone number for display to protect PII."""
    if not phone or len(phone) < 7:
        return "****"
    return f"{phone[:3]}****{phone[-4:]}"

async def make_outbound_call():
    """Example of initiating an outbound call."""
    
    # Call payload
    call_data = {
        "to": "+1234567890",  # Replace with actual phone number
        "caller_id": "+0987654321",  # Optional: override default caller ID
        "message": "Hello! This is a test call from your AI assistant."  # Optional initial message
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Initiate the call
            response = await client.post(f"{SERVER_URL}/call", json=call_data)
            
            if response.status_code == 200:
                result = response.json()
                call_id = result.get("call_id")
                print(f"✅ Call initiated successfully!")
                print(f"   Call ID: {call_id}")
                print(f"   Status: {result.get('status')}")
                print(f"   Message: {result.get('message')}")
                
                return call_id
            else:
                print(f"❌ Call failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error making call: {e}")
            return None

async def check_call_status(call_id: str = None):
    """Check status of active calls."""
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{SERVER_URL}/calls")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n📞 Active calls: {data.get('active_calls', 0)}")
                
                for call in data.get('calls', []):
                    print(f"   Call: {call.get('call_id')}")
                    print(f"   Type: {call.get('type')}")
                    print(f"   Duration: {call.get('duration', 0):.1f}s")
                    print(f"   Status: {call.get('status')}")
                    
                    if call.get('type') == 'outbound':
                        print(f"   To: {mask_phone_number(call.get('to', ''))}")
                        print(f"   From: {mask_phone_number(call.get('from', ''))}")
                        print(f"   Twilio Status: {call.get('twilio_status')}")
                    print()
                    
            else:
                print(f"❌ Failed to get call status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error checking calls: {e}")

async def cancel_call(call_id: str):
    """Cancel an outbound call."""
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(f"{SERVER_URL}/call/{call_id}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Call canceled: {call_id}")
                print(f"   Status: {result.get('status')}")
            else:
                print(f"❌ Failed to cancel call: {response.status_code}")
                print(f"   Error: {response.text}")
                
        except Exception as e:
            print(f"❌ Error canceling call: {e}")

async def main():
    """Main example function."""
    print("🎙️  OpenAI Voice Server - Outbound Call Example\n")
    
    # Check server status first
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{SERVER_URL}/health")
            if response.status_code == 200:
                health = response.json()
                print(f"✅ Server is running")
                print(f"   Agent: {health.get('agent')}")
                print(f"   Active calls: {health.get('active_calls')}")
                
                # Check if outbound calls are enabled
                root_response = await client.get(SERVER_URL)
                if root_response.status_code == 200:
                    root_data = root_response.json()
                    if not root_data.get('outbound_calls_enabled'):
                        print("❌ Outbound calls are not enabled!")
                        print("   Configure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
                        return
                    else:
                        print("✅ Outbound calls are enabled")
                
            else:
                print(f"❌ Server not responding: {response.status_code}")
                return
                
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            print(f"   Make sure the server is running on {SERVER_URL}")
            return
    
    print("\n" + "="*50)
    
    # Example workflow
    print("\n1. Checking current calls...")
    await check_call_status()
    
    print("\n2. Initiating outbound call...")
    call_id = await make_outbound_call()
    
    if call_id:
        print(f"\n3. Waiting a moment...")
        await asyncio.sleep(3)
        
        print(f"\n4. Checking call status...")
        await check_call_status()
        
        print(f"\n5. Example: Canceling call (uncomment to test)")
        # await cancel_call(call_id)
    
    print(f"\n✨ Example complete!")

if __name__ == "__main__":
    asyncio.run(main())