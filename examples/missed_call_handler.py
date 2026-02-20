#!/usr/bin/env python3
"""
Missed Call → Appointment Flow
===============================

Minimal example showing how to handle missed calls with an AI agent
that qualifies leads and books appointments.

Usage:
    1. Set environment variables (see .env.example)
    2. Run: python examples/missed_call_handler.py
    3. Expose via cloudflared/ngrok
    4. Point your Twilio number's webhook here

ROI: Small businesses report $47/mo cost → $2,100/mo revenue lift.
See docs/MISSED_CALL_TUTORIAL.md for the full walkthrough.
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

# Twilio config
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]

# Your business details — customize these
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "My Business")
AGENT_GREETING = os.environ.get(
    "AGENT_GREETING",
    f"Hi, you've reached {BUSINESS_NAME}. "
    "I'm an AI assistant here to help you book an appointment or answer questions. "
    "How can I help you today?",
)

# OpenAI Realtime session config
VOICE = os.environ.get("VOICE", "alloy")
MODEL = os.environ.get("MODEL", "gpt-4o-realtime-preview")

SYSTEM_PROMPT = f"""You are a friendly, professional receptionist for {BUSINESS_NAME}.

Your goals (in order):
1. Greet the caller warmly
2. Understand what they need
3. Collect their name and callback number
4. Suggest appointment times (Mon-Fri 9am-5pm)
5. Confirm the booking and thank them

Keep responses concise and natural. You're on a phone call, not writing an essay.
If the caller seems frustrated about reaching an AI, acknowledge it:
"I understand — I'm here to make sure you get taken care of right away
rather than going to voicemail."
"""


class CallHandler(BaseHTTPRequestHandler):
    """Handles incoming Twilio webhook requests."""

    def do_POST(self):
        # Parse the Twilio webhook payload
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        params = parse_qs(body)

        caller = params.get("From", ["unknown"])[0]
        print(f"📞 Incoming call from {caller}")

        # Respond with TwiML that connects to OpenAI Realtime
        # This uses Twilio's <Stream> to pipe audio to a WebSocket
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>{AGENT_GREETING}</Say>
    <Connect>
        <Stream url="wss://{os.environ['PUBLIC_HOST']}/media-stream">
            <Parameter name="caller" value="{caller}" />
        </Stream>
    </Connect>
</Response>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.end_headers()
        self.wfile.write(twiml.encode())

    def log_message(self, format, *args):
        # Quieter logging
        print(f"  {args[0]}")


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), CallHandler)
    print(f"🎙️  Missed-call handler running on port {port}")
    print(f"📋 Business: {BUSINESS_NAME}")
    print(f"🔗 Point your Twilio webhook to: https://YOUR_DOMAIN/")
    print(f"   (use cloudflared or ngrok to expose this port)")
    print()
    print("Waiting for calls...")
    server.serve_forever()


if __name__ == "__main__":
    main()
