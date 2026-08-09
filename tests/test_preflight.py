from scripts.analiza_raze_staer import canonical_text


def test_canonical_text_normalizes_only_case_and_whitespace():
    assert canonical_text("  Șoseaua   Colentina ") == "șoseaua colentina"
