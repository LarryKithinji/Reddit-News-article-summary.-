import requests
from requests.auth import HTTPBasicAuth

client_id = "p4SHQ57gs2X_bMtaARiJvw"
client_secret = "PVwX9RTdLj99l1lU9LkvPTEUNmotyQ"
username = "Beginning_Item_9587"
password = "KePCCgt2minU1s1"

auth = HTTPBasicAuth(client_id, client_secret)

headers = {
    "User-Agent": "my-personal-bot/0.1 by u/YOUR_REDDIT_USERNAME"
}

data = {
    "grant_type": "password",
    "username": username,
    "password": password
}

response = requests.post(
    "https://www.reddit.com/api/v1/access_token",
    auth=auth,
    headers=headers,
    data=data
)

print(response.status_code)
print(response.json())