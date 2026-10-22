from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default="", repr=False)
    owner_token: str = field(default="", repr=False)
    owner_id: UUID = UUID("11111111-1111-4111-8111-111111111111")
    storage_root: Path = Path("workspace/command_center_dev/storage")
    lease_seconds: int = 90
    max_attempts: int = 3

    @classmethod
    def load(cls):
        values = {}
        if os.getenv("CC_CONFIG_FILE"):
            values = json.loads(Path(os.environ["CC_CONFIG_FILE"]).read_text(encoding="utf-8"))
        return cls(
            database_url=os.getenv("CC_DATABASE_URL", values.get("database_url", "")),
            owner_token=os.getenv("CC_OWNER_TOKEN", values.get("owner_token", "")),
            owner_id=UUID(os.getenv("CC_OWNER_ID", values.get("owner_id", str(cls.owner_id)))),
            storage_root=Path(os.getenv("CC_STORAGE_ROOT", values.get("storage_root", str(cls.storage_root)))).resolve(),
        )
