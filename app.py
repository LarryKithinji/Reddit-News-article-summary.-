import random
import socket
import sys
import praw
import urllib.parse

def main():
    """Main function to generate a Reddit refresh token without user prompt."""

    # Set your Reddit credentials here
    client_id = "p4SHQ57gs2X_bMtaARiJvw"
    client_secret = "PVwX9RTdLj99l1lU9LkvPTEUNmotyQ"
    redirect_uri = "http://localhost:8080"
    user_agent = "obtain_refresh_token/v0 by u/Beginning_Item_9587"  # Updated with actual username

    # Define scopes here (e.g., read, submit, identity)
    scopes = ["identity", "read", "submit", "edit", "save", "vote"]  # Fixed: removed invalid scopes

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        user_agent=user_agent,
    )

    state = str(random.randint(0, 65000))
    url = reddit.auth.url(duration="permanent", scopes=scopes, state=state)

    print("\n🔗 Now open this URL in your browser and approve access:")
    print(url)
    print("\n🌐 Waiting for Reddit to redirect...")

    try:
        client = receive_connection()
        data = client.recv(1024).decode("utf-8")
        
        # Fixed: Better URL parsing with error handling
        try:
            request_line = data.split("\r\n")[0]  # Get first line of HTTP request
            path = request_line.split(" ")[1]  # Extract path from "GET /path HTTP/1.1"
            
            if "?" in path:
                query_string = path.split("?", 1)[1]
                # Handle URL fragments (remove #_ if present)
                if "#" in query_string:
                    query_string = query_string.split("#")[0]
                
                params = urllib.parse.parse_qs(query_string)
                # Convert lists to single values
                params = {k: v[0] if isinstance(v, list) and v else v for k, v in params.items()}
            else:
                send_message(client, "Error: No parameters found in redirect URL")
                return 1
                
        except (IndexError, ValueError) as e:
            send_message(client, f"Error parsing request: {e}")
            return 1

        # Verify state parameter
        if state != params.get("state"):
            send_message(
                client,
                f"State mismatch. Expected: {state} Received: {params.get('state')}",
            )
            return 1
        elif "error" in params:
            send_message(client, f"Error: {params['error']}")
            return 1
        elif "code" not in params:
            send_message(client, "Error: No authorization code received")
            return 1

        # Exchange code for refresh token
        try:
            refresh_token = reddit.auth.authorize(params["code"])
            success_msg = f"✅ SUCCESS! Your refresh token is:\n\n{refresh_token}\n\n💾 Store it safely - this token never expires!"
            send_message(client, success_msg)
            
            print("\n" + "="*60)
            print("✅ Refresh token obtained successfully:")
            print("="*60)
            print(refresh_token)
            print("="*60)
            print("\n🔧 Use it like this in your Reddit bots:")
            print("reddit = praw.Reddit(")
            print(f"    client_id='{client_id}',")
            print(f"    client_secret='{client_secret}',")
            print(f"    refresh_token='{refresh_token}',")
            print(f"    user_agent='{user_agent}'")
            print(")")
            
            return 0
            
        except Exception as e:
            error_msg = f"❌ Error getting refresh token: {e}"
            send_message(client, error_msg)
            print(error_msg)
            return 1
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return 1


def receive_connection():
    """Wait for and return a client socket connected on localhost:8080."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Try multiple ports if 8080 is busy
    ports_to_try = [8080, 8081, 8082, 8083]
    
    for port in ports_to_try:
        try:
            server.bind(("localhost", port))
            print(f"✅ Server listening on port {port}")
            break
        except OSError:
            print(f"❌ Port {port} is busy, trying next...")
            continue
    else:
        raise Exception("Could not bind to any available port")
    
    server.listen(1)
    client_socket, address = server.accept()
    print(f"🔗 Connection received from {address}")
    server.close()
    return client_socket


def send_message(client, message):
    """Send a message to the browser and close the socket."""
    print(f"📤 Sending to browser: {message}")
    
    # Proper HTTP response
    response = f"""HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Connection: close

<!DOCTYPE html>
<html>
<head>
    <title>Reddit OAuth</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .success {{ color: green; }}
        .error {{ color: red; }}
        pre {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h2>Reddit OAuth Result</h2>
    <div class="{'success' if 'SUCCESS' in message else 'error'}">
        <pre>{message}</pre>
    </div>
    <p><strong>You can close this browser window now.</strong></p>
</body>
</html>"""
    
    try:
        client.send(response.encode('utf-8'))
    except Exception as e:
        print(f"Error sending response: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    print("🚀 Reddit Refresh Token Generator")
    print("="*50)
    sys.exit(main())