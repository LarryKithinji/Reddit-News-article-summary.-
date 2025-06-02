import requests
from requests.auth import HTTPBasicAuth

# Replace these with your app credentials
client_id = ""
client_secret = ""
redirect_uri = "http://localhost:8080"
authorization_code = "YOUR_AUTHORIZATION_CODE"

# Setup authentication
auth = HTTPBasicAuth(client_id, client_secret)
headers = {
    "User-Agent": "my-permanent-bot/0.1 by YOUR_REDDIT_USERNAME"
}
data = {
    "grant_type": "authorization_code",
    "code": authorization_code,
    "redirect_uri": redirect_uri,
}

# Exchange code for access + refresh token
response = requests.post(
    "https://www.reddit.com/api/v1/access_token",
    auth=auth,
    headers=headers,
    data=data,
)

# Show response (should include 'refresh_token')
print("Response JSON:")
print(response.json())