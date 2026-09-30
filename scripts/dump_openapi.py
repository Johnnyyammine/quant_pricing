"""Write the API's OpenAPI schema to api/openapi.json (source for web/src/api/schema.d.ts)."""

import json
from pathlib import Path

from api.app import create_app

OUT = Path(__file__).resolve().parent.parent / "api" / "openapi.json"

if __name__ == "__main__":
    schema = create_app(web_dist=None).openapi()
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT}")
