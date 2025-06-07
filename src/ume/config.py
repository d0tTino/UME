import os

class Settings:
    def __init__(self) -> None:
        self.UME_API_TOKEN = os.environ.get("UME_API_TOKEN", "secret-token")

settings = Settings()

