import praw

client_id = 'p4SHQ57gs2X_bMtaARiJvw'
client_secret = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
redirect_uri = 'http://localhost:8080'
user_agent = 'myredditbot by u/YOUR_USERNAME'

# Put your fresh authorization code here
code = 'HDLz3nXz1SIv6wOIsbtMB_E8Y3LR1w#_'  # Replace with fresh code

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    user_agent=user_agent
)

try:
    refresh_token = reddit.auth.authorize(code)
    print("✅ SUCCESS!")
    print(f"Your refresh token is: {refresh_token}")
    print("\n💾 Save this token - you'll need it for your bot!")
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n💡 If your code is old, get a new one:")
    
    # Generate fresh auth URL
    import os
    state = os.urandom(16).hex()
    scopes = ['identity', 'read', 'submit', 'edit', 'save', 'vote']
    auth_url = reddit.auth.url(scopes=scopes, state=state, duration='permanent')
    print(f"\n🔗 Get new code here: {auth_url}")
    print("📋 Look for 'code=' in the redirect URL after authorizing")