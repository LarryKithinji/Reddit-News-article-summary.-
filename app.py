import requests
import base64

client_id = 'YOUR_CLIENT_ID'
client_secret = 'YOUR_CLIENT_SECRET'
code = 'AUTHORIZATION_CODE_FROM_REDDIT'
redirect_uri = 'http://localhost:8080'

auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
headers = {"User-Agent": "manual-token-bot by u/YOUR_USERNAME"}

data = {
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": redirect_uri,
}

response = requests.post(
    "https://www.reddit.com/api/v1/access_token",
    auth=auth,
    data=data,
    headers=headers,
)

print(response.json())  # will include 'refresh_token' if successful