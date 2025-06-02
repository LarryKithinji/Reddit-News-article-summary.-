import random
import socket
import sys

import praw


def main():
    """Provide the program's entry point when directly executed."""
    # Set your Reddit credentials here
    client_id = "p4SHQ57gs2X_bMtaARiJvw"
    client_secret = "PVwX9RTdLj99l1lU9LkvPTEUNmotyQ"
    redirect_uri = "http://localhost:8080"
    user_agent = "obtain_refresh_token/v0 by u/YOUR_USERNAME"

    scope_input = input(
        "Enter a comma separated list of scopes, or '*' for all scopes: "
    )
    scopes = [scope.strip() for scope in scope_input.strip().split(",")]

    # Initialize Reddit instance
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        user_agent=user_agent,
    )

    # Generate random state string
    state = str(random.randint(0, 65000))
    url = reddit.auth.url(duration="permanent", scopes=scopes, state=state)

    print("\nNow open this URL in your browser and approve access:\n")
    print(url)
    print("\nWaiting for Reddit to redirect...\n")

    # Open local socket to catch the redirect
    client = receive_connection()
    data = client.recv(1024).decode("utf-8")

    # Parse the returned URL parameters
    param_tokens = data.split(" ", 2)[1].split("?", 1)[1].split("&")
    params = dict(token.split("=") for token in param_tokens)

    if state != params.get("state"):
        send_message(
            client,
            f"State mismatch. Expected: {state} Received: {params.get('state')}",
        )
        return 1
    elif "error" in params:
        send_message(client, f"Error: {params['error']}")
        return 1

    # Exchange code for refresh token
    refresh_token = reddit.auth.authorize(params["code"])
    send_message(client, f"Success! Your refresh token is:\n\n{refresh_token}\n\nCopy and store it securely.")
    print("\nRefresh token obtained successfully:")
    print(refresh_token)
    return 0


def receive_connection():
    """Wait for and return a single client socket connected on localhost:8080"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("localhost", 8080))
    server.listen(1)
    client_socket, _ = server.accept()
    server.close()
    return client_socket


def send_message(client, message):
    """Send message to client and close the connection."""
    print(message)
    client.send(f"HTTP/1.1 200 OK\r\n\r\n{message}".encode())
    client.close()


if __name__ == "__main__":
    sys.exit(main())