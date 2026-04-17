# zadanie 1

Klasa Auth dziedziczy bezpośrednio z object
2 metody
suma CC 10
importuje: typing
```
    C 22:0 Auth - A (5)
    M 62:4 Auth.sync_auth_flow - A (5)
    M 87:4 Auth.async_auth_flow - A (5)
```
Klasa BrotliDecoder dziedziczenie <- ContentDecoder <- Object 
1 metoda
suma 4
brak importów
```
    C 108:0 BrotliDecoder - A (4)
    M 145:4 BrotliDecoder.flush - A (4)
```

Klasa GZipDecoder <- ContentDecoder <- Object
3 metody
suma cc 9
importy: zlib

```
    C 85:0 GZipDecoder - A (3)
    M 118:4 BrotliDecoder.__init__ - A (3)
    M 136:4 BrotliDecoder.decode - A (3)
    M 194:4 ZStandardDecoder.flush - A (3)
```