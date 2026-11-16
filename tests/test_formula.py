import pytest

from formula import FormulaError, composition, hill_notation, molecular_weight, parse_formula


def test_glucose_formula_and_weight():
    counts = parse_formula("C6H12O6")
    assert counts == {"C": 6, "H": 12, "O": 6}
    assert hill_notation(counts) == "C6H12O6"
    assert molecular_weight(counts) == pytest.approx(180.156, abs=0.01)


def test_brackets_and_multipliers():
    counts = parse_formula("(NH4)2SO4")
    assert counts == {"N": 2, "H": 8, "S": 1, "O": 4}


def test_composition_percentages_sum_to_100():
    rows = composition(parse_formula("C2H6O"))
    assert round(sum(row["percent"] for row in rows), 1) == 100.0
    assert {row["element"] for row in rows} == {"C", "H", "O"}


@pytest.mark.parametrize("bad", ["", "C6H12O)", "Xx2", "C(6)"])
def test_invalid_formula(bad):
    with pytest.raises(FormulaError):
        parse_formula(bad)
