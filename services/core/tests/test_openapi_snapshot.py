import json
import os
from pathlib import Path

SNAPSHOT = Path(__file__).parent.parent / "openapi.json"


async def test_openapi_schema_matches_the_committed_snapshot(app):
    current = json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("NOVA_UPDATE_SNAPSHOTS") == "1":
        SNAPSHOT.write_text(current, encoding="utf-8", newline="\n")
    assert SNAPSHOT.read_text(encoding="utf-8") == current
