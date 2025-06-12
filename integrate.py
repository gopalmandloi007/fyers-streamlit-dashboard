import requests
import os

class ConnectToIntegrate:
    BASE_URL = "https://integrate.definedgesecurities.com/dart/v1"

    def __init__(self):
        self.api_session_key = None
        self.ws_session_key = None
        self.uid = None
        self.actid = None

    def login(self, api_token, api_secret):
        # This is a placeholder: Replace with actual Definedge login API if needed
        url = f"{self.BASE_URL}/login"
        data = {
            "api_token": api_token,
            "api_secret": api_secret
        }
        resp = requests.post(url, json=data)
        resp.raise_for_status()
        result = resp.json()
        # Adjust these keys as per actual API response
        self.api_session_key = result.get("api_session_key")
        self.ws_session_key = result.get("ws_session_key")
        self.uid = result.get("uid")
        self.actid = result.get("actid")
        return result

    def set_session_keys(self, uid, actid, api_session_key, ws_session_key):
        self.uid = uid
        self.actid = actid
        self.api_session_key = api_session_key
        self.ws_session_key = ws_session_key

    def get_session_keys(self):
        return self.uid, self.actid, self.api_session_key, self.ws_session_key

    @property
    def headers(self):
        return {"Authorization": self.api_session_key}

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

    def orders(self):
        url = f"{self.conn.BASE_URL}/orders"
        resp = requests.get(url, headers=self.conn.headers)
        resp.raise_for_status()
        return resp.json()

    def tradebook(self):
        url = f"{self.conn.BASE_URL}/tradebook"
        resp = requests.get(url, headers=self.conn.headers)
        resp.raise_for_status()
        return resp.json()

    def place_order(self, **kwargs):
        url = f"{self.conn.BASE_URL}/placeorder"
        resp = requests.post(url, headers={**self.conn.headers, "Content-Type": "application/json"}, json=kwargs)
        resp.raise_for_status()
        return resp.json()

    def modify_order(self, **kwargs):
        url = f"{self.conn.BASE_URL}/modify"
        resp = requests.post(url, headers={**self.conn.headers, "Content-Type": "application/json"}, json=kwargs)
        resp.raise_for_status()
        return resp.json()

    def cancel_order(self, order_id):
        url = f"{self.conn.BASE_URL}/cancel/{order_id}"
        resp = requests.get(url, headers=self.conn.headers)
        resp.raise_for_status()
        return resp.json()

    # Add more methods as per your needs (GTT, OCO etc.)