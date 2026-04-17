# Lab 06: Metryki OO - anatomia klasy pod mikroskopem

Sorry, że znowu `request`, ale w `httpx` i `flask` nie udało się znaleźć klasy ocenionej jako C…

Klasy o róznej złożoności wybrane na bazie `radon cc requests/src/ -s -a | grep "^    C "`:

- `Response` → A (4)
- `SessionRedirectMixin` → B (8)
- `RequestEncodingMixin` → C (13)

Każda z analizowanych klas nie dziedziczy jawnie po żadnej klasie użytkownika, a jedynie po domyślnym `object`, co oznacza, że ich głębokość dziedziczenia wynosi **DIT = 0**.  
    
### Klasa `Response`

**Medody i ich CC:**

| Nazwa | Ocena | CC |
| --- | --- | --- |
| `iter_lines` | B | 9 |
| `json` | B | 8 |
| `iter_content` | B | 7 |
| `content` | B | 6 |
| `raise_for_status` | B | 6 |
| `text` | A | 4 |
| `links` | A | 4 |
| `__getstate__` | A | 3 |
| `close` | A | 3 |
| `__setstate__` | A | 2 |
| `ok` | A | 2 |
| `is_redirect` | A | 2 |
| `is_permanent_redirect` | A | 2 |
| `apparent_encoding` | A | 2 |
| `__init__` | A | 1 |
| `__enter__` | A | 1 |
| `__exit__` | A | 1 |
| `__repr__` | A | 1 |
| `__bool__` | A | 1 |
| `__nonzero__` | A | 1 |
| `__iter__` | A | 1 |
| `next` | A | 1 |
    
**Suma CC:** 68
    
**Średnia CC:** 3.09
    
**Zidentyfikowane zależności:**     
- struktyry/klasy: `CaseInsensitiveDict` → 1
- funkcje pomocnicze/utils: `cookiejar_from_dict`, `iter_slices`, `stream_decode_response_unicode`, `guess_json_utf`, `parse_header_links` → 5
- JSON/encoding: `complexjson`, `RequestsJSONDecodeError`, `JSONDecodeError` → 3
- wyjątki (HTTP/requests): `HTTPError`, `ChunkedEncodingError`, `ContentDecodingError`, `RequestsSSLError`, `StreamConsumedError` → 5
- wyjątki urllib3: `SSLError`, `ReadTimeoutError`, `DecodeError`, `ProtocolError` → 4
- inne: `chardet`, `codes`, `datetime`, `generate` (definiowana w obrębie klasy, ale nie jako jej metoda) → 4

**Podsumowując: CBO = 22**
    
Klasa `Response` wykazuje **wysokie sprzężenie**, wynikające z wykorzystania wielu modułów odpowiedzialnych za: **obsługę błędów**, **przetwarzanie danych** (JSON, encoding) i **operacje na strumieniach**.
    

### Klasa `SessionRedirectMixin`

**Medody i ich CC:**

| Nazwa | Ocena | CC |
| --- | --- | --- |
| `resolve_redirects` | C | 15 |
| `should_strip_auth` | B | 10 |
| `rebuild_method` | B | 7 |
| `rebuild_proxies` | B | 6 |
| `rebuild_auth` | A | 5 |
| `get_redirect_target` | A | 2 |
    
**Suma CC:** 45
    
**Średnia CC:** 7.5
    
**Zidentyfikowane zależności:** 
- parsowanie URL: `urlparse`, `urljoin`, `requote_uri` → 3
- funkcje pomocnicze/utils: `to_native_string`, `rewind_body`, `get_netrc_auth`, `resolve_proxies`, `get_auth_from_url` → 5
- cookies: `extract_cookies_to_jar`, `merge_cookies` → 2
- auth: `_basic_auth_str` → 1
- wyjątki (requests): `ChunkedEncodingError`, `ContentDecodingError`, `TooManyRedirects` → 3
- inne: `codes`, `DEFAULT_PORTS` → 2
    
**Podsumowując: CBO = 16**
    
Klasa `SessionRedirectMixin` wykazuje **umiarkowanie wysokie sprzężenie**, ale większość zależności jest związana z **obsługą przekierowań HTTP**, co wskazuje na spójną i wyspecjalizowaną odpowiedzialność klasy.
    

### Klasa `RequestEncodingMixin`

**Medody i ich CC:**
    
| Nazwa | Ocena | CC |
| --- | --- | --- |
| `_encode_files` | D | 21 |
| `_encode_params` | C | 11 |
| `path_url` | A | 3 |
    
**Suma CC:** 35
    
**Średnia CC:** 11.67
    
**Zidentyfikowane zależności:** 
    
- URL: `urlsplit`, `urlencode` → 2
- funkcje pomocnicze/utils: `to_key_val_list`, `guess_filename` → 2
- urllib3 (fields, filepost): `encode_multipart_formdata`, `RequestField` → 2
- requests.compat: `basestring` → 1
    
**Podsumowując: CBO = 7**
    
Klasa `RequestEncodingMixin` wykazuje dość niskie sprzężenie, ponieważ jej odpowiedzialność jest ograniczona do kodowania danych wejściowych (parametrów i plików). Zależności są skoncentrowane wokół przetwarzania danych i nie obejmują szerokiego zakresu funkcjonalności systemu.

### PODSUMOWANIE


| KLASA | LICZBA METOD | WMC (SUMA CC) | DIT | CBO |
| --- | --- | --- | --- | --- |
| `Response` | 22 | 68 | 0 | 22 |
| `SessionRedirectMixin` | 6 | 45 | 0 | 16 |
| `RequestEncodingMixin` | 3 | 35 | 0 | 7 |

### Podsumowanie

Na podstawie przeprowadzonych analiz metryk (CC, WMC, DIT, CBO) trudno jednoznacznie wskazać „najgorszą” klasę. `RequestEncodingMixin` charakteryzuje się najwyższą złożonością cyklomatyczną (średnia CC ≈ 11.67), jednak wynika to głównie z jednej metody (`_encode_files`), której złożoność jest uzasadniona specyfiką problemu (obsługa wielu przypadków kodowania danych wejściowych).

Z kolei klasa `Response`, mimo niskiej średniej złożoności metod, wykazuje najwyższe sprzężenie (CBO=22), co wynika z jej centralnej roli w systemie i integracji wielu mechanizmów (obsługa błędów, strumieniowanie, dekodowanie danych). Klasa `SessionRedirectMixin` reprezentuje podejście pośrednie – umiarkowaną złożoność oraz średnie sprzężenie, wynikające z obsługi złożonej logiki przekierowań HTTP.

Wniosek: żadna z analizowanych klas nie jest jednoznacznie „najgorsza” — każda z nich optymalizuje inne aspekty (złożoność vs. sprzężenie), a interpretacja metryk powinna uwzględniać kontekst i odpowiedzialność klasy, a nie tylko wartości liczbowe.