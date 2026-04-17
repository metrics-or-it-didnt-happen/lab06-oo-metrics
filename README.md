# Lab 06: Metryki OO - anatomia klasy pod mikroskopem

## Czy wiesz, że...

Według badań (które właśnie wymyśliłem), przeciętna "god class" w projekcie korporacyjnym ma więcej odpowiedzialności niż przeciętny manager średniego szczebla. I tak samo trudno ją zrefaktoryzować.

## Kontekst

Do tej pory mierzyliśmy kod "płasko" - linie, złożoność funkcji. Ale programowanie obiektowe to inny świat: klasy, dziedziczenie, woda, ziemia, halucynacja, hemoglobina, taka sytuacja. W 1994 roku Chidamber i Kemerer zaproponowali zestaw sześciu metryk (CK metrics) zaprojektowanych specjalnie do oceny jakości designu obiektowego. Te metryki do dziś są standardem w badaniach nad jakością oprogramowania.

Każda metryka CK odpowiada na inne pytanie: czy klasa jest zbyt duża? Czy hierarchia dziedziczenia jest zbyt głęboka? Czy klasy są zbyt mocno ze sobą powiązane? Czy klasa jest spójna? Odpowiedzi na te pytania pomagają identyfikować problemy projektowe - w szczególności niesławną "god class", która robi wszystko i wie o wszystkim.

## Cel laboratorium

Po tym laboratorium będziesz potrafić:
- wyjaśnić co mierzą metryki CK (WMC, DIT, NOC, CBO, RFC, LCOM),
- używać modułu `ast` do analizy struktury klas w Pythonie,
- napisać skrypt identyfikujący potencjalne "god classes",
- krytycznie ocenić design obiektowy projektu na podstawie metryk.

## Wymagania wstępne

- Python 3.9+
- `radon` (`pip install radon`) - do obliczania CC metod
- Znajomość programowania obiektowego (klasy, dziedziczenie, metody)
- Sklonowany projekt open-source z rozbudowaną hierarchią klas

## Trochę teorii

### Metryki Chidamber-Kemerer (CK)

| Metryka | Nazwa | Co mierzy | Wysoka wartość oznacza... |
|---------|-------|-----------|---------------------------|
| **WMC** | Weighted Methods per Class | Suma złożoności (CC) wszystkich metod klasy | Klasa robi za dużo |
| **DIT** | Depth of Inheritance Tree | Głębokość w drzewie dziedziczenia | Zbyt głęboka hierarchia |
| **NOC** | Number of Children | Ile klas dziedziczy po tej klasie | Duży wpływ zmian |
| **CBO** | Coupling Between Objects | Ile innych klas jest referencowanych | Silne powiązania |
| **RFC** | Response For a Class | Ile metod może zostać wywołanych w odpowiedzi na wiadomość | Złożone zachowanie |
| **LCOM** | Lack of Cohesion of Methods | Ile metod nie współdzieli atrybutów | Klasa powinna być podzielona |

### "God class" - jak ją rozpoznać?

Klasa jest potencjalną "god class" jeśli:
- **WMC > 50** - ma dużo złożonych metod
- **CBO > 15** - jest powiązana z wieloma innymi klasami
- **LCOM jest wysoki** - metody nie współdzielą atrybutów (brak spójności)

## Zadania

### Zadanie 1: Teoria w praktyce (30 min)

Zanim napiszemy automat, policzmy metryki ręcznie, żeby zrozumieć co mierzymy.

**Krok 1:** Wybierz projekt OSS ze sporą liczbą klas. Sklonuj go do `/tmp`, żeby nie zaśmiecać katalogu roboczego:

```bash
cd /tmp
git clone https://github.com/psf/requests.git
git clone https://github.com/pallets/flask.git
git clone https://github.com/encode/httpx.git
```

> **Uwaga:** Analizowane projekty klonuj do `/tmp` (lub innego katalogu poza swoim repo). Nie commitujcie cudzego kodu do swojego brancha.

**Krok 2:** Znajdź 3 klasy o różnej wielkości/złożoności. Np. w requests:

```bash
# Pokaż klasy w projekcie (radon oznacza klasy literą "C" z wcięciem 4 spacji)
radon cc requests/src/requests/ -s -a | grep "^    C "
```

**Krok 3:** Dla każdej z 3 klas policz ręcznie (na papierze lub w głowie):

