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
    is_god_class: bool = False
    lcom: float = 0.0


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

        # LCOM: brak spójności metod (Henderson-Sellers)
        metrics.lcom = self._compute_lcom(node)

        self.classes.append(metrics)

        # Odwiedzaj zagnieżdżone elementy
        self.generic_visit(node)

    def _build_class_nodes(self) -> dict:
        """Parse the current file once and return a name->ClassDef mapping."""
        try:
            src = Path(self.filepath).read_text(encoding="utf-8", errors="replace")
            module_tree = ast.parse(src)
            return {
                n.name: n
                for n in ast.walk(module_tree)
                if isinstance(n, ast.ClassDef)
            }
        except (OSError, SyntaxError):
            return {}

    def _compute_dit(self, node: ast.ClassDef,
                     class_nodes=None,
                     visited=None) -> int:
        """Compute Depth of Inheritance Tree.

        Simple heuristic: count explicit base classes.
        For full MRO analysis we'd need to resolve imports,
        which is beyond the scope of static analysis.
        """
        if class_nodes is None:
            class_nodes = self._build_class_nodes()

        if visited is None:
            visited = set()
        if node.name in visited:
            return 0
        visited.add(node.name)

        depth = 0
        for base in node.bases:
            if isinstance(base, ast.Name):
                if base.id == "object":
                    continue
                depth += 1
                if base.id in class_nodes and class_nodes[base.id] is not node:
                    depth += self._compute_dit(
                        class_nodes[base.id], class_nodes, visited
                    )
            elif isinstance(base, ast.Attribute):
                depth += 1

        return depth

    def _compute_lcom(self, node: ast.ClassDef) -> float:
        """Compute LCOM (Henderson-Sellers version).

        For each attribute, count how many methods access it.
        LCOM = (mean(accesses) - M) / (1 - M)
        where M = number of methods.
        Returns value in [0, 1]: 0 = fully cohesive, 1 = no cohesion.
        """
        methods = [n for n in node.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if len(methods) <= 1:
            return 0.0

        method_attrs: list[set[str]] = []
        for method in methods:
            attrs = set()
            for child in ast.walk(method):
                if (isinstance(child, ast.Attribute)
                        and isinstance(child.value, ast.Name)
                        and child.value.id == "self"):
                    attrs.add(child.attr)
            method_attrs.append(attrs)

        all_attrs: set[str] = set()
        for attrs in method_attrs:
            all_attrs.update(attrs)

        if not all_attrs:
            return 0.0

        m = len(methods)
        total = sum(
            sum(1 for ma in method_attrs if attr in ma)
            for attr in all_attrs
        )
        mean_access = total / len(all_attrs)

        lcom = (mean_access - m) / (1 - m)
        return max(0.0, min(1.0, lcom))

    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Compute Coupling Between Objects.

        Count unique names referenced in the class body that look like
        external classes or modules (Name nodes and Attribute nodes).
        """
        BUILTINS = frozenset({
            "self", "cls", "super",
            "str", "int", "float", "bool", "bytes", "list", "dict", "set",
            "tuple", "type", "object", "None", "True", "False",
            "len", "range", "enumerate", "zip", "map", "filter", "sorted",
            "print", "open", "isinstance", "issubclass", "hasattr", "getattr",
            "setattr", "delattr", "repr", "abs", "round", "min", "max",
            "sum", "any", "all", "iter", "next", "vars", "dir", "id",
            "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
            "AttributeError", "NotImplementedError", "StopIteration",
            "RuntimeError", "OSError", "IOError", "FileNotFoundError",
        })

        referenced: set[str] = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                name = child.id
                if name not in BUILTINS and not name.startswith("_"):
                    referenced.add(name)

            elif isinstance(child, ast.Attribute):
                if isinstance(child.value, ast.Name):
                    root = child.value.id
                    if root not in BUILTINS and not root.startswith("_"):
                        referenced.add(root)

        referenced.discard(node.name)

        return len(referenced)


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
                total_cc = item["complexity"]
                wmc[item["name"]] = total_cc
    return wmc


def analyze_project(project_path: Path) -> list[ClassMetrics]:
    """Analyze all Python files in a project."""
    all_classes = []

    for py_file in sorted(project_path.rglob("*.py")):
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
    print(f"\nZnaleziono {len(classes)} klas\n")

    # Sortuj po WMC malejąco
    by_wmc = sorted(classes, key=lambda c: c.wmc, reverse=True)

    print(f"{'Klasa':<35} {'WMC':>5} {'DIT':>5} {'CBO':>5} "
          f"{'Metod':>6} {'LCOM':>6} {'God?':>5}")
    print("-" * 83)

    for cls in by_wmc[:30]:
        god_mark = " !!!" if cls.is_god_class else ""
        short_name = cls.name if len(cls.name) < 33 else cls.name[:30] + "..."
        print(f"  {short_name:<33} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} "
              f"{cls.methods_count:>6} {cls.lcom:>5.2f}{god_mark}")

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
        lcoms = [c.lcom for c in classes]
        print(f"  LCOM: śr. {sum(lcoms)/len(lcoms):.2f}, "
              f"max {max(lcoms):.2f} ({max(classes, key=lambda c: c.lcom).name})")

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