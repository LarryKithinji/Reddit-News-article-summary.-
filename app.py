import praw
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==== FILL IN YOUR REDDIT APP DETAILS HERE ====
CLIENT_ID = 'p4SHQ57gs2X_bMtaARiJvw'
CLIENT_SECRET = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
REDIRECT_URI = 'http://localhost:8080'
USER_AGENT = 'refresh_token_bot by u/your_reddit_username'

SCOPES = ['identity', 'read', 'submit', 'edit', 'vote', 'save']  # include 'submit' to allow commenting
STATE = 'secure_random_string'

# ==== STEP 1: Start Reddit Instance ====
reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    user_agent=USER_AGENT
)

# ==== STEP 2: Start local web server to receive the code ====
class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if 'code=' in self.path:
            from urllib.parse import parse_qs, urlparse
            params = parse_qs(urlparse(self.path).query)
            self.server.auth_code = params['code'][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>You may now close this window.</h1>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h1>Invalid response.</h1>")

def start_server():
    server = HTTPServer(('localhost', 8080), AuthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

# ==== STEP 3: Generate auth URL and open it ====
server = start_server()
auth_url = reddit.auth.url(SCOPES, STATE, duration='permanent')
print(f"🔗 Open this URL in your browser if it doesn't open automatically:\n{auth_url}")
webbrowser.open(auth_url)

# ==== STEP 4: Wait for the code ====
import time
print("🌐 Waiting for you to authorize the app in your browser...")
while not hasattr(server, 'auth_code'):
    time.sleep(1)

code = server.auth_code
server.shutdown()

# ==== STEP 5: Exchange the code for a refresh token ====
refresh_token = reddit.auth.authorize(code)
print("\n✅ Your REFRESH TOKEN (save this securely):\n")
print(refresh_token)