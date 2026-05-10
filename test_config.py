import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print("CWD:", os.getcwd())
print("BINANCE_API_KEY from os:", os.getenv('BINANCE_API_KEY'))

from pydantic_settings import BaseSettingsModel

class TestSettings(BaseSettingsModel):
    BINANCE_API_KEY: str = "default"

    class Config:
        env_file = ".env"

s = TestSettings()
print("Pydantic BINANCE_API_KEY:", s.BINANCE_API_KEY)
