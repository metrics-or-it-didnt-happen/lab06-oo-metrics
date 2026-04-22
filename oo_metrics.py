#!/usr/bin/env python3
"""OO Metrics Analyzer - Chidamber-Kemerer metrics for Python classes."""

import ast
import json
import subprocess
import sys
import builtins
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
    is_god_class: bool = False


class OOAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts class metrics."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.classes: list[ClassMetrics] = []
        self._current_class: ClassMetrics | None = None
        # mapa: nazwa klasy -> wierzcholek ClassDef AST
        # zeby mozna bylo rekurencyjnie wywolywac dit
        self.class_map: dict[str, ast.ClassDef] = {}


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

        self.classes.append(metrics)

        # Odwiedzaj zagnieżdżone elementy
        self.generic_visit(node)

    def _compute_dit(self, node: ast.ClassDef) -> int:
        """Compute Depth of Inheritance Tree.

        Simple heuristic: count explicit base classes.
        For full MRO analysis we'd need to resolve imports,
        which is beyond the scope of static analysis.
        """
        # TODO: Twój kod tutaj
        # Prosta wersja: DIT = liczba jawnych baz (bez object)
        # Lepsza wersja: sprawdź czy bazy też mają bazy (rekurencja po AST)
        # Panika? FAQ ma sekcję o DIT i importach.

        if not node.bases:
            return 0

        depths = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            else:
                continue

            if base_name == "object":
                continue

            if base_name in self.class_map:
                depths.append(1 + self._compute_dit(self.class_map[base_name]))
            else:
                depths.append(1)

        return max(depths, default = 0)

    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Compute Coupling Between Objects.

        Count unique names referenced in the class body that look like
        external classes or modules (Name nodes and Attribute nodes).
        """
        # TODO: Twój kod tutaj
        # Wskazówki:
        # - Przejdź po ast.walk(node)
        # - Szukaj ast.Name (referencje do nazw) i ast.Attribute
        # - Odfiltruj self, cls, wbudowane typy (str, int, list, dict...)
        # - Policz unikatowe nazwy
        # CBO wychodzi 3000? Spokojnie, FAQ wyjaśnia co filtrować.

        import builtins
        EXCLUDE = set(dir(builtins)) | {"self", "cls", "str",
                                        "int", "list", "dict",
                                        "set", "tuple", "bool",
                                        "args", "kwargs", "super"
                                        "True", "False", "None"}

        local_names: set[str] = set()

        for v in ast.walk(node):
            if isinstance(v, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_names.add(v.name) # dodanie nazwy metody
                for arg in v.args.args + v.args.posonlyargs + v.args.kwonlyargs:
                    local_names.add(arg.arg)
                if v.args.vararg:
                    local_names.add(v.args.vararg.arg)
                if v.args.kwarg:
                    local_names.add(v.args.kwarg.arg)
                elif isinstance(v, ast.Name) and isinstance(v.ctx, (ast.State, ast.Del)):
                    local_names.add(v.id)
                elif isinstance(v, (ast.Import, ast.ImportFrom)):
                    for alias in v.names:
                        local_names.add(alias.asname or alias.name.split(".")[0])

        seen: set[str] = set()
        for v in ast.walk(node):
            if isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load):
                seen.add(v.id)
            elif isinstance(v, ast.Attribute) and isinstance(v.ctx, ast.Load):
                if isinstance(v.value, ast.Name):
                    seen.add(v.value.id)

        return len(seen - EXCLUDE - local_names)


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
    print(f"\n{'=' * 80}")
    print(f"RAPORT METRYK OBIEKTOWYCH (CK)")
    print(f"{'=' * 80}")
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

    print(f"{'Klasa':<35} {'WMC':>5} {'DIT':>5} {'CBO':>5} "
          f"{'Metod':>6} {'God?':>5}")
    print("-" * 75)

    for cls in by_wmc[:30]:
        god_mark = " !!!" if cls.is_god_class else ""
        short_name = cls.name if len(cls.name) < 33 else cls.name[:30] + "..."
        print(f"  {short_name:<33} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} "
              f"{cls.methods_count:>6}{god_mark}")

    # Statystyki
    print(f"\n--- Statystyki ---")
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
