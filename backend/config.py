import os
import secrets
from pathlib import Path
from dataclasses import dataclass


def _load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


ROOT_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = bool(os.getenv("VERCEL"))
# Vercel's filesystem is read-only except /tmp (ephemeral: exports/uploads only, DB lives in Postgres).
DATA_DIR = Path("/tmp/data") if IS_VERCEL else ROOT_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "presales_command.db"
MASTER_KEY_FILE = DATA_DIR / ".master.key"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

_load_dotenv(ROOT_DIR / ".env")


def _get_or_create_master_key() -> bytes:
    env_key = os.getenv("APP_MASTER_KEY", "").strip()
    if env_key:
        return env_key.encode("utf-8")
    if IS_VERCEL:
        # A generated key would change on every cold start and make stored secrets undecryptable.
        raise RuntimeError("APP_MASTER_KEY env var is required on Vercel.")
    if MASTER_KEY_FILE.exists():
        return MASTER_KEY_FILE.read_bytes().strip()
    generated = secrets.token_urlsafe(48).encode("utf-8")
    MASTER_KEY_FILE.write_bytes(generated)
    try:
        os.chmod(MASTER_KEY_FILE, 0o600)
    except OSError:
        pass
    return generated


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8080"))
    env: str = os.getenv("APP_ENV", "production")
    master_key: bytes = _get_or_create_master_key()
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "12"))
    default_gemini_key: str = os.getenv("GEMINI_API_KEY", "")
    default_openai_key: str = os.getenv("OPENAI_API_KEY", "")
    default_anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    google_oauth_client_id: str = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    google_oauth_client_secret: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    whatsapp_verify_token: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "presales_ai_verify_token_change_me")
    whatsapp_app_secret: str = os.getenv("WHATSAPP_APP_SECRET", "")
    whatsapp_access_token: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


settings = Settings()
