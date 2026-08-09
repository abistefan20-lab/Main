import pandas as pd

from scripts.analiza_raze_staer import (
    ADDRESS_COLUMNS,
    canonical_text,
    responsible_address_mask,
)


def test_canonical_text_normalizes_only_case_and_whitespace():
    assert canonical_text("  Șoseaua   Colentina ") == "șoseaua colentina"


def test_responsible_address_excludes_placeholders_but_keeps_unassigned_sector():
    rows = pd.DataFrame(
        [
            ["calea victoriei", "sector 1", "sector 1", "bucurești"],
            ["strada lalelelor", "voluntari", "—", "ilfov"],
            ["necunoscută", "sector 2", "sector 2", "bucurești"],
            ["strada florilor", "1191", "—", "ilfov"],
        ],
        columns=ADDRESS_COLUMNS,
    )
    assert responsible_address_mask(rows).tolist() == [True, True, False, False]
