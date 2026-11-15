import json
from pathlib import Path

from app.eastbank import build_map_document

if __name__ == "__main__":
    output = Path(__file__).resolve().parents[2] / "shared" / "eastbank_grid.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_map_document(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
