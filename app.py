import praw

# Your Reddit app credentials
client_id = 'p4SHQ57gs2X_bMtaARiJvw'
client_secret = 'PVwX9RTdLj99l1lU9LkvPTEUNmotyQ'
redirect_uri = 'http://localhost:8080'
user_agent = 'my-reddit-bot/0.1 by u/Beginning_Item_9587'

# Your fresh authorization code
code = 'CDTOJt5esyZ8ZGU-Ny5bnAOfo3AQuA'

print("🔄 Converting authorization code to permanent refresh token...")
print(f"Code: {code}")

# Create Reddit instance
reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    user_agent=user_agent
)

try:
    # Exchange code for permanent refresh token
    refresh_token = reddit.auth.authorize(code)
    
    print("\n" + "="*60)
    print("✅ SUCCESS! Your PERMANENT refresh token is:")
    print("="*60)
    print(refresh_token)
    print("="*60)
    
    print("\n💾 IMPORTANT: Save this refresh token securely!")
    print("🔧 Use it in your Reddit bots like this:")
    print("\nreddit = praw.Reddit(")
    print(f"    client_id='{client_id}',")
    print(f"    client_secret='{client_secret}',")
    print(f"    refresh_token='{refresh_token}',")
    print(f"    user_agent='{user_agent}'")
    print(")")
    
    print("\n🎉 This refresh token NEVER expires!")
    print("💡 You can now authenticate your bot permanently without passwords")
    
    # Test the refresh token
    print("\n🧪 Testing the refresh token...")
    test_reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        user_agent=user_agent
    )
    
    user = test_reddit.user.me()
    print(f"✅ Test successful! Authenticated as: {user.name}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n💡 Possible issues:")
    print("- Authorization code may have expired (they expire in ~10 minutes)")
    print("- Code may have already been used (single-use only)")
    print("- Check that your app credentials are correct")
    
    print(f"\n🔍 Debug info:")
    print(f"Client ID: {client_id}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Code length: {len(code)} characters")