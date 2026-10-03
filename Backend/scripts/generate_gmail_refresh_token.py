import base64
import hashlib
import json
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import dotenv_values


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    expected_state = ""
    authorization_code = None
    authorization_error = None
    callback_received = threading.Event()

    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if query.get("state", [None])[0] != self.expected_state:
            self.send_error(400, "OAuth state validation failed.")
            return

        handler = type(self)
        handler.authorization_error = query.get("error", [None])[0]
        handler.authorization_code = query.get("code", [None])[0]
        handler.callback_received.set()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"Google authorization received. You can close this browser tab."
        )

    def log_message(self, _format, *_args):
        return


def save_refresh_token(refresh_token: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated_lines = []
    token_written = False

    for line in lines:
        if line.lstrip().startswith("GMAIL_REFRESH_TOKEN="):
            if not token_written:
                updated_lines.append(f"GMAIL_REFRESH_TOKEN={refresh_token}")
                token_written = True
        else:
            updated_lines.append(line)

    if not token_written:
        updated_lines.append(f"GMAIL_REFRESH_TOKEN={refresh_token}")

    ENV_PATH.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def main() -> None:
    if not ENV_PATH.exists():
        raise SystemExit(f"Backend .env file not found: {ENV_PATH}")

    env = dotenv_values(ENV_PATH)
    client_id = env.get("GMAIL_CLIENT_ID")
    client_secret = env.get("GMAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in Backend/.env first."
        )

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    OAuthCallbackHandler.expected_state = state
    OAuthCallbackHandler.authorization_code = None
    OAuthCallbackHandler.authorization_error = None
    OAuthCallbackHandler.callback_received = threading.Event()

    try:
        server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), OAuthCallbackHandler)
    except OSError as exc:
        raise SystemExit(
            f"Could not listen on {CALLBACK_HOST}:{CALLBACK_PORT}. "
            "Close the process using that port and retry."
        ) from exc
    server.timeout = 180
    redirect_uri = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}/"
    authorization_url = AUTHORIZATION_ENDPOINT + "?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SEND_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    print("Opening Google sign-in. Approve Gmail send access for your sender account.")
    print("If the browser does not open, visit this URL:")
    print(authorization_url)
    webbrowser.open(authorization_url)

    try:
        server.handle_request()
    finally:
        server.server_close()

    if not OAuthCallbackHandler.callback_received.is_set():
        raise SystemExit(
            "No Google authorization callback arrived within 3 minutes. Run the script again."
        )
    if OAuthCallbackHandler.authorization_error:
        raise SystemExit(
            "Google authorization was not completed: "
            f"{OAuthCallbackHandler.authorization_error}"
        )
    if not OAuthCallbackHandler.authorization_code:
        raise SystemExit("Google did not return an authorization code.")

    token_request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": OAuthCallbackHandler.authorization_code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        ).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(token_request, timeout=20) as response:
            token_response = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            error_response = json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            error_response = {}
        provider_error = error_response.get("error")
        error_description = error_response.get("error_description")
        reason = ": ".join(
            value
            for value in (provider_error, error_description)
            if isinstance(value, str) and value
        )
        raise SystemExit(
            f"Google token exchange failed (HTTP {exc.code})"
            f"{': ' + reason if reason else '.'}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(
            "Could not reach Google's token endpoint. Check your internet connection."
        ) from exc

    refresh_token = token_response.get("refresh_token")
    if not refresh_token:
        raise SystemExit(
            "Google did not issue a refresh token. Confirm the OAuth consent screen "
            "includes your account as a test user, then revoke this app's access "
            "from your Google Account and run the script again."
        )

    save_refresh_token(refresh_token)
    print(f"Refresh token saved to {ENV_PATH}. Do not commit or share this file.")
    print(
        "For Render, copy GMAIL_REFRESH_TOKEN from your local .env into the "
        "Web Service environment settings."
    )


if __name__ == "__main__":
    main()
