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
        self.class_map: dict[str, ast.ClassDef] = {} #dit for every class

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

        # CBO: ile unikatowych nazw (klas/modułów) jest referencjowanych
        metrics.cbo = self._compute_cbo(node)

        metrics.lcom = self._compute_lcom(node)

        self.classes.append(metrics)

        # Odwiedzaj zagnieżdżone elementy
        self.generic_visit(node)

    def _get_base_name(self, base: ast.expr) -> str | None:
        """Extract base class name from an AST node."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            # Obsługa np. module.BaseClass
            return base.attr
        return None
    
    def _compute_dit(self, node: ast.ClassDef, visited=None) -> int:
        """Compute Depth of Inheritance Tree.

        Simple heuristic: count explicit base classes.
        For full MRO analysis we'd need to resolve imports,
        which is beyond the scope of static analysis.
        """
        # Prosta wersja: DIT = liczba jawnych baz (bez object)
        # Lepsza wersja: sprawdź czy bazy też mają bazy (rekurencja po AST)

        if visited is None:
            visited = set()
        
        class_name = node.name
        if class_name in visited:
            return 0  # Zapobiegaj cyklom
        
        visited.add(class_name)
        if not node.bases:
            return 0  # Brak baz, DIT = 0
        
        max_depth = 0
        for base in node.bases:
            base_name = self._get_base_name(base)
            if base_name and base_name != "object":
                if base_name in self.class_map:
                    base_node = self.class_map[base_name]
                    depth = 1 + self._compute_dit(base_node, visited.copy())
                    max_depth = max(max_depth, depth)
                else:
                    max_depth = max(max_depth, 1)  # Nieznana baza, zakładamy DIT=1

        return max_depth

    def _extract_names(self, target):
        names = set()
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                names |= self._extract_names(elt)
        return names
    
    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Compute Coupling Between Objects.

        Count unique names referenced in the class body that look like
        external classes or modules (Name nodes and Attribute nodes).
        """

        import builtins
        builtins_set = set(dir(builtins))

        local_names = set()
        used = set()

        #zbierz lokalne zmienne i argumenty
        for n in ast.walk(node):
            if isinstance(n, ast.FunctionDef):
                for arg in n.args.args:
                    local_names.add(arg.arg)

                if n.args.vararg:
                    local_names.add(n.args.vararg.arg)
                if n.args.kwarg:
                    local_names.add(n.args.kwarg.arg)

            elif isinstance(n, ast.Assign):
                for target in n.targets:
                    local_names |= self._extract_names(target)

            elif isinstance(n, ast.For):
                local_names |= self._extract_names(n.target)
            
            elif isinstance(n, ast.With):
                for item in n.items:
                    if item.optional_vars:
                        local_names |= self._extract_names(item.optional_vars)

            elif isinstance(n, ast.ExceptHandler):
                if n.name:
                    local_names.add(n.name)

            elif isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                for gen in n.generators:
                    local_names |= self._extract_names(gen.target)

        #zbierz użycia
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                name = n.id

                if (
                    not name.isupper() and
                    name not in local_names and
                    name not in builtins_set and
                    name not in {"self", "cls", "kwargs", "args", "super"} and
                    name is not node.name
                ):
                    used.add(name)

            elif isinstance(n, ast.Attribute):
                if isinstance(n.value, ast.Name):
                    name = n.value.id

                    if (
                        name not in local_names and
                        name not in builtins_set and
                        name not in {"self", "cls"}
                    ):
                        used.add(name)
        return len(used)
    
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
    # znajdujemy klasy i inicjujemy WMC na 0
    for items in data.values():
        for item in items:
            if item["type"] == "class":
                wmc[item["name"]] = 0

    # sumujemy CC metod do WMC odpowiedniej klasy
    for items in data.values():
        for item in items:
            if item["type"]=="method":
                cls = item.get("classname")
                if cls in wmc:
                    wmc[cls] += item.get("complexity", 0)
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
          f"{'Metod':>6} {'LCOM':>6} {'God?':>5} ")
    print("-" * 75)

    for cls in by_wmc[:30]:
        god_mark = " !!!" if cls.is_god_class else ""
        short_name = cls.name if len(cls.name) < 33 else cls.name[:30] + "..."
        print(f"  {short_name:<33} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} "
              f"{cls.methods_count:>6} {cls.lcom:>6.2f}{god_mark}")

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
        print("Użycie: python oo_metrics.py <ścieżka_do_projektu> [wmc_threshold] [cbo_threshold]")
        sys.exit(1)

    project_path = Path(sys.argv[1])
    if not project_path.is_dir():
        print(f"Nie znaleziono katalogu: {project_path}")
        sys.exit(1)

    wmc_threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    cbo_threshold = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    print(f"Progi: WMC>{wmc_threshold}, CBO>{cbo_threshold}")

    print(f"Analizuję metryki OO: {project_path}")
    classes = analyze_project(project_path)
    if not classes:
        print("Nie znaleziono klas do analizy.")
        sys.exit(1)

    detect_god_classes(classes, wmc_threshold, cbo_threshold)
    print_report(classes)


if __name__ == "__main__":
    main()