- **WMC** - ile metod ma klasa? Jaka jest suma ich CC? (użyj `radon cc plik.py -s`)
- **DIT** - po czym dziedziczy? Ile poziomów do `object`?
- **CBO** - ile innych klas/modułów importuje lub referencuje?

**Krok 4:** Zweryfikuj swoje obliczenia WMC za pomocą radona:

```bash
radon cc requests/src/requests/models.py -s
```

Suma CC metod klasy = WMC. Zgadza się z Twoimi obliczeniami? (Jeśli kusi Cię żeby wziąć `item["complexity"]` z JSONa radona zamiast sumować metody - patrz FAQ, zanim stracisz wieczór na debugowanie.)

**Krok 5:** Zapiszcie wyniki i wnioski - która klasa wygląda najgorzej?

### Zadanie 2: OO Metrics Analyzer (60 min)

Napiszcie skrypt `oo_metrics.py`, który analizuje klasy w projekcie Pythonowym za pomocą modułu `ast`.

**Co skrypt ma robić:**

1. Przejść rekurencyjnie po plikach `.py`
2. Sparsować każdy plik modułem `ast`
3. Dla każdej znalezionej klasy policzyć:
   - **WMC** - suma CC metod (z radona)
   - **DIT** - głębokość dziedziczenia (analiza baz klas)
   - **CBO** - ile innych klas/modułów jest referencowanych w ciele klasy
4. Oznaczyć potencjalne "god classes" (WMC > próg AND CBO > próg)
5. Wydrukować raport

**Punkt startowy:**

```python
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
        return 0

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
        return 0


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
```

**Oczekiwany output (przykład dla `requests`):**

Twoje konkretne liczby mogą się różnić w zależności od implementacji CBO i DIT - ważne, żeby WMC zgadzał się z radonem, a reszta była rozsądna. Orientacyjnie top 5 po WMC dla `requests`:

```
Analizuję metryki OO: requests/src/

================================================================================
RAPORT METRYK OBIEKTOWYCH (CK)
================================================================================

Znaleziono 44 klasy

Klasa                               WMC   DIT   CBO  Metod  God?
---------------------------------------------------------------------------
  Response                           68     0   ...     22  !!!
  HTTPAdapter                        64     1   ...     15  !!!
  PreparedRequest                    63     2   ...     13  !!!
  RequestsCookieJar                  63     2   ...     24
  Session                            52     1   ...     19  !!!
  ...
```

(WMC powinien być dokładny - to suma CC metod z radona. CBO zależy od Twojej implementacji, więc zamiast `...` zobaczysz swoje wartości. God classes to te, gdzie WMC > 50 AND CBO > 15 - ile ich będzie, zależy od Twojego CBO.)

### Zadanie 3: LCOM (45 min) - dla ambitnych

LCOM (Lack of Cohesion of Methods) to najtrudniejsza z metryk CK, ale też jedna z najciekawszych.

**Intuicja:** Klasa jest spójna, jeśli jej metody operują na tych samych atrybutach. Jeśli metody dzielą się na grupy, z których każda dotyka innych atrybutów - klasa powinna być podzielona.

**LCOM (wersja Henderson-Sellers):**
- Dla każdego atrybutu policz ile metod go używa
- LCOM = (średnia - M) / (1 - M), gdzie M = liczba metod
- LCOM bliski 0 = spójna klasa, bliski 1 = niespójna

**Do zrobienia:**
- Rozszerz `OOAnalyzer` o obliczanie LCOM
- Użyj `ast.walk` do znalezienia referencji `self.atrybut` w każdej metodzie
- Zbuduj macierz: metoda x atrybut (1 jeśli metoda używa atrybutu, 0 jeśli nie)
- Policz LCOM

```python
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
```

## Co oddajecie

W swoim branchu `lab06_nazwisko1_nazwisko2`:

1. **`oo_metrics.py`** - działający skrypt z zadania 2
2. **`answers.md`** - ręczne obliczenia metryk z zadania 1 + wnioski
3. *(opcjonalnie)* rozszerzenie skryptu o **LCOM** z zadania 3

## Kryteria oceny

- Skrypt parsuje pliki Pythona za pomocą modułu `ast` (nie regex!)
- WMC jest obliczany na podstawie danych z radona
- DIT uwzględnia jawne bazy klas (przynajmniej prosta heurystyka)
- CBO liczy unikatowe referencje do zewnętrznych nazw
- Raport jest czytelny, posortowany po WMC
- Detekcja god classes działa z konfigurowalnymi progami
- Ręczne obliczenia z zadania 1 zgadzają się z wynikami skryptu

