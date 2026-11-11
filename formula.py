"""分子式解析与分子量计算"""
import re

# 常用元素原子量（IUPAC 平均原子量）
ATOMIC_WEIGHTS = {
    "H": 1.008, "He": 4.0026, "Li": 6.94, "Be": 9.0122, "B": 10.81, "C": 12.011,
    "N": 14.007, "O": 15.999, "F": 18.998, "Ne": 20.180, "Na": 22.990, "Mg": 24.305,
    "Al": 26.982, "Si": 28.085, "P": 30.974, "S": 32.06, "Cl": 35.45, "Ar": 39.948,
    "K": 39.098, "Ca": 40.078, "Sc": 44.956, "Ti": 47.867, "V": 50.942, "Cr": 51.996,
    "Mn": 54.938, "Fe": 55.845, "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38,
    "Ga": 69.723, "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904, "Kr": 83.798,
    "Rb": 85.468, "Sr": 87.62, "Y": 88.906, "Zr": 91.224, "Nb": 92.906, "Mo": 95.95,
    "Ru": 101.07, "Rh": 102.906, "Pd": 106.42, "Ag": 107.868, "Cd": 112.414, "In": 114.818,
    "Sn": 118.710, "Sb": 121.760, "Te": 127.60, "I": 126.904, "Xe": 131.293, "Cs": 132.905,
    "Ba": 137.327, "La": 138.905, "Ce": 140.116, "Pr": 140.908, "Nd": 144.242,
    "Sm": 150.36, "Eu": 151.964, "Gd": 157.25, "Tb": 158.925, "Dy": 162.500,
    "Ho": 164.930, "Er": 167.259, "Tm": 168.934, "Yb": 173.045, "Lu": 174.967,
    "Hf": 178.49, "Ta": 180.948, "W": 183.84, "Re": 186.207, "Os": 190.23, "Ir": 192.217,
    "Pt": 195.084, "Au": 196.967, "Hg": 200.592, "Tl": 204.38, "Pb": 207.2, "Bi": 208.980,
    "Th": 232.038, "U": 238.029,
}

TOKEN_RE = re.compile(r"([A-Z][a-z]?)|(\()|(\))|(\d+)")


class FormulaError(ValueError):
    pass


def parse_formula(formula: str) -> dict:
    """解析分子式，支持括号和数字，如 C6H12O6、(NH4)2SO4"""
    formula = formula.strip().replace(" ", "")
    if not formula:
        raise FormulaError("Empty formula")

    stack = [{}]
    tokens = TOKEN_RE.findall(formula)
    if not tokens:
        raise FormulaError("Cannot parse formula")

    i = 0
    while i < len(tokens):
        element, open_p, close_p, number = tokens[i]
        if open_p:
            stack.append({})
            i += 1
            continue

        if close_p:
            if len(stack) < 2:
                raise FormulaError("Unbalanced parentheses")
            block = stack.pop()
            mult = 1
            if i + 1 < len(tokens) and tokens[i + 1][3]:
                mult = int(tokens[i + 1][3])
                i += 1
            for el, cnt in block.items():
                stack[-1][el] = stack[-1].get(el, 0) + cnt * mult
            i += 1
            continue

        if element:
            if element not in ATOMIC_WEIGHTS:
                raise FormulaError(f"Unknown element: {element}")
            n = 1
            if i + 1 < len(tokens) and tokens[i + 1][3]:
                n = int(tokens[i + 1][3])
                i += 1
            stack[-1][element] = stack[-1].get(element, 0) + n
            i += 1
            continue

        raise FormulaError("Unexpected number in formula")

    if len(stack) != 1:
        raise FormulaError("Unbalanced parentheses")
    result = {k: v for k, v in stack[0].items() if v > 0}
    if not result:
        raise FormulaError("No elements found")
    return result


def hill_notation(counts: dict) -> str:
    """Hill 顺序：C、H，其余按字母序"""
    parts = []
    remaining = dict(counts)
    if "C" in remaining:
        parts.append(("C", remaining.pop("C")))
        if "H" in remaining:
            parts.append(("H", remaining.pop("H")))
    for el in sorted(remaining):
        parts.append((el, remaining[el]))
    return "".join(el + (str(n) if n > 1 else "") for el, n in parts)


def molecular_weight(counts: dict) -> float:
    return sum(ATOMIC_WEIGHTS[el] * n for el, n in counts.items())


def composition(counts: dict):
    total = molecular_weight(counts)
    rows = []
    for el, n in sorted(counts.items(), key=lambda kv: -ATOMIC_WEIGHTS[kv[0]] * kv[1]):
        mass = ATOMIC_WEIGHTS[el] * n
        rows.append({
            "element": el,
            "count": n,
            "mass": round(mass, 4),
            "percent": round(mass / total * 100, 2) if total else 0.0,
        })
    return rows
