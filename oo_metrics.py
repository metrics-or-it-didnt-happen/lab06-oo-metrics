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

    def visit_ClassDef(self, node: ast.ClassDef):
        metrics = ClassMetrics(
            name=node.name,
            file=self.filepath,
            lineno=node.lineno,
        )

        # DIT: Analiza głębokości dziedziczenia
        metrics.dit = self._compute_dit(node)

        # Liczba metod
        methods = [n for n in node.body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        metrics.methods_count = len(methods)

        # CBO: Ile unikatowych nazw jest referencowanych w ciele klasy
        metrics.cbo = self._compute_cbo(node, methods)

        self.classes.append(metrics)
        self.generic_visit(node)

    def _compute_dit(self, node: ast.ClassDef) -> int:
        """
        Oblicza DIT na podstawie jawnych baz. 
        W statycznej analizie bez dostępu do całego drzewa projektu przyjmujemy:
        1 - brak jawnych baz (dziedziczy po 'object')
        2 - dziedziczy po jakiejkolwiek innej klasie
        """
        if not node.bases:
            return 1
        
        # Sprawdzamy, czy w bazach nie ma tylko 'object'
        bases = [b for b in node.bases if not (isinstance(b, ast.Name) and b.id == 'object')]
        return 2 if bases else 1

    def _compute_cbo(self, node: ast.ClassDef, methods: list) -> int:
        """
        Oblicza Coupling Between Objects.
        Zbiera unikalne nazwy klas/modułów użyte wewnątrz definicji klasy.
        """
        referenced_names = set()
        
        # Nazwy do zignorowania (built-ins, self, nazwy metod własnych)
        local_method_names = {m.name for m in methods}
        ignored = {
            'self', 'cls', 'None', 'True', 'False', 'object', 'int', 'str', 
            'float', 'dict', 'list', 'set', 'tuple', 'Any', 'Optional', 
            'Union', 'Annotated', 'Callable', 'Sequence', 'Iterable'
        }
        ignored.update(local_method_names)

        for subnode in ast.walk(node):
            # 1. Proste nazwy (np. Depends, Request)
            if isinstance(subnode, ast.Name) and isinstance(subnode.ctx, ast.Load):
                if subnode.id not in ignored:
                    referenced_names.add(subnode.id)
            
            # 2. Atrybuty (np. routing.Route -> bierzemy 'routing')
            elif isinstance(subnode, ast.Attribute) and isinstance(subnode.ctx, ast.Load):
                if isinstance(subnode.value, ast.Name):
                    if subnode.value.id not in ignored:
                        referenced_names.add(subnode.value.id)

        return len(referenced_names)

def get_wmc_from_radon(filepath: str) -> dict[str, int]:
    """Uruchamia radon i zwraca sumę CC (WMC) dla każdej klasy."""
    try:
        result = subprocess.run(
            ["radon", "cc", filepath, "-j"],
            capture_output=True, text=True, check=True,
        )
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return {}

    wmc = {}
    # Radon zwraca słownik, gdzie kluczem jest ścieżka do pliku
    for file_content in data.values():
        for item in file_content:
            if item["type"] == "class":
                # Sumujemy złożoność wszystkich metod w klasie
                total_cc = sum(m["complexity"] for m in item.get("methods", []))
                wmc[item["name"]] = total_cc
    return wmc

EXCLUDED_DIRS = {".venv", "venv", "__pycache__", ".git", ".tox", "node_modules"}

def analyze_project(project_path: Path) -> list[ClassMetrics]:
    """Analizuje pliki .py w projekcie."""
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
            # Jeśli radon nie zwrócił danych, fallback do liczby metod
            cls.wmc = wmc_data.get(cls.name, cls.methods_count)

        all_classes.extend(analyzer.classes)

    return all_classes

def detect_god_classes(classes: list[ClassMetrics],
                        wmc_threshold: int = 50,
                        cbo_threshold: int = 15) -> list[ClassMetrics]:
    """Oznacza klasy przekraczające progi złożoności."""
    gods = []
    for cls in classes:
        if cls.wmc > wmc_threshold and cls.cbo > cbo_threshold:
            cls.is_god_class = True
            gods.append(cls)
    return gods

def print_report(classes: list[ClassMetrics]) -> None:
    """Drukuje końcowy raport w konsoli."""
    print(f"\n{'=' * 80}")
    print(f"RAPORT METRYK OBIEKTOWYCH (CK)")
    print(f"{'=' * 80}")
    
    n = len(classes)
    if n == 1: word = "klasę"
    elif n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14): word = "klasy"
    else: word = "klas"
    
    print(f"\nZnaleziono {n} {word}\n")

    by_wmc = sorted(classes, key=lambda c: c.wmc, reverse=True)

    header = f"{'Klasa':<35} {'WMC':>5} {'DIT':>5} {'CBO':>5} {'Metod':>6} {'God?':>5}"
    print(header)
    print("-" * len(header))

    for cls in by_wmc[:30]:
        god_mark = " !!!" if cls.is_god_class else ""
        short_name = cls.name if len(cls.name) < 33 else cls.name[:30] + "..."
        print(f"  {short_name:<33} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} "
              f"{cls.methods_count:>6}{god_mark}")

    if classes:
        wmcs = [c.wmc for c in classes]
        dits = [c.dit for c in classes]
        cbos = [c.cbo for c in classes]
        print(f"\n--- Statystyki ---")
        print(f"  WMC: śr. {sum(wmcs)/len(wmcs):.1f}, max {max(wmcs)} ({by_wmc[0].name})")
        print(f"  DIT: śr. {sum(dits)/len(dits):.1f}, max {max(dits)}")
        print(f"  CBO: śr. {sum(cbos)/len(cbos):.1f}, max {max(cbos)}")

    gods = [c for c in classes if c.is_god_class]
    if gods:
        print(f"\n--- Potencjalne god classes ({len(gods)}) ---")
        for g in gods:
            print(f"  {g.name} ({g.file}:{g.lineno}) -> WMC={g.wmc}, CBO={g.cbo}")
    else:
        print(f"\n  Brak potencjalnych god classes (WMC>50 AND CBO>15)")

def main():
    if len(sys.argv) < 2:
        print("Użycie: python oo_metrics.py <ścieżka_do_projektu>")
        sys.exit(1)

    project_path = Path(sys.argv[1])
    if not project_path.is_dir():
        print(f"Nie znaleziono katalogu: {project_path}")
        sys.exit(1)

    classes = analyze_project(project_path)
    if not classes:
        print("Nie znaleziono klas do analizy.")
        sys.exit(1)

    detect_god_classes(classes)
    print_report(classes)

if __name__ == "__main__":
    main()
