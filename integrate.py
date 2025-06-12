import requests

class ConnectToIntegrate:
    BASE_URL = "https://integrate.definedgesecurities.com/dart/v1"

    def __init__(self):
        self.api_token = None
        self.api_secret = None
        self.uid = None
        self.actid = None
        self.api_session_key = None
        self.ws_session_key = None

    def login(self, api_token, api_secret):
        self.api_token = api_token
        self.api_secret = api_secret

    def set_session_keys(self, uid, actid, api_session_key, ws_session_key):
        self.uid = uid
        self.actid = actid
        self.api_session_key = api_session_key
        self.ws_session_key = ws_session_key

    @property
    def headers(self):
        # For holdings/positions, the session key is also required in Authorization header (per your Colab logic)
        base = {
            "x-api-key": self.api_token,
            "x-api-secret": self.api_secret,
        }
        # Attach session key if available
        if self.api_session_key:
            base["Authorization"] = self.api_session_key
        return base

class IntegrateOrders:
    def __init__(self, conn):
        self.conn = conn

    def holdings(self):
        url = f"{self.conn.BASE_URL}/holdings"
        resp = requests.get(url, headers=self.conn.headers)
        resp.raise_for_status()
        return resp.json()

    def positions(self):
        url = f"{self.conn.BASE_URL}/positions"
        resp = requests.get(url, headers=self.conn.headers)
        resp.raise_for_status()
        return resp.json()
