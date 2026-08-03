6. Lancer la qualité backend

.\.venv\Scripts\python.exe -m ruff check backend/app tests
.\.venv\Scripts\python.exe -m ruff format --check backend/app tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q

Résultat requis : aucun échec et, avec Docker correctement configuré, aucun test d’infrastructure ignoré.

7. Lancer la qualité frontend

cd client
npm run lint
npm test
npm run build
cd ..