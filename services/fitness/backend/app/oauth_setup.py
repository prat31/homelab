from app.drive import run_oauth_setup


def main() -> None:
    client_id = input("Google OAuth client id: ").strip()
    client_secret = input("Google OAuth client secret: ").strip()
    refresh_token = run_oauth_setup(client_id=client_id, client_secret=client_secret)
    print("Add this to homelab .env as GOOGLE_OAUTH_REFRESH_TOKEN=")
    print(refresh_token)


if __name__ == "__main__":
    main()
