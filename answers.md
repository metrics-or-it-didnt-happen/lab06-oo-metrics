1. Klasa RequestEncodingMixin
   WMC = 35, DIT = 1, CBO = 7
2. Klasa Respons
   WMC = 68, DIT = 1, CBO = 20
3. Klasa AuthBase
   WMC = 1, DIT = 1, CBO = 1 
---
Najgorzej wypada klasa Response, ponieważ ze swoim ogromnym WMC (~68) i wysokim CBO (~20) działa jak tzw. "Boski Obiekt", który wie i robi zbyt wiele. Przez tak ogromne sprzężenie i złożoność jest to klasa najtrudniejsza do przetestowania i najbardziej podatna na błędy przy modyfikacjach kodu