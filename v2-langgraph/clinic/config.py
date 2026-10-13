import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv(override=True)  # the file wins over stale values injected by the IDE / shell


def _env(name: str, default: str = "") -> str:
    """Environment value with any trailing '# comment' and whitespace removed."""
    return os.getenv(name, default).split(" #")[0].split("\t#")[0].strip()


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    staff_chat_id: int
    database_url: str
    chat_model: str
    embedding_model: str
    embedding_dims: int
    timezone: str
    rate_limit_per_hour: int
    memory_window: int
    retrieval_min_similarity: float
    price_in_per_m: float
    price_out_per_m: float


@lru_cache
def get_settings() -> Settings:
    e = _env
    return Settings(
        telegram_token=e("TELEGRAM_BOT_TOKEN", ""),
        staff_chat_id=int(e("STAFF_CHAT_ID", "0")),
        database_url=e("DATABASE_URL", "postgresql://clinic:clinic@localhost:5432/clinic"),
        chat_model=e("CHAT_MODEL", "gemini-3.5-flash-lite"),
        embedding_model=e("EMBEDDING_MODEL", "models/gemini-embedding-001"),
        embedding_dims=int(e("EMBEDDING_DIMS", "768")),
        timezone=e("CLINIC_TIMEZONE", "Africa/Cairo"),
        rate_limit_per_hour=int(e("RATE_LIMIT_PER_HOUR", "20")),
        memory_window=int(e("MEMORY_WINDOW", "20")),
        retrieval_min_similarity=float(e("RETRIEVAL_MIN_SIMILARITY", "0.5")),
        price_in_per_m=float(e("PRICE_IN_PER_M", "0.10")),
        price_out_per_m=float(e("PRICE_OUT_PER_M", "0.40")),
    )
