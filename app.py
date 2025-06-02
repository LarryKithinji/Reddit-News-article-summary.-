import requests
# import base64 # Still not used for this request

print("Script started.")

client_id = 'YOUR_ACTUAL_CLIENT_ID'
client_secret = 'YOUR_ACTUAL_CLIENT_SECRET'
code = 'THE_FRESH_AUTHORIZATION_CODE_YOU_GOT_FROM_REDDIT'
redirect_uri = 'http://localhost:8080' # Must EXACTLY match your app's redirect URI
your_reddit_username = 'YOUR_ACTUAL_REDDIT_USERNAME'

print(f"Client ID: {client_id[:5]}...") # Print first 5 chars for verification
print(f"Code: {code[:5]}...") # Print first 5 chars
print(f"Redirect URI: {redirect_uri}")
print(f"Username: u/{your_reddit_username}")

auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
print("HTTPBasicAuth object created.")

headers = {"User-Agent": f"manual-token-bot/0.1 by u/{your_reddit_username}"}
print(f"Headers created: {headers}")

data = {
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": redirect_uri,
}
print(f"Data payload created: {data}")

target_url = "https://www.reddit.com/api/v1/access_token"
print(f"Target URL: {target_url}")

print("\nAttempting to send POST request...")
try:
    response = requests.post(
        target_url,
        auth=auth,
        data=data,
        headers=headers,
        timeout=20  # Added a timeout of 20 seconds
    )

    print("\n--- Response Received ---") # This will print if the request completed
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {response.headers}")
    print(f"Response Text (first 500 chars): {response.text[:500]}") # Print only first 500 chars

    if response.ok:
        print("\n--- Success! Token Data ---")
        try:
            token_data = response.json()
            print(token_data)
            if 'refresh_token' in token_data:
                print("Refresh token was included.")
            else:
                print("Refresh token was NOT included.")
        except requests.exceptions.JSONDecodeError as json_err:
            print(f"Could not decode JSON from successful response: {json_err}")
            print("This is unexpected for a successful token request.")
    else:
        print("\n--- Error from Reddit API ---")
        try:
            # Reddit often returns JSON error messages
            print(f"Error JSON: {response.json()}")
        except requests.exceptions.JSONDecodeError:
            print("Response was not JSON, full text printed above (first 500 chars).")

except requests.exceptions.Timeout:
    print("\n---REQUEST TIMED OUT---")
    print("The request to Reddit took too long and was stopped by the timeout.")
    print("This could indicate a network problem, a firewall blocking the request, or Reddit API issues.")
except requests.exceptions.RequestException as e:
    print(f"\n---REQUEST FAILED (RequestException)---")
    print(f"An error occurred during the request: {e}")
    print("This could be a network issue (like DNS failure, connection refused) or other request problem.")
except Exception as e:
    print(f"\n---AN UNEXPECTED ERROR OCCURRED---")
    print(f"A Python error occurred: {e}")

print("\nScript finished or error handled.")
