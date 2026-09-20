from store import CACHE, fetch


def load(key, schedule):
    if key in CACHE:
        return CACHE[key]
    schedule(refresh, key)
    return None


def refresh(key):
    CACHE[key] = fetch(key)
