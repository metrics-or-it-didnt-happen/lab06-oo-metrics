## zadanie 1

### trzy wybrane klasy:
1. `HTTPProxyAuth`: WMC = 1, DIT = 0, CBO = 2
2. `CookieConflictError`: WMC = 0, DIT = 0, CBO = 0
3. `Response`: WMC = 68, DIT = 0, CBO = 22

obliczenia ręczne zgadzają się z obliczeniami z radona, które z kolei zgadzają się z obliczeniami na liczydle. klasa `Response` jest dobrym kandydatem
na "god class" -- jej WMC > 50, CBO > 15, a LCOM na oko też wygląda na wysokie. "najgorzej wygląda" (o ile dobrze rozumiemy co to znaczy, że klasa źle
wygląda) klasa `CookieConflictError`, pewnie dlatego, że jest zupełnie pusta. 


