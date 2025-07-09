from functools import lru_cache
from . import Settings

@lru_cache(maxsize=1)
def load_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
