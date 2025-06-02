import praw

# Your Reddit app credentials
client_id = 'p4SHQ57gs2X_bMtaARiJvw'
client_secret = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
username = 'Beginning_Item_9587'
password = 'KePCCgt2minU1s1'

# Method 1: Username/Password (Limited - no permanent tokens)
print("=== METHOD 1: Username/Password Authentication ===")
reddit_temp = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    username=username,
    password=password,
    user_agent='my-reddit-bot/0.1 by u/Beginning_Item_9587'
)

try:
    print(f"✅ Authenticated as: {reddit_temp.user.me()}")
    print("⚠️  This uses username/password - not permanent tokens")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*60)

# Method 2: OAuth2 for Permanent Refresh Token
print("=== METHOD 2: OAuth2 for Permanent Refresh Token ===")

reddit_oauth = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri='http://localhost:8080',
    user_agent='my-reddit-bot/0.1 by u/Beginning_Item_9587'
)

# Generate permanent authorization URL
import os
state = os.urandom(16).hex()
scopes = ['identity', 'read', 'submit', 'edit', 'save', 'vote']
auth_url = reddit_oauth.auth.url(
    scopes=scopes, 
    state=state, 
    duration='permanent'  # This makes it permanent!
)

print("🔗 Open this URL for PERMANENT authorization:")
print(auth_url)
print("\n📋 After authorizing, paste the authorization code below:")

# Get authorization code
auth_code = input("Authorization code: ").strip()

if auth_code:
    try:
        # Exchange for permanent refresh token
        refresh_token = reddit_oauth.auth.authorize(auth_code)
        print(f"\n✅ SUCCESS! Your PERMANENT refresh token:")
        print(f"🔑 {refresh_token}")
        print("\n💾 Save this refresh token securely!")
        print("\n🔧 Use it like this in your bots:")
        print("reddit = praw.Reddit(")
        print(f"    client_id='{client_id}',")
        print(f"    client_secret='{client_secret}',")
        print(f"    refresh_token='{refresh_token}',")
        print("    user_agent='your-user-agent'")
        print(")")
        
    except Exception as e:
        print(f"❌ Error getting refresh token: {e}")
        print("💡 Make sure the authorization code is fresh (expires in ~10 min)")
else:
    print("❌ No authorization code provided")