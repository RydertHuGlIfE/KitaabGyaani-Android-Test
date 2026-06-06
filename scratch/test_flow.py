from google_auth_oauthlib.flow import Flow

client_config = {
    "web": {
        "client_id": "dummy",
        "project_id": "dummy",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/dummy",
        "client_secret": "dummy",
        "redirect_uris": ["http://localhost:8000/callback"]
    }
}
flow = Flow.from_client_config(client_config, scopes=['https://www.googleapis.com/auth/calendar'])
flow.autogenerate_code_verifier = False

url, state = flow.authorization_url()
print("Url:", url)
print("Code verifier:", flow.code_verifier)
