import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

JSONBIN_API_KEY = os.getenv("JSONBIN_API_KEY", "")
JSONBIN_BIN_ID = os.getenv("JSONBIN_BIN_ID", "")

JSONBIN_READ_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}/latest"
JSONBIN_UPDATE_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

HEADERS = {
    "Content-Type": "application/json",
    "X-Master-Key": JSONBIN_API_KEY
}

# Local cache to avoid too many API calls
_cache = None

DEFAULT_MAPPING = {}


def load_mapping():
    """Load mapping from JSONBin.io (with local cache)."""
    global _cache

    # Return cache if available
    if _cache is not None:
        return _cache

    # If JSONBin not configured, use local file fallback
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        return _load_local()

    try:
        response = requests.get(JSONBIN_READ_URL, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json().get("record", DEFAULT_MAPPING)
            _cache = data
            print(f"[STORAGE] JSONBin'dan {len(data)} ta kalit yuklandi.")
            return _cache
        else:
            print(f"[STORAGE] JSONBin xatolik: {response.status_code} — mahalliy faylga o'tilmoqda.")
            return _load_local()
    except Exception as e:
        print(f"[STORAGE] JSONBin ulanish xatoligi: {e} — mahalliy faylga o'tilmoqda.")
        return _load_local()


def save_mapping(mapping):
    """Save mapping to JSONBin.io and update local cache."""
    global _cache
    _cache = mapping

    # If JSONBin not configured, save locally
    if not JSONBIN_API_KEY or not JSONBIN_BIN_ID:
        _save_local(mapping)
        return True

    try:
        response = requests.put(
            JSONBIN_UPDATE_URL,
            headers=HEADERS,
            json=mapping,
            timeout=10
        )
        if response.status_code == 200:
            print(f"[STORAGE] JSONBin'ga {len(mapping)} ta kalit saqlandi.")
            return True
        else:
            print(f"[STORAGE] JSONBin saqlashda xatolik: {response.status_code}")
            _save_local(mapping)
            return False
    except Exception as e:
        print(f"[STORAGE] JSONBin saqlash xatoligi: {e}")
        _save_local(mapping)
        return False


def invalidate_cache():
    """Force reload from JSONBin on next call."""
    global _cache
    _cache = None


# --- Local file fallback ---
LOCAL_FILE = os.path.join(os.path.dirname(__file__), "mapping.json")


def _load_local():
    """Load from local mapping.json as fallback."""
    try:
        if os.path.exists(LOCAL_FILE):
            with open(LOCAL_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[STORAGE] Mahalliy fayldan {len(data)} ta kalit yuklandi.")
                return data
    except Exception as e:
        print(f"[STORAGE] Mahalliy fayl o'qish xatoligi: {e}")
    return {}


def _save_local(mapping):
    """Save to local mapping.json as fallback."""
    try:
        with open(LOCAL_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(f"[STORAGE] Mahalliy faylga {len(mapping)} ta kalit saqlandi.")
    except Exception as e:
        print(f"[STORAGE] Mahalliy fayl saqlash xatoligi: {e}")


def set_caption(msg_id: int, caption: str):
    """Save cleaned caption for a message_id."""
    mapping = load_mapping()
    if "_captions" not in mapping:
        mapping["_captions"] = {}
    mapping["_captions"][str(msg_id)] = caption
    save_mapping(mapping)


def get_caption(msg_id: int):
    """Retrieve cleaned caption for a message_id if available."""
    mapping = load_mapping()
    captions = mapping.get("_captions", {})
    return captions.get(str(msg_id))


def add_message(key: str, msg_id: int, caption: str = None) -> bool:
    """Add a message_id to a topic key with optional clean caption. Returns True if added/updated."""
    mapping = load_mapping()
    if key not in mapping:
        mapping[key] = []

    changed = False
    if msg_id not in mapping[key]:
        mapping[key].append(msg_id)
        changed = True

    if caption is not None:
        if "_captions" not in mapping:
            mapping["_captions"] = {}
        mapping["_captions"][str(msg_id)] = caption
        changed = True

    if changed:
        save_mapping(mapping)
        return True
    return False


def remove_message(key: str, msg_id: int) -> bool:
    """Remove a specific message_id from a topic key. Returns True if removed."""
    mapping = load_mapping()
    if key in mapping and msg_id in mapping[key]:
        mapping[key].remove(msg_id)
        if not mapping[key]:
            del mapping[key]
        if "_captions" in mapping and str(msg_id) in mapping["_captions"]:
            del mapping["_captions"][str(msg_id)]
        save_mapping(mapping)
        return True
    return False


def clear_topic(key: str) -> bool:
    """Remove all messages for a topic key."""
    mapping = load_mapping()
    if key in mapping:
        msg_ids = mapping[key]
        del mapping[key]
        if "_captions" in mapping:
            for mid in msg_ids:
                mapping["_captions"].pop(str(mid), None)
        save_mapping(mapping)
        return True
    return False


def get_messages(key: str) -> list:
    """Get all message_ids for a topic key."""
    mapping = load_mapping()
    return mapping.get(key, [])


def list_topics() -> list:
    """Return all topic keys that have at least one message."""
    mapping = load_mapping()
    return [(k, len(v)) for k, v in mapping.items() if v and not k.startswith("_")]
