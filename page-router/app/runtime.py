"""One router per GUI process, including optional startup benchmark runs."""
from functools import lru_cache
from app.engine import Router


@lru_cache(maxsize=1)
def resident_router():
    return Router()
