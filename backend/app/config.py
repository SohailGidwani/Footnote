"""Environment loading. Real keys live in backend/.env (never committed)."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_env_file(BACKEND_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def db_path() -> str:
    return env("DB_PATH", str(BACKEND_DIR / "footnote.db"))


def pack_path() -> Path:
    return Path(env("COMPANY_PACK_PATH", str(REPO_ROOT / "data" / "company_pack.json")))
