import praw
import os

# === Your Reddit app credentials ===
client_id = 'p4SHQ57gs2X_bMtaARiJvw'
client_secret = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
redirect_uri = 'http://localhost:8080'
user_agent = 'myredditbot by u/YOUR_USERNAME'

# === Scopes needed ===
scopes = ['identity', 'read', 'submit', 'edit', 'save', 'vote']

print("🚀 Reddit OAuth Setup")
print("="*40)

# Create Reddit instance
reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    user_agent=user_agent
)

# Generate authorization URL
state = os.urandom(16).hex()
auth_url = reddit.auth.url(scopes=scopes, state=state, duration='permanent')

print("📋 STEP 1: Copy and open this URL in your browser:")
print(f"\n{auth_url}\n")
print("📋 STEP 2: After authorizing, you'll be redirected to a URL like:")
print("http://localhost:8080/?state=abc123&code=YOUR_CODE_HERE")
print("\n📋 STEP 3: Copy ONLY the code parameter (after 'code=') and paste below:")

# Get fresh authorization code
while True:
    code = input("\n🔑 Enter authorization code: ").strip()
    
    if not code:
        print("❌ Please enter a code")
        continue
        
    if len(code) < 10:
        print("❌ Code seems too short, please check")
        continue
        
    break

# Exchange code for refresh token
print(f"\n⏳ Exchanging code for refresh token...")

try:
    refresh_token = reddit.auth.authorize(code)
    print("\n" + "="*50)
    print("✅ SUCCESS! Here's your permanent refresh token:")
    print("="*50)
    print(f"{refresh_token}")
    print("="*50)
    print("\n💾 IMPORTANT: Save this refresh token securely!")
    print("💡 You can now use this token for permanent authentication")
    print("\n🔧 Usage example:")
    print("reddit = praw.Reddit(")
    print(f"    client_id='{client_id}',")
    print(f"    client_secret='{client_secret}',")
    print(f"    refresh_token='{refresh_token}',")
    print(f"    user_agent='{user_agent}'")
    print(")")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 Troubleshooting:")
    print("- Make sure you copied the ENTIRE code parameter")
    print("- Authorization codes expire in ~10 minutes")
    print("- Each code can only be used once")
    print("- Try getting a fresh code and running immediately")