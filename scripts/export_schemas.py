"""Write JSON Schemas for the measurement configuration (keeps config/*.schema.json in sync with code).

python scripts/export_schemas.py           # write
python scripts/export_schemas.py --check   # fail if out of date (used in tests/CI)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from meritvector_analytics.measurement.spec import JobFamilySpec, Ontology

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    ROOT / "config" / "job_families" / "schema.json": JobFamilySpec,
    ROOT / "config" / "measurement" / "ontology.schema.json": Ontology,
}


def render(model) -> str:
    schema = model.model_json_schema()
    schema["$id"] = f"https://meritvector.invalid/schemas/{model.__name__}/1.0"
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for path, model in TARGETS.items():
        text = render(model)
        if check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("out of date:", ", ".join(stale), "— run python scripts/export_schemas.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
