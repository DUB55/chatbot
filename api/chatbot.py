from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import asyncio
import httpx

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            # Extract parameters
            user_input = request_data.get('input', '')
            personality = request_data.get('personality', 'general')
            
            # Set response headers for streaming
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            # Call Pollinations AI
            self.wfile.write(b'data: {"choices": [{"delta": {"content": "')
            self.wfile.write(f"I received your message: {user_input}".encode())
            self.wfile.write(b'"}}]}\n\n')
            self.wfile.write(b'data: [DONE]\n\n')
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {"error": str(e)}
            self.wfile.write(json.dumps(error_response).encode())
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
