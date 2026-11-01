import importlib.util
import json
from pathlib import Path

EVALS = Path(__file__).parents[1] / "evals"


def _load_exporter():
    spec = importlib.util.spec_from_file_location("export_hf", EVALS / "export_hf.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_has_flat_stable_schema_and_round_trips(tmp_path: Path) -> None:
    exporter = _load_exporter()
    rows = exporter.export(tmp_path)

    lines = (tmp_path / "data" / "test.jsonl").read_text(encoding="utf-8").splitlines()
    source = [
        json.loads(line)
        for line in (EVALS / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == len(rows) == len(source)

    exported = [json.loads(line) for line in lines]
    assert len({tuple(sorted(r)) for r in exported}) == 1
    for case, row in zip(source, exported, strict=True):
        for name in exporter.JSON_FIELDS:
            decoded = None if row[name] is None else json.loads(row[name])
            assert decoded == case.get(name)

    card = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert card.startswith("---\n")
    assert "path: data/test.jsonl" in card
    assert f"There are {len(source)} cases" in card
    assert "amitdutta121/mythinking-evals" in card
