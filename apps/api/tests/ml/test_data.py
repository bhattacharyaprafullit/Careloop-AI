"""M2 unit tests: deterministic hashes, stage positive rates 15-35%, no leakage, 60 seed cases."""
import json
import logging
from pathlib import Path

from ml.data.generate import DEFAULT_ARTIFACTS_DIR, generate_dataset
from ml.data.schema import FEATURE_COLUMNS, FORBIDDEN_DEMOGRAPHIC_COLUMNS, STAGE_SEQUENCE

logger = logging.getLogger(__name__)


def test_generator_deterministic_hashes_and_rates(tmp_path: Path) -> None:
    """Running generate_dataset(seed=42) twice yields identical hashes and 15-35% rates."""
    out1 = tmp_path / "run1"
    art1 = tmp_path / "art1"
    res1 = generate_dataset(seed=42, out_dir=out1, artifacts_dir=art1)

    out2 = tmp_path / "run2"
    art2 = tmp_path / "art2"
    res2 = generate_dataset(seed=42, out_dir=out2, artifacts_dir=art2)

    assert res1["hashes"] == res2["hashes"]
    assert res1["n_patients"] == 12000
    assert res1["seed_cases"] == 60

    for st in STAGE_SEQUENCE:
        rate = res1["stage_positive_rates"][st]
        assert 0.15 <= rate <= 0.35, f"Stage {st} rate {rate} out of bounds"


def test_no_leakage_or_forbidden_demographics() -> None:
    assert not (set(FEATURE_COLUMNS) & FORBIDDEN_DEMOGRAPHIC_COLUMNS)
    assert "dropoff" not in FEATURE_COLUMNS
    assert "closed_flag" not in FEATURE_COLUMNS
    assert "stage_hours" not in FEATURE_COLUMNS


def test_seed_json_has_60_cases_and_12_archetypes() -> None:
    seed_file = DEFAULT_ARTIFACTS_DIR / "seed.json"
    assert seed_file.exists(), "ml/artifacts/seed.json must be generated"
    data = json.loads(seed_file.read_text(encoding="utf-8"))
    assert data["case_count"] == 60
    assert len(data["cases"]) == 60

    by_arch: dict[int, int] = {}
    langs: set[str] = set()
    screenings: set[str] = set()
    for c in data["cases"]:
        aid = int(c["archetype_id"])
        by_arch[aid] = by_arch.get(aid, 0) + 1
        langs.add(c["patient"]["language"])
        screenings.add(c["case"]["screening_type"])
        assert len(c["events"]) >= 1
        assert len(c["messages"]) >= 1
        assert len(c["llm_outputs"]) >= 3
        assert c["case"]["patient_token"]
        assert c["case"]["patient_token_hash"]

    assert len(by_arch) == 12
    assert all(v == 5 for v in by_arch.values())
    assert langs == {"en", "hi", "es"}
    assert screenings == {"FIT", "MAMMOGRAPHY", "PAP_HPV"}
