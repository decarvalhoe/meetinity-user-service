import os
import secrets

from authlib.integrations.flask_client import OAuth


oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        access_token_url="https://oauth2.googleapis.com/token",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        client_kwargs={"scope": "openid email profile"},
    )
    oauth.register(
        name="linkedin",
        client_id=os.getenv("LINKEDIN_CLIENT_ID"),
        client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
        access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
        authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        client_kwargs={"scope": "r_liteprofile r_emailaddress"},
        api_base_url="https://api.linkedin.com/v2",
    )


def generate_state() -> str:
    return secrets.token_urlsafe(16)


def generate_nonce() -> str:
    return secrets.token_urlsafe(16)


def build_auth_url(  # pragma: no cover
    provider: str,
    redirect_uri: str,
    state: str,
    nonce: str | None = None,
) -> str:
    client = oauth.create_client(provider)
    params = {"redirect_uri": redirect_uri, "state": state}
    if nonce:
        params["nonce"] = nonce
    url, _ = client.create_authorization_url(**params)
    return url


def fetch_user_info(  # pragma: no cover
    provider: str,
    code: str,
    redirect_uri: str,
    nonce: str | None = None,
):
    """Exchange code for token and retrieve user info."""
    client = oauth.create_client(provider)
    token = client.fetch_token(code=code, redirect_uri=redirect_uri)
    if provider == "google":
        return client.parse_id_token(token, nonce=nonce)
    if provider == "linkedin":
        resp = client.get("userinfo", token=token)
        return resp.json()
    raise ValueError("unsupported provider")
