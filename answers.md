#Analiza trzech klas Django:
Klasa ModelDetailView:

Metryki:
Liczba metod: 1
get_context_data
Cyclomatic Complexity (CC):
szacowane ręcznie: ~18
wg narzędzia radon: 26

DIP 5
```c  
                ModelDetailView
                      |
              BaseAdminDocsView 
                      |
               TemplateView
      /                 |          \
TemplateResponseMixin  View  ContextMixin
    |                   |            |
  object              object       object


```

CBO:
1. apps.get_app_config
2. Http404
3. _ (gettext)
4. models.ForeignKey
5. utils
6. inspect
7. cached_property
8. property
9. MODEL_METHODS_EXCLUDE
10. get_readable_field_data_type
11. get_return_data_type
12. method_has_no_args
13. func_accepts_kwargs
14. func_accepts_var_args
15. get_func_full_args
16. strip_p_tags
17. PermissionDenied

Klasa spelnia wymogu CBO żeby być GODclas, ale nie splenia wymogu WMC (ma jedną skomplikowaną metodę 15 CC) ale nie prekracza progu 50.
Klasa nie spełnia kryteriów GOD Class, choć wykazuje cechy problematyczne (duża złożoność jednej metody i wysokie sprzężenie).


Wynik radon
**    C 231:0 ModelDetailView - D (27) **
**    M 234:4 ModelDetailView.get_context_data - D (26) **
Różnice względem obliczeń ręcznych wynikają z tego, że:

ręczne liczenie uwzględnia głównie instrukcje decyzyjne (if, for, try)
radon dodatkowo uwzględnia m.in.:
złożone wyrażenia logiczne
comprehensions
operatory boolowskie (and, or)
ukryte ścieżki wykonania


Klasa 2:
`GZipMiddleware`
Liczba metod *1*  `process_response`
CC *~7*  radon: *10*

DIP 3
```c  
               GZipMiddleware
                      |
              MiddlewareMixin
                      |
                    object
```

CBO:
1. patch_vary_headers
2.  MiddlewareMixin
3. _lazy_re_compile
4. acompress_sequence
5. compress_sequence
6. compress_string


Klasa nie spełnia żadnych kryteriów GOD Class.

Wynik radon
django/django/middleware/gzip.py
    C 9:0 GZipMiddleware - C (11)
    M 18:4 GZipMiddleware.process_response - B (10)
Wyniki się nie zgadzają. Różnice wynikają z niedoszacowania CC przy analizie ręcznej.


Klas 3:
`LocaleMiddleware`

Liczba metod *2*  `process_response` i `process_request`
CC  process_response(4) i process_response(9) = *13*

DIP 3
```c  
               LocaleMiddleware
                      |
              MiddlewareMixin
                      |
                    object
```

CBO:
1. settings
2.  is_language_prefix_patterns_used
3. HttpResponseRedirect
4. get_script_prefix
5. is_valid_path
6. translation
7. patch_vary_headers
8. MiddlewareMixin

- Niski WMC
- umiarkowane CBO
- brak dużej złożoności

Klasa nie spelnia żadnych wymogów żeby się nazywać GODClass.

Z przeanalizowanych klas najgorzej wygląda `ModelDetailView`. Ma ona najwieksze zależności i duże WBC, ale w tym momencie jeszcze nie jest GODclass.
```py

                __
             __(o )>
~~~~~~~~~~~~~\ <_. )~~~~~~~~~~~~~~~~~~~~~~~~~~
  ~      ~    `---'      ~         ~        ~
     ~       ~        ~       ~        ~
        ~     ~    ~      ~         ~
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```