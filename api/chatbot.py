from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
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
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Prepare system message based on personality
            system_messages = {
                'general': "You are a helpful AI assistant. Be friendly and helpful.",
                'coder': "You are DUB5, an AI expert programmer. Provide code solutions and technical help.",
                'teacher': "You are an educational AI tutor. Explain concepts clearly and encourage learning.",
                'writer': "You are a creative writing assistant. Help with writing, editing, and creative ideas."
            }
            
            system_message = system_messages.get(personality, system_messages['general'])
            
            # Call Pollinations AI
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    'https://text.pollinations.ai/openai',
                    json={
                        "model": "openai",
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_input}
                        ],
                        "stream": True
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    # Stream the response
                    for chunk in response.iter_bytes():
                        if chunk:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                else:
                    # Fallback response
                    self.wfile.write(b'data: {"choices": [{"delta": {"content": "')
                    self.wfile.write(f"I'm sorry, I'm having trouble connecting to my AI services right now. You said: {user_input}".encode())
                    self.wfile.write(b'"}}]}\n\n')
                    self.wfile.write(b'data: [DONE]\n\n')
            
        except Exception as e:
            # Error fallback
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(b'data: {"choices": [{"delta": {"content": "')
            self.wfile.write(f"Error occurred: {str(e)}. Please try again.".encode())
            self.wfile.write(b'"}}]}\n\n')
            self.wfile.write(b'data: [DONE]\n\n')
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Token')
        self.end_headers()