## FAQ

**P: Moduł `ast` nie rozwiązuje importów - jak mam policzyć prawdziwy DIT?**
O: Nie musisz rozwiązywać importów. Prosta heurystyka (policz jawne bazy, odfiltruj `object`) wystarczy na potrzeby tego laba. Pełna analiza MRO wymagałaby dynamicznego importowania modułów, co jest poza zakresem.

**P: CBO wychodzi mi ogromne, bo liczę każdy `ast.Name`.**
O: Odfiltruj: `self`, `cls`, wbudowane typy (`str`, `int`, `list`, `dict`, `set`, `tuple`, `bool`, `None`, `True`, `False`), i nazwy zdefiniowane lokalnie (argumenty metod, zmienne lokalne). CBO powinno liczyć referencje do *zewnętrznych* klas/modułów.

**P: Czy `__init__` liczy się jako metoda do WMC?**
O: Tak. `__init__` to normalna metoda z punktu widzenia CC. Dunder methods (`__str__`, `__repr__`, etc.) też się liczą.

**P: W Pythonie dziedziczenie wielokrotne jest częste. Jak liczyć DIT?**
O: Weź najdłuższą ścieżkę do `object`. Jeśli klasa dziedziczy po A i B, a A dziedziczy po C, to DIT = max(DIT(A), DIT(B)) + 1. Ale w prostej wersji wystarczy policzyć jawne bazy.

**P: Mój projekt OSS nie ma dużo klas.**
O: `requests` to dobre minimum - ma ~44 klasy z kilkoma god class kandydatami. Jeśli chcesz więcej materiału: `django`, `sqlalchemy`, `boto3`, `celery`. Django ma setki klas z wielopoziomowym dziedziczeniem.

**P: Radon daje mi `item["complexity"]` dla klasy. To jest WMC, prawda?**
O: Nie. `item["complexity"]` to złożoność cyklomatyczna *samej klasy* (CC klasy jako bloku), nie suma CC jej metod. WMC = suma CC poszczególnych metod. Klasa z jedną metodą o CC=50 i klasa z 50 metodami o CC=1 mają ten sam WMC, ale `item["complexity"]` będzie drastycznie inny. Użyj `item["methods"]` żeby dostać się do metod i zsumować ich CC.

**P: Mój skrypt znalazł 0 god classes. Czy jestem geniuszem designu obiektowego?**
O: Bardziej prawdopodobne, że masz buga w CBO. Sprawdź na `requests` - `Session`, `Response`, `HTTPAdapter` i `PreparedRequest` powinny mieć WMC > 50. Jeśli WMC się zgadza a CBO nie - Twoje filtrowanie jest zbyt agresywne.

**P: Mogę użyć AI do napisania tego skryptu?**
O: Możesz użyć czego chcesz. Polecam [opencode](https://github.com/opencode-ai/opencode) + Qwen3.5-coder - darmowe, lokalne, nie wysyła Twojego kodu na serwery korporacji. Ale niezależnie od narzędzia - rozumiej co oddajesz. Kod, którego nie potrafisz wyjaśnić, nie jest Twoim kodem.

**P: Moja klasa ma LCOM = 1.0. Co zrobiłem źle?**
O: Nic - to znaczy, że Twoja klasa jest zbiorem niepowiązanych metod, które nie dzielą atrybutów. Albo odkryłeś god class, albo utility class. Albo nie znalazłeś referencji do `self.atrybut`, bo zapomniałeś o `ast.walk`.

## Przydatne linki

- [Python ast module](https://docs.python.org/3/library/ast.html)
- [Green Tree Snakes - ast tutorial](https://greentreesnakes.readthedocs.io/)
- [Chidamber & Kemerer, 1994 - oryginalny paper](https://doi.org/10.1109/32.295895)
- [radon documentation](https://radon.readthedocs.io/)
- [God class (Wikipedia)](https://en.wikipedia.org/wiki/God_object)

---
*"Każdy problem w informatyce można rozwiązać dodając kolejną warstwę abstrakcji. Oprócz problemu zbyt wielu warstw abstrakcji."* - David Wheeler (prawie na pewno)

*"God class to taka klasa, która wie o wszystkim, robi wszystko i jest jedyną rzeczą, której dotknięcie powoduje awarię produkcji o 3 w nocy."* - anonimowy programista po trzecim on-callu z rzędu
