import json
from pathlib import Path

import pytest

from app.moteurs.programme import Programme

DOSSIER_CAS = Path(__file__).parent / "cas_reference"


@pytest.fixture
def cas_reference() -> dict:
    return json.loads((DOSSIER_CAS / "villa_3ch.json").read_text(encoding="utf-8"))


@pytest.fixture
def programme_ref(cas_reference) -> Programme:
    return Programme(**cas_reference["programme"])
