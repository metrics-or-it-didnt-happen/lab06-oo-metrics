1. Trzy klasy o różnej złożoności w requests:
RequestEncodingMixin - C (13)
    WMC - metody: 3 suma CC: 35
    DIT - nie dziedziczy po niczym
    CBO - 4

SessionRedirectMixin - B (8)
    WMC - metody: 6 suma CC: 45
    DIT - nie dziedziczy po niczym
    CBO - 4

CaseInsensitiveDict - A (2)
    WMC - metody: 10 suma CC: 14
    DIT - dziedziczy po: MutableMapping -> mapping -> collection -> Sized/Iterable/Container -> object
    CBO - 2

Najbliżej do god class tieru WMC > 50 uplasowała się klasa SessionRedirectMixin
Jeśli chodzi o dziedziczenie to żadna klasa nie poszalała, wszystko jest dosyć ograniczone
CBO również nie wyszło za duże, zależą od pojedynczych modółów i funkcji pomocniczych

CBO - porównanie z wynikami skryptów: liczenie ręczne można przez okno wyrzucić, policzyłem importowane biblioteki wykorzystane i to był błąd, ale żeby się nauczyć to zostawiam pamięć po błędzie