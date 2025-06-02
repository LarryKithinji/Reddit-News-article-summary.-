import praw
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

# === Generate the authorization URL ===
state = os.urandom(16).hex()
auth_url = reddit.auth.url(scopes=scopes, state=state, duration='permanent')

print("\n🔗 STEP 1: Open this URL in your browser to authorize:")
print(auth_url)
print("\n📋 STEP 2: After authorizing, you'll be redirected to a URL like:")
print("http://localhost:8080/?state=...&code=AUTHORIZATION_CODE_HERE")
print("\n✂️  STEP 3: Copy the 'code' parameter from the redirected URL and paste it below:")

# Get the authorization code manually
code = input("\nEnter the authorization code: ").strip()

if not code:
    print("❌ No code provided. Exiting.")
    exit(1)

# === Use the code to get a permanent refresh token ===
try:
    refresh_token = reddit.auth.authorize(code)
    print("\n✅ SUCCESS: Your permanent refresh token is:\n")
    print(refresh_token)
    print("\n💾 Save this refresh token securely. You can now use it to authenticate your bot forever.")
except Exception as e:
    print(f"❌ Error getting refresh token: {e}")
    print("💡 Make sure you copied the authorization code correctly.")