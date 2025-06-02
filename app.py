import requests
# import base64 # base64 is imported but not used in your original script for this request

client_id = 'YOUR_ACTUAL_CLIENT_ID'  # Make sure this is your real Client ID
client_secret = 'YOUR_ACTUAL_CLIENT_SECRET' # Make sure this is your real Client Secret
code = 'THE_FRESH_AUTHORIZATION_CODE_YOU_GOT_FROM_REDDIT' # Make sure this is a new code
redirect_uri = 'http://localhost:8080' # Must EXACTLY match your app's redirect URI
your_reddit_username = 'YOUR_ACTUAL_REDDIT_USERNAME' # e.g., 'MyCoolBot123'

auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
headers = {"User-Agent": f"manual-token-bot/0.1 by u/{your_reddit_username}"} # Formatted User-Agent

data = {
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": redirect_uri,
}

print("--- Sending Request ---")
print(f"Endpoint: https://www.reddit.com/api/v1/access_token")
print(f"Headers: {headers}")
print(f"Data: {data}")
print(f"Auth: Basic Auth with Client ID: {client_id}") # Don't print client_secret here for security if sharing output

try:
    response = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=auth,
        data=data,
        headers=headers,
    )

    print("\n--- Response ---")
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {response.headers}")
    print(f"Response Text: {response.text}")

    if response.ok:
        print("\n--- Success! Token Data ---")
        print(response.json())
    else:
        print("\n--- Error ---")
        try:
            # Reddit often returns JSON error messages
            print(f"Error JSON: {response.json()}")
        except requests.exceptions.JSONDecodeError:
            print("Response was not JSON, printed as text above.")

except requests.exceptions.RequestException as e:
    print(f"\n--- Request Exception ---")
    print(f"An error occurred: {e}")

