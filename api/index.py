from backend.database import init_db
from backend.main import app  # noqa: F401  (Vercel serves this ASGI app)

# Lifespan may not run on serverless; schema creation is idempotent.
init_db()
