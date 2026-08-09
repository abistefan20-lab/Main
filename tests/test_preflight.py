import pandas as pd

from scripts.analiza_raze_staer import (
    ADDRESS_COLUMNS,
    canonical_text,
    haversine,
    responsible_address_mask,
    weighted_quantile,
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


def test_haversine_is_zero_for_same_point():
    assert haversine(44.4, 26.1, 44.4, 26.1) == 0


def test_weighted_quantile_weights_clients_not_addresses():
    values = pd.Series([1.0, 10.0])
    weights = pd.Series([9, 1])
    assert weighted_quantile(values, weights, .8) == 1.0
