import requests

class ConnectToIntegrate:
    BASE_URL = "https://integrate.definedgesecurities.com/dart/v1"

    def __init__(self):
        self.api_token = None
        self.api_secret = None

    def login(self, api_token, api_secret):
        # DO NOT make any HTTP request here!
        self.api_token = api_token
        self.api_secret = api_secret

    @property
    def headers(self):
        return {
            "Authorization": self.api_token,
            "x-api-secret": self.api_secret
        }

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

    def place_gtt_order(self, **kwargs):
        url = f"{self.conn.BASE_URL}/gtt"
        resp = requests.post(url, headers={**self.conn.headers, "Content-Type": "application/json"}, json=kwargs)
        resp.raise_for_status()
        return resp.json()

    def place_oco_order(self, **kwargs):
        url = f"{self.conn.BASE_URL}/oco"
        resp = requests.post(url, headers={**self.conn.headers, "Content-Type": "application/json"}, json=kwargs)
        resp.raise_for_status()
        return resp.json()
