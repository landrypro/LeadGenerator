# Google Maps Lead Generator — Python + React

Application Web pour rechercher des entreprises avec **Google Places API (New) — Text Search**, dédupliquer les résultats, appliquer un rayon global et exporter les leads dans Excel.

## Stack

- API : Python 3.12, FastAPI, HTTPX et Pydantic.
- Interface : React et Vite.
- Excel : openpyxl (l’équivalent Python de ClosedXML).
- Tests : pytest avec `httpx.MockTransport`, sans appel réel à Google.
- CI : Azure DevOps YAML.

> Les références `.sln`, NuGet, ClosedXML et xUnit concernent une solution C#. Cette version étant Python + React, elles sont remplacées par leurs équivalents Python.

## Fonctionnalités

- endpoint Google `places:searchText` et masque de champs explicite ;
- pagination `nextPageToken` / `pageToken`, jusqu’à trois pages par zone ;
- recherche multi-zones en motif radial autour du centre ;
- déduplication prioritaire par `PlaceId`, avec repli nom + adresse ;
- filtrage Haversine par rayon global ;
- conservation configurable des entreprises de service sans coordonnées ;
- téléphone, site Web, adresse, coordonnées et URL Google Maps ;
- export `.xlsx` mis en forme, avec onglet récapitulatif ;
- retry exponentiel simple sur HTTP 429, erreurs 5xx, timeouts et erreurs réseau ;
- interface responsive avec capture réelle Google Maps et statistiques d’exécution ;
- identification du demandeur avant chaque génération et blocage des générations simultanées pour une même adresse ;
- pages publiques de conditions d’utilisation et de politique de confidentialité.

## Installation locale

Prérequis : Python 3.12+, Node.js 22+, un projet Google Cloud facturé avec **Places API (New)** et **Maps Static API** activées.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt

cd client
npm install
cd ..

$env:GOOGLE_MAPS_API_KEY = "VOTRE_CLE"
# Recommandé : clé serveur distincte, restreinte à Maps Static API.
$env:GOOGLE_MAPS_STATIC_API_KEY = "VOTRE_CLE_STATIC_MAPS"
```

Ne commitez jamais les clés. Si `GOOGLE_MAPS_STATIC_API_KEY` est absente, le serveur utilise `GOOGLE_MAPS_API_KEY` pour la carte ; cette clé doit alors être autorisée pour les deux API. Les clés restent côté serveur et ne sont jamais envoyées au navigateur.

### Développement

Terminal 1 :

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 :

```powershell
cd client
npm run dev
```

Ouvrez ensuite `http://localhost:5173`. Vite redirige les appels `/api` vers FastAPI.

### Build de production

```powershell
cd client
npm ci
npm run build
cd ..
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

FastAPI sert automatiquement `client/dist` lorsqu’il existe.

## Premier test recommandé

Dans l’interface, utilisez :

- objectif : 20 ;
- zones : 1 ;
- pages par zone : 1 ;
- « Téléphone et site Web » : désactivé.

Puis activez les contacts, et augmentez progressivement le nombre de zones. Utilisez un terme métier simple comme `plombier`, sans ajouter `Québec` à la requête : un lieu explicite dans `textQuery` peut prendre le dessus sur `locationBias`.

Au clic sur « Générer les leads », le prénom, la raison sociale et l’adresse professionnelle sont requis. Une même adresse ne peut lancer qu’une génération à la fois. Ce verrou est conservé uniquement en mémoire ; pour plusieurs processus ou serveurs en production, remplacez-le par un verrou distribué (par exemple Redis).

La capture Google Maps est chargée après une génération afin d’éviter des appels Maps Static inutiles pendant le réglage du formulaire. Elle constitue un appel Google Maps Platform potentiellement facturable. L’API délivre après chaque recherche un jeton de carte éphémère et à usage unique : les coordonnées de la capture ne peuvent donc pas être envoyées librement au point d’accès Maps. Ces jetons sont conservés en mémoire ; une exécution avec plusieurs processus ou serveurs nécessite un registre partagé.

## Tests

```powershell
pytest
```

La suite couvre la géométrie, le maillage, la pagination, la déduplication, le rayon, les entreprises sans coordonnées, le retry 429, le masque de champs et l’export Excel. Elle utilise uniquement de fausses réponses HTTP.

## Données exportées

`Name`, `Address`, `Phone`, `InternationalPhone`, `Website`, `GoogleMapsUrl`, `Latitude`, `Longitude`, `PlaceId`, `PrimaryType`, `BusinessStatus`, `ServiceAreaBusiness`, zone d’origine, distance, vérification du rayon et horodatage UTC.

## Limites, coûts et conformité

- Text Search (New) retourne au maximum 60 résultats sur l’ensemble des pages d’une requête. Plusieurs `locationBias` peuvent augmenter la couverture, sans garantir 200 entreprises uniques.
- Chaque zone et chaque page est un appel facturable. Les champs téléphone et site Web augmentent le niveau de facturation.
- Google ne garantit ni l’exhaustivité ni la stabilité des résultats.
- Les entreprises de service sans coordonnées peuvent être conservées, mais leur présence dans le rayon ne peut pas être vérifiée.
- Validez les conditions de stockage, d’affichage et de rafraîchissement de Google Maps Platform pour votre usage.
- Respectez les lois canadiennes et américaines applicables à la prospection et au consentement.
- Complétez l’identité juridique et les coordonnées de contact dans `client/public/conditions.html` et `client/public/confidentialite.html` avant toute mise en production commerciale.

## Références officielles

- [Text Search (New)](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [Sécurité des clés API](https://developers.google.com/maps/api-security-best-practices)
- [Maps Static API](https://developers.google.com/maps/documentation/maps-static/overview)
- [FastAPI](https://fastapi.tiangolo.com/)
- [openpyxl](https://openpyxl.readthedocs.io/)
- [pytest](https://docs.pytest.org/)
