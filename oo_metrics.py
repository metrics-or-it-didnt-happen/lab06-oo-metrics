#!/usr/bin/env python3
"""OO Metrics Analyzer - Chidamber-Kemerer metrics for Python classes."""

import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# typy wbudowane i funkcje ktore nie powinny wchodzic do CBO
_BUILTINS = frozenset({
    "str", "int", "float", "list", "dict", "set", "tuple", "bool",
    "bytes", "bytearray", "object", "type", "None", "True", "False",
    "Exception", "BaseException", "ValueError", "TypeError", "KeyError",
    "IndexError", "AttributeError", "RuntimeError", "NotImplementedError",
    "StopIteration", "OSError", "IOError", "FileNotFoundError",
    "ImportError", "ModuleNotFoundError", "NameError", "LookupError",
    "OverflowError", "ZeroDivisionError", "UnicodeError",
    "ConnectionError", "TimeoutError", "PermissionError",
    "super", "print", "len", "range", "enumerate", "zip", "map", "filter",
    "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
    "property", "staticmethod", "classmethod",
    "open", "iter", "next", "sorted", "reversed", "min", "max", "sum", "abs",
    "any", "all", "id", "hash", "repr", "chr", "ord", "hex", "bin", "oct",
    "callable", "vars", "dir", "format",
})


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

        metrics.dit = self._compute_dit(node)

        methods = [n for n in node.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        metrics.methods_count = len(methods)

        metrics.cbo = self._compute_cbo(node)

        self.classes.append(metrics)
        self.generic_visit(node)

    def _compute_dit(self, node: ast.ClassDef) -> int:
        """Depth of Inheritance Tree - liczymy jawne bazy, pomijamy object."""
        count = 0
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "object":
                continue
            # cos w stylu modul.Klasa tez sie liczy
            count += 1
        return count

    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Coupling Between Objects - unikatowe zewnetrzne nazwy uzywane w klasie."""
        # najpierw zbieramy nazwy lokalne zeby je potem odfiltrowac
        local_names = {node.name}
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for arg in child.args.args + child.args.kwonlyargs:
                    local_names.add(arg.arg)
                if child.args.vararg:
                    local_names.add(child.args.vararg.arg)
                if child.args.kwarg:
                    local_names.add(child.args.kwarg.arg)
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        local_names.add(target.id)
            elif isinstance(child, ast.For):
                if isinstance(child.target, ast.Name):
                    local_names.add(child.target.id)

        # teraz szukamy referencji do zewnetrznych nazw
        refs = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                name = child.id
                if (name not in {"self", "cls"}
                        and name not in _BUILTINS
                        and name not in local_names):
                    refs.add(name)
            elif isinstance(child, ast.Attribute):
                # referencja w stylu modul.cos - liczymy ten modul
                if (isinstance(child.value, ast.Name)
                        and child.value.id not in {"self", "cls"}
                        and child.value.id not in _BUILTINS
                        and child.value.id not in local_names):
                    refs.add(child.value.id)

        return len(refs)


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
    print(f"\n{'=' * 80}")
    print("RAPORT METRYK OBIEKTOWYCH (CK)")
    print(f"{'=' * 80}")

    n = len(classes)
    if n == 1:
        word = "klasę"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        word = "klasy"
    else:
        word = "klas"
    print(f"\nZnaleziono {n} {word}\n")

    by_wmc = sorted(classes, key=lambda c: c.wmc, reverse=True)

    print(f"{'Klasa':<35} {'WMC':>5} {'DIT':>5} {'CBO':>5} "
          f"{'Metod':>6} {'God?':>5}")
    print("-" * 75)

    for cls in by_wmc[:30]:
        god_mark = " !!!" if cls.is_god_class else ""
        short_name = cls.name if len(cls.name) < 33 else cls.name[:30] + "..."
        print(f"  {short_name:<33} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} "
              f"{cls.methods_count:>6}{god_mark}")

    print("\n--- Statystyki ---")
    if classes:
        wmcs = [c.wmc for c in classes]
        dits = [c.dit for c in classes]
        cbos = [c.cbo for c in classes]
        print(f"  WMC: śr. {sum(wmcs)/len(wmcs):.1f}, "
              f"max {max(wmcs)} ({by_wmc[0].name})")
        print(f"  DIT: śr. {sum(dits)/len(dits):.1f}, max {max(dits)}")
        print(f"  CBO: śr. {sum(cbos)/len(cbos):.1f}, max {max(cbos)}")

    gods = [c for c in classes if c.is_god_class]
    if gods:
        print(f"\n--- Potencjalne god classes ({len(gods)}) ---")
        for g in gods:
            print(f"  {g.name} ({g.file}:{g.lineno})")
            print(f"    WMC={g.wmc}, CBO={g.cbo}, metod={g.methods_count}")
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
