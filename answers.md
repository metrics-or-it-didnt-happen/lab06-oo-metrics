# Zadanie 1 - Ręczne obliczenia metryk CK

Projekt: **requests** (https://github.com/psf/requests)

Wybrałem 3 klasy o różnej wielkości: jedną dużą, jedną średnią i jedną małą.

---

## 1. Response (models.py, linia 642)

Duża klasa odpowiadająca za reprezentację odpowiedzi HTTP. Ma 22 metody.

### WMC

Policzyłem CC każdej metody z radona (`radon cc models.py -s`):

| Metoda | CC |
|---|---|
| `iter_lines` | 9 |
| `json` | 8 |
| `iter_content` | 7 |
| `content` | 6 |
| `raise_for_status` | 6 |
| `text` | 4 |
| `links` | 4 |
| `__getstate__` | 3 |
| `close` | 3 |
| `__setstate__` | 2 |
| `ok` | 2 |
| `is_redirect` | 2 |
| `is_permanent_redirect` | 2 |
| `apparent_encoding` | 2 |
| `__init__` | 1 |
| `__enter__` | 1 |
| `__exit__` | 1 |
| `__repr__` | 1 |
| `__bool__` | 1 |
| `__nonzero__` | 1 |
| `__iter__` | 1 |
| `next` | 1 |

**WMC = 68**

### DIT

`class Response:` - nie dziedziczy po niczym jawnie (domyślnie object).

**DIT = 0**

### CBO

Response referencuje sporo rzeczy z zewnątrz: moduły `encodings`, `utils`, `compat`, `hooks`, `structures`, `cookies`, `urllib3`, `chardet`/`charset_normalizer`, klasy jak `CaseInsensitiveDict`, `CookieJar`, itd. Mój skrypt policzył 30 unikalnych referencji zewnętrznych.

**CBO = 30**

Wniosek: to god class - WMC > 50 i CBO > 15. Masa odpowiedzialności: parsuje body, iteruje po contencie, obsługuje JSON, redirecty, status codes...

---

## 2. CaseInsensitiveDict (structures.py, linia 13)

Średnia klasa - słownik case-insensitive, 10 metod.

### WMC

| Metoda | CC |
|---|---|
| `__init__` | 2 |
| `__iter__` | 2 |
| `lower_items` | 2 |
| `__eq__` | 2 |
| `__setitem__` | 1 |
| `__getitem__` | 1 |
| `__delitem__` | 1 |
| `__len__` | 1 |
| `copy` | 1 |
| `__repr__` | 1 |

**WMC = 14**

### DIT

`class CaseInsensitiveDict(MutableMapping):` - dziedziczy po MutableMapping.

**DIT = 1**

### CBO

Używa `MutableMapping` (z collections.abc), `OrderedDict`... Skrypt policzył 8.

**CBO = 8**

Wniosek: OK klasa. WMC dość niski, spójna - wszystkie metody robią operacje słownikowe. Zdecydowanie nie god class.

---

## 3. AuthBase (auth.py, linia 69)

Mała klasa bazowa dla mechanizmów autentykacji. Jedna metoda.

### WMC

| Metoda | CC |
|---|---|
| `__call__` | 1 |

**WMC = 1**

### DIT

`class AuthBase:` - nie dziedziczy po niczym.

**DIT = 0**

### CBO

Nie referencuje żadnych zewnętrznych klas/modułów.

**CBO = 0**

Wniosek: minimalna klasa abstrakcyjna, definiuje tylko interfejs. Dokładnie tak powinno być.

---

## Podsumowanie

| Klasa | WMC | DIT | CBO | God class? |
|---|---|---|---|---|
| Response | 68 | 0 | 30 | Tak |
| CaseInsensitiveDict | 14 | 1 | 8 | Nie |
| AuthBase | 1 | 0 | 0 | Nie |

Sprawdziłem wyniki skryptem `oo_metrics.py` - WMC się zgadza z radonem. Response jest ewidentnie god class - robi za dużo i jest powiązana z połową projektu. Gdyby ktoś chciał ją zrefaktoryzować, to pewnie można by wydzielić np. osobną klasę do parsowania body, osobną do obsługi redirectów itd. Ale w praktyce w requests to tak po prostu jest i jakoś działa.
