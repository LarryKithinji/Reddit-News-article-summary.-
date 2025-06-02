import requests
import requests.auth

client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
username = "YOUR_REDDIT_USERNAME"
password = "YOUR_REDDIT_PASSWORD"

auth = requests.auth.HTTPBasicAuth(client_id, client_secret)

data = {
    "grant_type": "password",
    "username": username,
    "password": password
}

headers = {
    "User-Agent": "my-reddit-bot/0.1 by u/YOUR_REDDIT_USERNAME"
}

response = requests.post(
    "https://www.reddit.com/api/v1/access_token",
    auth=auth,
    data=data,
    headers=headers
)

print(response.status_code)
print(response.json())