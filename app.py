import praw
import socket
import urllib.parse
import os

# === Fill in your Reddit app credentials ===
client_id = 'p4SHQ57gs2X_bMtaARiJvw'
client_secret = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
redirect_uri = 'http://localhost:8080'
user_agent = 'myredditbot by u/YOUR_USERNAME'

# === Scopes for commenting ===
scopes = ['identity', 'read', 'submit', 'edit', 'save', 'vote']

# === Create the Reddit instance ===
reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    user_agent=user_agent
)

# === Step 1: Generate the authorization URL ===
state = os.urandom(16).hex()
auth_url = reddit.auth.url(scopes=scopes, state=state, duration='permanent')

print("\n🔗 Open this URL in your browser to authorize:")
print(auth_url)

# === Step 2: Start a simple web server to catch the redirect ===
print("\n🌐 Waiting for the redirect from Reddit...")

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(("localhost", 8080))
    s.listen(1)
    conn, _ = s.accept()
    with conn:
        request = conn.recv(1024).decode("utf-8")
        # Parse the GET request to get the code
        try:
            path = request.split(" ")[1]
            params = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            code = params["code"][0]
        except Exception as e:
            print("❌ Failed to extract authorization code.")
            print(e)
            conn.send(b"HTTP/1.1 400 Bad Request\n\nSomething went wrong.")
            exit(1)

        # Tell the browser it's done
        conn.send(b"HTTP/1.1 200 OK\n\nAuthorization successful! You can close this window.")

# === Step 3: Use the code to get a permanent refresh token ===
refresh_token = reddit.auth.authorize(code)

print("\n✅ SUCCESS: Your permanent refresh token is:\n")
print(refresh_token)
print("\n💾 Save this refresh token securely. You can now use it to authenticate your bot forever.")