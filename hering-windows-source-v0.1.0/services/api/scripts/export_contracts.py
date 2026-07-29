"""Export REST and realtime schemas from the FastAPI/Pydantic source of truth."""

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from app.main import create_app  # noqa: E402
from app.schemas import RealtimeEnvelope  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    schema_root = PROJECT_ROOT / "packages" / "contracts" / "schema"
    write_json(schema_root / "openapi.json", create_app().openapi())
    write_json(schema_root / "realtime.schema.json", RealtimeEnvelope.model_json_schema())
