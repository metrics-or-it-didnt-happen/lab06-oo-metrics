#!/usr/bin/env python3
"""OO Metrics Analyzer - Chidamber-Kemerer metrics for Python classes."""

import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ClassMetrics:
    name: str
    file: str
    lineno: int
    methods_count: int = 0
    wmc: int = 0
    dit: int = 0
    cbo: int = 0
    lcom: float = 0.0
    is_god_class: bool = False


class OOAnalyzer(ast.NodeVisitor):

    BUILTINS = {
        "str", "int", "float", "bool", "list", "dict", "set", "tuple",
        "object", "Exception", "None", "True", "False"
    }

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.classes: list[ClassMetrics] = []
        self.class_defs: dict[str, ast.ClassDef] = {}

    def visit_ClassDef(self, node: ast.ClassDef):
        self.class_defs[node.name] = node

        metrics = ClassMetrics(
            name=node.name,
            file=self.filepath,
            lineno=node.lineno,
        )

        metrics.dit = self._compute_dit(node)

        methods = [
            n for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        metrics.methods_count = len(methods)

        metrics.cbo = self._compute_cbo(node)
        metrics.lcom = self._compute_lcom(node)

        self.classes.append(metrics)
        self.generic_visit(node)

    # ---------------- DIT ----------------
    def _compute_dit(self, node: ast.ClassDef) -> int:

        def depth(cls: ast.ClassDef, visited: set[str]) -> int:
            if not cls.bases:
                return 0

            max_depth = 0
            for base in cls.bases:
                base_name = None

                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr

                if not base_name or base_name in visited:
                    continue

                visited.add(base_name)

                parent = self.class_defs.get(base_name)
                if parent:
                    max_depth = max(max_depth, 1 + depth(parent, visited))
                else:
                    max_depth = max(max_depth, 1)

            return max_depth

        return depth(node, set())

    # ---------------- CBO ----------------
    def _compute_cbo(self, node: ast.ClassDef) -> int:
        referenced = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                name = child.id
                if name not in self.BUILTINS and name not in {"self", "cls"}:
                    referenced.add(name)

            elif isinstance(child, ast.Attribute):
                if isinstance(child.value, ast.Name):
                    if child.value.id == "self":
                        continue
                referenced.add(child.attr)

        return len(referenced)

    # ---------------- LCOM ----------------
    def _compute_lcom(self, node: ast.ClassDef) -> float:
        methods = [
            n for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        if len(methods) <= 1:
            return 0.0

        method_attrs: list[set[str]] = []

        for method in methods:
            attrs = set()
            for child in ast.walk(method):
                if (
                    isinstance(child, ast.Attribute)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "self"
                ):
                    attrs.add(child.attr)
            method_attrs.append(attrs)

        all_attrs = set().union(*method_attrs)

        if not all_attrs:
            return 0.0

        m = len(methods)

        total = sum(
            sum(1 for ma in method_attrs if attr in ma)
            for attr in all_attrs
        )

        mean_access = total / len(all_attrs)

        if m == 1:
            return 0.0

        lcom = (mean_access - m) / (1 - m)
        return max(0.0, min(1.0, lcom))


# ---------------- WMC (radon) ----------------
def get_wmc_from_radon(filepath: str) -> dict[str, int]:
    try:
        result = subprocess.run(
            ["radon", "cc", filepath, "-j"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
    except Exception:
        return {}

    wmc = {}
    for items in data.values():
        for item in items:
            if item.get("type") == "class":
                total = sum(m["complexity"] for m in item.get("methods", []))
                wmc[item["name"]] = total
    return wmc


EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".git", ".tox", "node_modules"}


def analyze_project(project_path: Path) -> list[ClassMetrics]:
    all_classes = []

    for py_file in sorted(project_path.rglob("*.py")):
        if any(part in EXCLUDED_DIRS for part in py_file.parts):
            continue

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        analyzer = OOAnalyzer(str(py_file))
        analyzer.visit(tree)

        wmc_data = get_wmc_from_radon(str(py_file))
        for cls in analyzer.classes:
            cls.wmc = wmc_data.get(cls.name, cls.methods_count)

        all_classes.extend(analyzer.classes)

    return all_classes


def detect_god_classes(
    classes: list[ClassMetrics],
    wmc_threshold: int = 50,
    cbo_threshold: int = 15,
) -> list[ClassMetrics]:

    gods = []
    for cls in classes:
        if cls.wmc > wmc_threshold and cls.cbo > cbo_threshold:
            cls.is_god_class = True
            gods.append(cls)
    return gods


def print_report(classes: list[ClassMetrics]) -> None:
    print("\n" + "=" * 80)
    print("RAPORT METRYK OBIEKTOWYCH (CK)")
    print("=" * 80)

    n = len(classes)
    word = "klas"
    if n == 1:
        word = "klasę"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = "klasy"

    print(f"\nZnaleziono {n} {word}\n")

    by_wmc = sorted(classes, key=lambda c: c.wmc, reverse=True)

    print(f"{'Klasa':<35} {'WMC':>5} {'DIT':>5} {'CBO':>5} {'Metod':>6} {'LCOM':>6} {'God?':>5}")
    print("-" * 75)

    for cls in by_wmc[:30]:
        mark = " !!!" if cls.is_god_class else ""
        name = cls.name if len(cls.name) < 33 else cls.name[:30] + "..."
        print(f"{name:<35} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} {cls.methods_count:>6} {cls.lcom:.2f} {mark}")

    if classes:
        wmcs = [c.wmc for c in classes]
        dits = [c.dit for c in classes]
        cbos = [c.cbo for c in classes]
        lcoms  = [c.lcom for c in classes]

        print("\n--- Statystyki ---")
        print(f"WMC: śr {sum(wmcs)/len(wmcs):.1f}, max {max(wmcs)}")
        print(f"DIT: śr {sum(dits)/len(dits):.1f}, max {max(dits)}")
        print(f"CBO: śr {sum(cbos)/len(cbos):.1f}, max {max(cbos)}")
        print(f"LCOM: śr {sum(lcoms)/len(lcoms):.1f}, max {max(lcoms)}")

    gods = [c for c in classes if c.is_god_class]
    if gods:
        print(f"\n--- God classes ({len(gods)}) ---")
        for g in gods:
            print(
                f"{g.name} ({g.file}:{g.lineno}) "
                f"WMC={g.wmc}, CBO={g.cbo}, LCOM={g.lcom:.2f}"
            )
    else:
        print(f"\nBrak god classes (WMC>{50} AND CBO>{15})")


def main():
    if len(sys.argv) < 2:
        print("Użycie: python oo_metrics.py <projekt>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.is_dir():
        print("Nie znaleziono katalogu")
        sys.exit(1)

    print(f"Analizuję: {path}")

    classes = analyze_project(path)
    if not classes:
        print("Brak klas")
        sys.exit(1)

    detect_god_classes(classes)
    print_report(classes)


if __name__ == "__main__":
    main()