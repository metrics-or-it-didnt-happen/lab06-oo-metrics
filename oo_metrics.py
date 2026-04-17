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
    """Metrics for a single class."""
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
    """AST visitor that extracts class metrics."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.classes: list[ClassMetrics] = []
        self._current_class: ClassMetrics | None = None

    def visit_ClassDef(self, node: ast.ClassDef):
        metrics = ClassMetrics(
            name=node.name,
            file=self.filepath,
            lineno=node.lineno,
        )

        # DIT: analiza baz klas
        metrics.dit = self._compute_dit(node)

        # Liczba metod
        methods = [n for n in node.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        metrics.methods_count = len(methods)

        # CBO: ile unikatowych nazw (klas/modułów) jest referencowanych
        metrics.cbo = self._compute_cbo(node)

        # LCOM: Spójność metod
        metrics.lcom = self._compute_lcom(node)

        self.classes.append(metrics)
        self.generic_visit(node)

    def _compute_dit(self, node: ast.ClassDef) -> int:
        """Compute Depth of Inheritance Tree.
        Simple heuristic: count explicit base classes.
        """
        explicit_bases = 0
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "object":
                continue
            explicit_bases += 1

        return 1 + explicit_bases if explicit_bases > 0 else 1

    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Compute Coupling Between Objects (Final Version)."""
        coupled_names = set()

        ignored_names = {
            "self", "cls", "int", "str", "float", "bool", "list", "dict", "set", "tuple", "bytes",
            "isinstance", "hasattr", "getattr", "setattr", "len", "print", "range", "enumerate",
            "super", "object", "type", "True", "False", "None"
        }

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    name = child.func.id
                    if name not in ignored_names and not name.startswith("__"):
                        coupled_names.add(name)
                elif isinstance(child.func, ast.Attribute):
                    if isinstance(child.func.value, ast.Name):
                        name = child.func.value.id
                        if name not in ignored_names and name != "self":
                            coupled_names.add(name)

            elif isinstance(child, ast.Raise):
                if isinstance(child.exc, ast.Name):
                    if child.exc.id not in ignored_names:
                        coupled_names.add(child.exc.id)
                elif isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                    if child.exc.func.id not in ignored_names:
                        coupled_names.add(child.exc.func.id)

            elif isinstance(child, ast.ExceptHandler):
                if isinstance(child.type, ast.Name):
                    if child.type.id not in ignored_names:
                        coupled_names.add(child.type.id)
                elif isinstance(child.type, ast.Tuple):
                    for el in child.type.elts:
                        if isinstance(el, ast.Name) and el.id not in ignored_names:
                            coupled_names.add(el.id)

        return len(coupled_names)

    def _compute_lcom(self, node: ast.ClassDef) -> float:
        """Compute LCOM (Henderson-Sellers version).
        For each attribute, count how many methods access it.
        LCOM = (mean(accesses) - M) / (1 - M)
        where M = number of methods.
        """
        methods = [n for n in node.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if len(methods) <= 1:
            return 0.0

        # Zbierz atrybuty używane w każdej metodzie
        method_attrs: list[set[str]] = []
        for method in methods:
            attrs = set()
            for child in ast.walk(method):
                if (isinstance(child, ast.Attribute)
                        and isinstance(child.value, ast.Name)
                        and child.value.id == "self"):
                    attrs.add(child.attr)
            method_attrs.append(attrs)

        # Wszystkie atrybuty klasy
        all_attrs = set()
        for attrs in method_attrs:
            all_attrs.update(attrs)

        if not all_attrs:
            return 0.0

        # Dla każdego atrybutu: ile metod go używa
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

def get_wmc_from_radon(filepath: str) -> dict[str, int]:
    """Run radon on a file and return WMC per class."""
    try:
        result = subprocess.run(
            ["radon", "cc", filepath, "-j"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}

    wmc = {}
    for items in data.values():
        for item in items:
            if item["type"] == "class":
                total_cc = sum(m["complexity"] for m in item.get("methods", []))
                wmc[item["name"]] = total_cc
    return wmc


EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".git", ".tox", "node_modules"}


def analyze_project(project_path: Path) -> list[ClassMetrics]:
    """Analyze all Python files in a project."""
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

        # Pobierz WMC z radona
        wmc_data = get_wmc_from_radon(str(py_file))
        for cls in analyzer.classes:
            cls.wmc = wmc_data.get(cls.name, cls.methods_count)

        all_classes.extend(analyzer.classes)

    return all_classes


def detect_god_classes(classes: list[ClassMetrics],
                       wmc_threshold: int = 50,
                       cbo_threshold: int = 15) -> list[ClassMetrics]:
    """Mark and return potential god classes."""
    gods = []
    for cls in classes:
        if cls.wmc > wmc_threshold and cls.cbo > cbo_threshold:
            cls.is_god_class = True
            gods.append(cls)
    return gods


def print_report(classes: list[ClassMetrics]) -> None:
    """Print OO metrics report."""
    print(f"\n{'=' * 81}")
    print(f"RAPORT METRYK OBIEKTOWYCH (CK)")
    print(f"{'=' * 81}")

    # Żeby prof. Miodek spał spokojnie
    n = len(classes)
    if n == 1:
        word = "klasę"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = "klasy"
    else:
        word = "klas"
    print(f"\nZnaleziono {n} {word}\n")

    # Sortuj po WMC malejąco
    by_wmc = sorted(classes, key=lambda c: c.wmc, reverse=True)

    # Zaktualizowane nagłówki z LCOM
    print(f"{'Klasa':<35} {'WMC':>5} {'DIT':>5} {'CBO':>5} {'LCOM':>5} "
          f"{'Metod':>6} {'God?':>5}")
    print("-" * 81)

    # Zaktualizowana pętla z LCOM
    for cls in by_wmc[:30]:
        god_mark = " !!!" if cls.is_god_class else ""
        short_name = cls.name if len(cls.name) < 33 else cls.name[:30] + "..."
        print(f"  {short_name:<33} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} {cls.lcom:>5.2f} "
              f"{cls.methods_count:>6}{god_mark}")

    # Statystyki (dodano LCOM dla spójności)
    print(f"\n--- Statystyki ---")
    if classes:
        wmcs = [c.wmc for c in classes]
        dits = [c.dit for c in classes]
        cbos = [c.cbo for c in classes]
        lcoms = [c.lcom for c in classes]

        print(f"  WMC: śr. {sum(wmcs) / len(wmcs):.1f}, "
              f"max {max(wmcs)} ({by_wmc[0].name})")
        print(f"  DIT: śr. {sum(dits) / len(dits):.1f}, max {max(dits)}")
        print(f"  CBO: śr. {sum(cbos) / len(cbos):.1f}, max {max(cbos)}")
        print(f"  LCOM: śr. {sum(lcoms) / len(lcoms):.2f}, max {max(lcoms):.2f}")

    # Sekcja God Classes (dodano wyświetlanie LCOM)
    gods = [c for c in classes if c.is_god_class]
    if gods:
        print(f"\n--- Potencjalne god classes ({len(gods)}) ---")
        for g in gods:
            print(f"  {g.name} ({g.file}:{g.lineno})")
            print(f"    WMC={g.wmc}, CBO={g.cbo}, LCOM={g.lcom:.2f}, metod={g.methods_count}")
    else:
        print(f"\n  Brak potencjalnych god classes (WMC>{50} AND CBO>{15})")


def main():
    if len(sys.argv) < 2:
        print("Użycie: python oo_metrics.py <ścieżka_do_projektu>")
        sys.exit(1)

    project_path = Path(sys.argv[1])
    if not project_path.is_dir():
        print(f"Nie znaleziono katalogu: {project_path}")
        sys.exit(1)

    print(f"Analizuję metryki OO: {project_path}")

    classes = analyze_project(project_path)
    if not classes:
        print("Nie znaleziono klas do analizy.")
        sys.exit(1)

    detect_god_classes(classes)
    print_report(classes)


if __name__ == "__main__":
    main()