import requests
import requests.auth

client_id = "PVwX9RTdLj99l1lU9LkvPTEUNmotyQ"
client_secret = "PVwX9RTdLj99l1lU9LkvPTEUNmotyQ"
username = "Beginning_Item_9587"
password = "KePCCgt2minU1s1"

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