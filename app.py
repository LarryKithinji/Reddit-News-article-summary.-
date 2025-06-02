import praw
import time

client_id = 'p4SHQ57gs2X_bMtaARiJvw'
client_secret = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
redirect_uri = 'http://localhost:8080'
user_agent = 'myredditbot by u/YOUR_USERNAME'

# Your authorization code (this might be expired)
code = 'g9kZrU0JrY9i6tEfpXnO0kEeDI-eFg'

print("🔍 Debugging Reddit OAuth...")
print(f"Client ID: {client_id}")
print(f"Redirect URI: {redirect_uri}")
print(f"Code: {code}")

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    user_agent=user_agent
)

try:
    print("\n⏳ Attempting to get refresh token...")
    refresh_token = reddit.auth.authorize(code)
    print(f"✅ SUCCESS! Your refresh token is:")
    print(f"{refresh_token}")
    print("\n💾 Save this refresh token securely!")
    
except praw.exceptions.OAuthException as e:
    print(f"❌ OAuth Error: {e}")
    print("\n💡 Common solutions:")
    print("1. Authorization code has expired (they expire in ~10 minutes)")
    print("2. Authorization code has already been used (single-use only)")
    print("3. Redirect URI mismatch")
    print("\n🔄 You need to get a NEW authorization code:")
    
    # Generate new auth URL
    import os
    state = os.urandom(16).hex()
    scopes = ['identity', 'read', 'submit', 'edit', 'save', 'vote']
    auth_url = reddit.auth.url(scopes=scopes, state=state, duration='permanent')
    
    print(f"\n🔗 Open this URL to get a NEW authorization code:")
    print(auth_url)
    print("\n📋 After authorizing, look for 'code=' in the redirect URL")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    print(f"Error type: {type(e).__name__}")

print("\n" + "="*50)
print("🆘 If you need a fresh authorization code:")
print("1. Open the auth URL above")
print("2. Authorize your app")
print("3. Copy the 'code' parameter from the redirect URL")
print("4. Replace the old code in this script")
print("5. Run the script again immediately (within 10 minutes)")