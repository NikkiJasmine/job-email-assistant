"""One-time local script to obtain a Gmail OAuth refresh token.

Run this ONCE, locally, after creating a Desktop-app OAuth client in Google
Cloud Console. It opens a browser for consent, then prints the resulting
refresh_token -- store that as the GOOGLE_REFRESH_TOKEN GitHub secret.

This script never runs in CI and is not imported by any part of the
automated pipeline.

Usage:
    python scripts/local_oauth_bootstrap.py --client-id <id> --client-secret <secret>
"""

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    args = parser.parse_args()

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # access_type=offline + prompt=consent force Google to issue a refresh_token
    # even if this Google account has consented to this app before.
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    print("\nSuccess. Store this as the GOOGLE_REFRESH_TOKEN GitHub secret:\n")
    print(credentials.refresh_token)
    print(
        "\nNote: if this prints nothing (None), you likely already consented once "
        "before without requesting offline access. Revoke access at "
        "https://myaccount.google.com/permissions and re-run this script."
    )


if __name__ == "__main__":
    main()
