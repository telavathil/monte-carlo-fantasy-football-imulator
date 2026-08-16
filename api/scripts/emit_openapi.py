"""Emit OpenAPI JSON from the FastAPI app for the TS client generator."""
from __future__ import annotations
import json
import pathlib
from app.main import create_app


def main():
    app = create_app()
    out = pathlib.Path(__file__).parents[2] / "shared" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
