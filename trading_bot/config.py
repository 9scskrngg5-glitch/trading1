import os

class TradingConfig:
    def __init__(self):
        self.api_key = os.getenv('TRADING_API_KEY')
        self.api_secret = os.getenv('TRADING_API_SECRET')
        self.base_url = os.getenv('TRADING_BASE_URL')

    def validate(self):
        if not self.api_key or not self.api_secret or not self.base_url:
            raise ValueError('Missing configuration variables')
