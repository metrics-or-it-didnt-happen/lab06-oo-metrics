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


class OOAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts class metrics."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.classes: list[ClassMetrics] = []
        self._current_class: ClassMetrics | None = None
        self.class_defs: dict[str, ast.ClassDef] = {}

    def visit_ClassDef(self, node: ast.ClassDef):
        self.class_defs[node.name] = node
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
        # wyciąganie nazwy bazowych klas z różnych typów wyrażeń
        def get_base_name(expr: ast.expr) -> str | None:
            if isinstance(expr, ast.Name):
                return expr.id
            if isinstance(expr, ast.Attribute):
                return expr.attr
            if isinstance(expr, ast.Subscript):
                return get_base_name(expr.value)
            if isinstance(expr, ast.Call):
                return get_base_name(expr.func)
            return None

        #  funkcja do rekurencyjnego liczenia DIT, z zabezpieczeniem przed cyklami przez seen set
        def class_dit(class_node: ast.ClassDef, seen: set[str]) -> int:
            # ochrona przed zapętleniem
            if class_node.name in seen:
                return 0
            seen.add(class_node.name)

            # zliczamy DIT dla bazowych klas, wchodząc rekurencyjnie i bierzemy maksimum
            base_dits: list[int] = []
            for base in class_node.bases:
                base_name = get_base_name(base)
                if base_name is None or base_name == "object":
                    continue
                if base_name in self.class_defs:
                    base_dits.append(class_dit(self.class_defs[base_name], seen))
                else:
                    base_dits.append(0)

            if not base_dits:
                return 0
            return max(base_dits) + 1

        return class_dit(node, set())

    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Compute Coupling Between Objects.

        Count unique names referenced in the class body that look like
        external classes or modules (Name nodes and Attribute nodes).
        """
        # może niekompletna, może nadmierna, ale jakaś baza wbudowanych nazw, które ignorujemy przy liczeniu CBO
        builtins = {
            "self", "cls", "str", "int", "float", "bool", "list",
            "dict", "set", "tuple", "None", "True", "False",
            "bytes", "complex", "range", "object", "type",
        }

        # wyciąganie nazwy z różnych typów wyrażeń, żeby móc zidentyfikować potencjalne odniesienia do klas/modułów
        def get_root_name(expr: ast.expr) -> str | None:
            if isinstance(expr, ast.Name):
                return expr.id
            if isinstance(expr, ast.Attribute):
                return get_root_name(expr.value) or expr.attr
            if isinstance(expr, ast.Subscript):
                return get_root_name(expr.value)
            if isinstance(expr, ast.Call):
                return get_root_name(expr.func)
            return None

        # zbieranie kandydatów do jednego zestawu po nazwach, żeby potem łatwo policzyć unikalne
        def collect_targets(target: ast.AST, names: set[str]) -> None:
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for element in target.elts:
                    collect_targets(element, names)
            elif isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Name):
                    names.add(target.value.id)
            elif isinstance(target, ast.Starred):
                collect_targets(target.value, names)

        # ogólna pętla po całym drzewie AST klasy, żeby zebrać wszystkie lokalne nazwy...
        local_names: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_names.add(child.name)
                for arg in (child.args.posonlyargs + child.args.args +
                            child.args.kwonlyargs):
                    local_names.add(arg.arg)
                if child.args.vararg:
                    local_names.add(child.args.vararg.arg)
                if child.args.kwarg:
                    local_names.add(child.args.kwarg.arg)
            elif isinstance(child, ast.arg):
                local_names.add(child.arg)
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    collect_targets(target, local_names)
            elif isinstance(child, ast.AnnAssign):
                collect_targets(child.target, local_names)
            elif isinstance(child, ast.AugAssign):
                collect_targets(child.target, local_names)
            elif isinstance(child, ast.For):
                collect_targets(child.target, local_names)
            elif isinstance(child, ast.With):
                for item in child.items:
                    if item.optional_vars is not None:
                        collect_targets(item.optional_vars, local_names)
            elif isinstance(child, ast.comprehension):
                collect_targets(child.target, local_names)

        # ...potem odfiltrować je od potencjalnych odniesień do zewnętrznych klas/modułów
        candidates: set[str] = set()
        for expr in ast.walk(node):
            if isinstance(expr, ast.Name) and isinstance(expr.ctx, ast.Load):
                name = expr.id
                if name in builtins or name in local_names:
                    continue
                candidates.add(name)
            elif isinstance(expr, ast.Attribute):
                root = get_root_name(expr)
                if root and root not in builtins and root not in local_names:
                    candidates.add(root)

        return len(candidates)


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