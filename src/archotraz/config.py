from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of true/false, 1/0, yes/no, on/off")


@dataclass(frozen=True, slots=True)
class ArchotrazConfig:
    db_path: Path = Path(".archotraz/archotraz.db")
    dry_mode: bool = True
    bopo_base_url: str = "http://localhost:4020"
    bopo_company_id: str | None = None
    bopo_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "ArchotrazConfig":
        timeout_raw = os.getenv("ARCHOTRAZ_BOPO_TIMEOUT_SECONDS", "10")
        timeout = float(timeout_raw)
        if timeout <= 0:
            raise ValueError("ARCHOTRAZ_BOPO_TIMEOUT_SECONDS must be greater than zero")
        return cls(
            db_path=Path(os.getenv("ARCHOTRAZ_DB_PATH", ".archotraz/archotraz.db")),
            dry_mode=_env_bool("ARCHOTRAZ_DRY_MODE", True),
            bopo_base_url=os.getenv("ARCHOTRAZ_BOPO_URL", "http://localhost:4020").rstrip("/"),
            bopo_company_id=os.getenv("ARCHOTRAZ_BOPO_COMPANY_ID") or None,
            bopo_timeout_seconds=timeout,
        )
