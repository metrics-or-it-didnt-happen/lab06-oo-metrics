Wybrane klasy z fastapi repo:

- APIRoute C (12)
    *DIT = 3 (object -> BaseRoute -> Route -> APIRoute)
    *CBO = 10
    *WMC = 34 (3 metody)
- Body B (7)
    *DIT = 3 (object -> _Representation -> FieldInfo -> Body)
    *CBO = 8
    *WMC = 12 (2 metody)
- ApiKeyQuery A (2)
    *DIT = 3 (object -> SecurityBase -> APIKeyBase-> APIKeyQuery)
    *CBO = 2 (APIKeyBase i Request)
    *WMC = 2 (2 metody)

Wnioski: Complexity Klasy koreluje z tymi jej składowymi - tym wieksze poszczegolne skladowe w niej (mniej wiecej). Najgorzej wypadła wlasnie ta oznaczona
przez radona kategorią klasową "C". Najlepiej ta z "A". 

