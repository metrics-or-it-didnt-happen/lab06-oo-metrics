#!/usr/bin/env python3
"""OO Metrics Analyzer - Chidamber-Kemerer metrics for Python classes."""

import ast
import builtins
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
    is_god_class: bool = False


class OOAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts class metrics."""

    def __init__(self, filepath: str, tree: ast.AST):
        self.filepath = filepath
        self.classes: list[ClassMetrics] = []
        self._class_defs: dict[str, ast.ClassDef] = {
            n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
        }

        excluded_names = {
            "self", "cls", "True", "False", "None", "NotImplemented", "Ellipsis",
            "str", "int", "float", "bool", "bytes", "list", "dict", "set", "tuple",
            "object", "type", "len", "range", "enumerate", "zip", "map", "filter",
            "sum", "min", "max", "any", "all", "open", "isinstance", "issubclass",
            "super", "staticmethod", "classmethod", "property",
        }
        self._ignored_names = excluded_names | set(dir(builtins))

    @staticmethod
    def _collect_assigned_names(subtree: ast.AST) -> set[str]:
        assigned: set[str] = set()
        for child in ast.walk(subtree):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                assigned.add(child.id)
            elif isinstance(child, ast.arg):
                assigned.add(child.arg)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                assigned.add(child.name)
        return assigned

    @staticmethod
    def _base_name(base: ast.expr):
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            return base.attr
        if isinstance(base, ast.Subscript):
            # e.g. Generic[T] -> Generic
            return OOAnalyzer._base_name(base.value)
        return None

    def visit_ClassDef(self, node: ast.ClassDef):
        metrics = ClassMetrics(
            name=node.name,
            file=self.filepath,
            lineno=node.lineno,
        )

        metrics.dit = self._compute_dit(node)

        metrics.methods_count = sum(
            1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        )

        metrics.cbo = self._compute_cbo(node)

        self.classes.append(metrics)
        self.generic_visit(node)

    def _compute_dit(self, node: ast.ClassDef) -> int:
        """Compute Depth of Inheritance Tree.

        Simple heuristic: count explicit base classes.
        For full MRO analysis we'd need to resolve imports,
        which is beyond the scope of static analysis.
        """
        visited: set[str] = set()

        def depth_for(class_node: ast.ClassDef) -> int:
            if not class_node.bases:
                return 0

            max_depth = 0
            for base in class_node.bases:
                name = self._base_name(base)
                if not name or name == "object":
                    continue

                # Unknown external base: count one inheritance level.
                if name not in self._class_defs:
                    max_depth = max(max_depth, 1)
                    continue

                # Prevent loops in malformed class hierarchies.
                if name in visited:
                    max_depth = max(max_depth, 1)
                    continue

                visited.add(name)
                base_depth = 1 + depth_for(self._class_defs[name])
                visited.remove(name)
                max_depth = max(max_depth, base_depth)

            return max_depth

        return depth_for(node)

    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Compute Coupling Between Objects.

        Count unique names referenced in the class body that look like
        external classes or modules (Name nodes and Attribute nodes).
        """
        class_defined: set[str] = {
            n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        for item in node.body:
            if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                class_defined.update(self._collect_assigned_names(item))

        couplings: set[str] = set()
        for item in node.body:
            local_defined = self._collect_assigned_names(item)
            blocked = class_defined | local_defined | self._ignored_names

            for child in ast.walk(item):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    if child.id not in blocked:
                        couplings.add(child.id)
                elif isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
                    base = child.value.id
                    if base not in blocked:
                        couplings.add(base)

        return len(couplings)


def get_wmc_from_radon(filepath: str) -> dict[str, int]:
    """Run radon on a file and return WMC per class."""
    data = None
    for cmd in (
        ["radon", "cc", filepath, "-j"],
        [sys.executable, "-m", "radon", "cc", filepath, "-j"],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            break
        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            pass

    if not isinstance(data, dict):
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

        analyzer = OOAnalyzer(str(py_file), tree)
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
    gods = [c for c in classes if c.wmc > wmc_threshold and c.cbo > cbo_threshold]
    for cls in gods:
        cls.is_god_class = True
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
