import praw

client_id = 'p4SHQ57gs2X_bMtaARiJvw'
client_secret = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
redirect_uri = 'http://localhost:8080'
user_agent = 'myredditbot by u/YOUR_USERNAME'

code = 'g9kZrU0JrY9i6tEfpXnO0kEeDI-eFg'

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    user_agent=user_agent
)

try:
    refresh_token = reddit.auth.authorize(code)
    print(f"✅ Your refresh token is:\n{refresh_token}")
    print("\n💾 Save this refresh token securely!")
    print("💡 You can now use this refresh token to authenticate your bot permanently.")
except Exception as e:
    print(f"❌ Error getting refresh token: {e}")
    print("💡 The authorization code might have expired or been used already.")
    print("💡 Authorization codes are single-use and expire quickly (usually within 10 minutes).")