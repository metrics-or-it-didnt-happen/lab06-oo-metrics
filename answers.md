# Lab 06 - Answers

Analysis target: [`django/django`](https://github.com/django/django) (submodule
at `oss/django`), analysed path `oss/django/django/`.

## Task 1: Manual CK metrics

Three classes of different size and complexity were selected:

1. **`Query`** (`db/models/sql/query.py:231`) - the largest class in Django's ORM
2. **`BaseFormSet`** (`forms/formsets.py:52`) - forms subsystem, medium complexity
3. **`Signal`** (`dispatch/dispatcher.py:68`) - event dispatch, moderate size

### Class 1: `Query`

```
class Query(BaseExpression):
```

| Metric | Value | How computed |
|--------|------:|--------------|
| **WMC** | 574 | Sum of CC of 93 methods (radon). Top contributors: `get_aggregation` CC=44, `build_filter` CC=37, `names_to_path` CC=26, `combine` CC=22 |
| **DIT** | 1 | `Query` → `BaseExpression` → `object`. BaseExpression has no explicit base (implicit `object`), so depth = 1 |
| **CBO** | 276 | Extremely high. `Query` references nearly every ORM module: lookups, joins, expressions, aggregates, constraints, compiler, fields, etc. |

**Verdict:** Clear god class. WMC=574 is ~50x the median class. CBO=276 means it
is coupled to virtually every part of Django's ORM. This is expected: `Query` is
the internal representation of a SQL query, and any ORM operation eventually
touches it.

### Class 2: `BaseFormSet`

```
class BaseFormSet(RenderableFormMixin):
```

| Metric | Value | How computed |
|--------|------:|--------------|
| **WMC** | 111 | Sum of CC of 35 methods. Top: `full_clean` CC=15, `ordered_forms` CC=10, `__init__` CC=9, `deleted_forms` CC=9 |
| **DIT** | 2 | `BaseFormSet` → `RenderableFormMixin` → `RenderableMixin` → `object`. Depth = 2 |
| **CBO** | 34 | References forms, widgets, management form, validation errors, ordered/deleted form logic, rendering context |

**Verdict:** God class (WMC=111, CBO=34). `BaseFormSet` manages form
construction, validation, ordering, deletion, error collection, and rendering -
too many responsibilities for a single class. Could benefit from splitting
validation and rendering into separate concerns.

### Class 3: `Signal`

```
class Signal:
```

| Metric | Value | How computed |
|--------|------:|--------------|
| **WMC** | 68 | Sum of CC of 12 methods. Top: `_live_receivers` CC=16, `connect` CC=13, `send_robust` CC=7 |
| **DIT** | 0 | No explicit base classes (inherits only from `object` implicitly) |
| **CBO** | 32 | References threading, weakref, asyncio, logging, functools, context management |

**Verdict:** Not a god class by the strict definition (CBO=32 > 15 but WMC=68
exceeds the threshold - it is actually flagged). Still, Signal is relatively
focused: it handles connect/disconnect, sync/async send, and receiver lifecycle.
The complexity comes from handling weak references, thread safety, and
async/sync duality, which are tightly related concerns.

### Verification

All WMC values were verified against `radon cc <file> -j` by summing
`item["methods"][i]["complexity"]` (not the class-level `item["complexity"]`,
which is a different metric). Script output matches manual calculations exactly.

### Conclusions

- **Django's ORM layer is the worst offender:** `Query` (WMC=574), `QuerySet`
  (472), `BaseDatabaseSchemaEditor` (484), `SQLCompiler` (358) are all god
  classes. This is a known pattern in Django - the ORM was designed as a
  monolithic query builder.
- **DIT is shallow in Django:** Mean DIT=2.0, max=7. Python's preference for
  composition over inheritance keeps hierarchies flat. The deepest chains are in
  `db.models.fields` (ForeignKey has DIT=5).
- **High LCOM is universal in god classes:** All three analysed classes have
  LCOM > 0.9, meaning their methods rarely share instance attributes. This
  confirms they bundle unrelated responsibilities.
