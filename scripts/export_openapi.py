import json
from pathlib import Path

from server.main import app

OUTPUT = Path(__file__).resolve().parent.parent / "specs" / "openapi.json"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
