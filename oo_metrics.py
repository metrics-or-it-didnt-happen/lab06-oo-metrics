#!/usr/bin/env python3
"""OO Metrics Analyzer - Chidamber-Kemerer metrics for Python classes."""

import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, stdev

EXCLUDED_DIRS = {
    ".venv", "venv", "__pycache__", ".git", ".tox",
    "node_modules", ".eggs", "build", "dist", ".mypy_cache",
}

BUILTIN_NAMES = {
    "str", "int", "float", "bool", "bytes", "list", "dict", "set",
    "tuple", "frozenset", "type", "object", "None", "True", "False",
    "Exception", "BaseException", "ValueError", "TypeError", "KeyError",
    "AttributeError", "IndexError", "RuntimeError", "NotImplementedError",
    "StopIteration", "OSError", "IOError", "ImportError", "AssertionError",
    "super", "print", "len", "range", "enumerate", "zip", "map", "filter",
    "sorted", "reversed", "any", "all", "min", "max", "sum", "abs",
    "isinstance", "issubclass", "hasattr", "getattr", "setattr", "delattr",
    "callable", "id", "hash", "repr", "iter", "next", "property",
    "staticmethod", "classmethod", "staticmethod",
}


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


@dataclass
class ProjectClassMap:
    """Map of class names to their AST nodes across the project.

    Used for resolving DIT across files.
    """

    classes: dict[str, list[ast.ClassDef]] = field(default_factory=dict)

    def add(self, name: str, node: ast.ClassDef) -> None:
        self.classes.setdefault(name, []).append(node)

    def get_base_names(self, node: ast.ClassDef) -> list[str]:
        """Return explicit base class names, excluding 'object'."""
        names = []
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id != "object":
                names.append(base.id)
            elif isinstance(base, ast.Attribute):
                names.append(base.attr)
        return names

    def compute_dit(self, node: ast.ClassDef, visited: set[str] | None = None) -> int:
        """Compute DIT by resolving base classes within the project."""
        if visited is None:
            visited = set()

        base_names = self.get_base_names(node)
        if not base_names:
            return 0

        max_depth = 0
        for bname in base_names:
            if bname in visited:
                continue
            visited.add(bname)
            if bname in self.classes:
                parent_node = self.classes[bname][0]
                depth = 1 + self.compute_dit(parent_node, visited)
            else:
                depth = 1
            max_depth = max(max_depth, depth)

        return max_depth


class OOAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts class metrics."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.classes: list[ClassMetrics] = []
        self.class_nodes: list[tuple[str, ast.ClassDef]] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        metrics = ClassMetrics(
            name=node.name,
            file=self.filepath,
            lineno=node.lineno,
        )

        methods = [
            n
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        metrics.methods_count = len(methods)
        metrics.cbo = self._compute_cbo(node)
        metrics.lcom = self._compute_lcom(node)

        self.classes.append(metrics)
        self.class_nodes.append((node.name, node))

        self.generic_visit(node)

    def _compute_cbo(self, node: ast.ClassDef) -> int:
        """Compute Coupling Between Objects.

        Count unique external names referenced in the class body:
        - ast.Name nodes (direct name references)
        - Root names from ast.Attribute chains (e.g. 'os' in os.path.join)
        Filter out self, cls, builtins, local args, and the class's own name.
        """
        local_names = {node.name}

        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_names.add(child.name)
                for arg in child.args.args + child.args.posonlyargs + child.args.kwonlyargs:
                    local_names.add(arg.arg)
                if child.args.vararg:
                    local_names.add(child.args.vararg.arg)
                if child.args.kwarg:
                    local_names.add(child.args.kwarg.arg)

        external_refs: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                name = child.id
                if name not in local_names and name not in BUILTIN_NAMES:
                    external_refs.add(name)

        return len(external_refs)

    def _compute_lcom(self, node: ast.ClassDef) -> float:
        """Compute LCOM (Henderson-Sellers version).

        For each attribute, count how many methods access it.
        LCOM = (mean_access - M) / (1 - M)
        where M = number of methods.
        Result: 0 = cohesive, 1 = no cohesion.
        """
        methods = [
            n
            for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if len(methods) <= 1:
            return 0.0

        method_attrs: list[set[str]] = []
        for method in methods:
            attrs: set[str] = set()
            for child in ast.walk(method):
                if (
                    isinstance(child, ast.Attribute)
                    and isinstance(child.value, ast.Name)
                    and child.value.id == "self"
                ):
                    attrs.add(child.attr)
            method_attrs.append(attrs)

        all_attrs: set[str] = set()
        for attrs in method_attrs:
            all_attrs.update(attrs)

        if not all_attrs:
            return 0.0

        m = len(methods)
        total = sum(
            sum(1 for ma in method_attrs if attr in ma) for attr in all_attrs
        )
        mean_access = total / len(all_attrs)

        if m == 1:
            return 0.0

        lcom = (mean_access - m) / (1 - m)
        return max(0.0, min(1.0, lcom))


def get_wmc_from_radon(filepath: str) -> dict[str, int]:
    """Run radon on a file and return WMC per class.

    WMC = sum of CC of individual methods, NOT the class-level CC.
    """
    try:
        result = subprocess.run(
            ["radon", "cc", filepath, "-j"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}

    wmc: dict[str, int] = {}
    for items in data.values():
        for item in items:
            if item["type"] == "class":
                total_cc = sum(m["complexity"] for m in item.get("methods", []))
                wmc[item["name"]] = total_cc
    return wmc


def analyze_project(project_path: Path) -> list[ClassMetrics]:
    """Analyze all Python files in a project."""
    class_map = ProjectClassMap()
    file_results: list[tuple[OOAnalyzer, list[ClassMetrics]]] = []

    # First pass: collect all class AST nodes for DIT resolution
    py_files = sorted(project_path.rglob("*.py"))
    py_files = [
        f for f in py_files if not any(p in EXCLUDED_DIRS for p in f.parts)
    ]

    parsed: dict[str, tuple[OOAnalyzer, ast.Module]] = {}
    for py_file in py_files:
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        analyzer = OOAnalyzer(str(py_file))
        analyzer.visit(tree)

        for name, node in analyzer.class_nodes:
            class_map.add(name, node)

        parsed[str(py_file)] = (analyzer, tree)

    # Second pass: compute DIT using the full class map, and fetch WMC
    all_classes: list[ClassMetrics] = []
    for filepath, (analyzer, tree) in parsed.items():
        wmc_data = get_wmc_from_radon(filepath)

        for cls, (name, node) in zip(analyzer.classes, analyzer.class_nodes):
            cls.dit = class_map.compute_dit(node)
            cls.wmc = wmc_data.get(cls.name, cls.methods_count)

        all_classes.extend(analyzer.classes)

    return all_classes


def detect_god_classes(
    classes: list[ClassMetrics],
    wmc_threshold: int = 50,
    cbo_threshold: int = 15,
) -> list[ClassMetrics]:
    """Mark and return potential god classes."""
    gods = []
    for cls in classes:
        if cls.wmc > wmc_threshold and cls.cbo > cbo_threshold:
            cls.is_god_class = True
            gods.append(cls)
    return gods


def print_report(
    classes: list[ClassMetrics],
    project_path: str,
    wmc_threshold: int = 50,
    cbo_threshold: int = 15,
) -> None:
    """Print OO metrics report."""
    print(f"\n{'=' * 90}")
    print("OO METRICS REPORT (Chidamber-Kemerer)")
    print(f"{'=' * 90}")
    print(f"Project: {project_path}")
    print(f"Classes found: {len(classes)}")

    by_wmc = sorted(classes, key=lambda c: c.wmc, reverse=True)

    print(f"\n--- Top 30 by WMC ---")
    print(
        f"  {'Class':<40} {'WMC':>5} {'DIT':>5} {'CBO':>5} "
        f"{'LCOM':>6} {'#Met':>5} {'God?':>5}"
    )
    print("  " + "-" * 82)

    for cls in by_wmc[:30]:
        god_mark = " !!!" if cls.is_god_class else ""
        short = cls.name if len(cls.name) < 38 else cls.name[:35] + "..."
        print(
            f"  {short:<40} {cls.wmc:>5} {cls.dit:>5} {cls.cbo:>5} "
            f"{cls.lcom:>6.2f} {cls.methods_count:>5}{god_mark}"
        )

    # Statistics
    if classes:
        wmcs = [c.wmc for c in classes]
        dits = [c.dit for c in classes]
        cbos = [c.cbo for c in classes]
        lcoms = [c.lcom for c in classes]

        print(f"\n--- Statistics ---")
        print(
            f"  WMC:  mean {mean(wmcs):.1f}, median {median(wmcs):.1f}, "
            f"stdev {stdev(wmcs):.1f}, max {max(wmcs)} ({by_wmc[0].name})"
        )
        print(
            f"  DIT:  mean {mean(dits):.1f}, median {median(dits):.1f}, "
            f"max {max(dits)}"
        )
        print(
            f"  CBO:  mean {mean(cbos):.1f}, median {median(cbos):.1f}, "
            f"max {max(cbos)}"
        )
        print(
            f"  LCOM: mean {mean(lcoms):.2f}, median {median(lcoms):.2f}, "
            f"max {max(lcoms):.2f}"
        )

    gods = [c for c in classes if c.is_god_class]
    if gods:
        gods_sorted = sorted(gods, key=lambda c: c.wmc, reverse=True)
        print(f"\n--- God classes (WMC>{wmc_threshold} AND CBO>{cbo_threshold}): {len(gods)} ---")
        for g in gods_sorted:
            rel = g.file.replace(project_path.rstrip("/") + "/", "")
            print(f"  {g.name} ({rel}:{g.lineno})")
            print(
                f"    WMC={g.wmc}, DIT={g.dit}, CBO={g.cbo}, "
                f"LCOM={g.lcom:.2f}, methods={g.methods_count}"
            )
    else:
        print(f"\n  No god classes found (WMC>{wmc_threshold} AND CBO>{cbo_threshold})")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python oo_metrics.py <project_path>")
        sys.exit(1)

    project_path = Path(sys.argv[1])
    if not project_path.is_dir():
        print(f"Directory not found: {project_path}")
        sys.exit(1)

    print(f"Analysing OO metrics: {project_path}")

    classes = analyze_project(project_path)
    if not classes:
        print("No classes found.")
        sys.exit(1)

    detect_god_classes(classes)
    print_report(classes, str(project_path))


if __name__ == "__main__":
    main()
