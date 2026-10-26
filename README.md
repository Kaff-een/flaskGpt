# FlaskGPT — assistant augmenté

Application Flask + Tailwind de chat documenté : conversations persistées, domaines
spécialisés, sources sélectionnables, mesure de performance, évaluation des réponses,
exports et gouvernance des jeux de données.

## Démarrage

```powershell
cd 2
python -m pip install -r requirements.txt
copy .env.example .env
npm install          # uniquement pour reconstruire le CSS
npm run build
python app.py
```

L'application écoute sur <http://127.0.0.1:5000>. La base SQLite `data/app.db` est
créée automatiquement au premier lancement, avec 8 domaines et 24 documents de
référence.

## Configuration

Tout se règle dans `.env` (voir `.env.example`) :

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `LLM_PROVIDER` | `ollama`, `openai` ou `demo` | `ollama` |
| `OLLAMA_HOST` | URL du service Ollama | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modèle local | `llama3.2:3b` |
| `OPENAI_BASE_URL` | API compatible OpenAI | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Modèle distant | `gpt-4o-mini` |
| `OPENAI_API_KEY` | Clé API | vide |
| `ALLOW_DEMO_FALLBACK` | Réponse locale si connexion impossible | `true` |
| `LLM_TIMEOUT` | Délai maximal (secondes) | `300` |
| `LLM_MAX_TOKENS` | Tokens générés par réponse | `1024` |

### Ollama

```powershell
ollama serve
ollama pull llama3.2:3b
# variante légère pour tester rapidement :
ollama pull qwen2.5:0.5b
```

Puis `OLLAMA_MODEL=qwen2.5:0.5b` dans `.env`.

### API compatible OpenAI

Décommentez le bloc OpenAI dans `.env`, renseignez `OPENAI_API_KEY`, puis
redémarrez. Les erreurs de clé invalide, de quota et de connexion sont affichées
avec un code stable et une action corrective.

## Fonctionnalités

- **Conversations** : nouvelle conversation, effacement complet (messages, notes,
  métriques) et historique persistant dans SQLite.
- **Domaines** : général, informatique, finance, analyse de données, école,
  santé, droit et marketing. Chaque domaine possède son prompt système.
- **Sources** : panneau de sélection avec cases à cocher, choix du nombre
  d'extraits par source et de lignes par extrait. Chaque réponse enregistre les
  passages utilisés, leur pertinence et un lien vers le document complet. Les
  citations `[Source N]` présentes dans la réponse sont cliquables et ouvrent le
  passage correspondant.
- **Erreurs lisibles** : clé invalide, quota épuisé, modèle absent, service
  injoignable. En cas de simple panne de connexion, une réponse locale construite
  à partir des sources peut prendre le relais (clairement signalée).
- **PDF et exports** : synthèse PDF de la conversation, export TXT, JSON, PDF de
  la conversation et PDF de synthèse.
- **Performances** : durée, tokens d'entrée/sortie, débit, moyenne, p50/p95,
  taux de réussite et comparaison des dernières réponses.
- **Évaluation** : boutons Satisfaisante / Moyenne / Insuffisante, note 1 à 5,
  code couleur de la carte et indicateurs agrégés.
- **Données & gouvernance** : import CSV, TSV, TXT, Excel, JSON, JSONL et SQLite
  (50 000 lignes et 200 colonnes maximum). Le rapport couvre complétude, unicité,
  doublons exacts et fonctionnels, cohérence, validité, valeurs atypiques,
  données personnelles, documentation, clé métier et fraîcheur. Exports PDF/JSON
  et réutilisation du jeu de données comme source de chat.

## Import de données

Depuis `/data`, déposez un fichier ou utilisez l'API :

```powershell
curl.exe -F "file=@ventes.csv" http://127.0.0.1:5000/api/datasets/import
```

Une base SQLite peut contenir plusieurs tables : chacune devient un jeu de
données analysé séparément, puis une source interrogeable dans le domaine
« Analyse de données ».

## Structure

```
app.py          routes pages et API
db.py           schéma SQLite, requêtes, agrégats
llm.py          Ollama / OpenAI / mode local, erreurs normalisées
sources.py      recherche documentaire, extraits, contexte
analytics.py    import et rapport qualité / gouvernance
reporting.py    exports TXT, JSON, PDF et synthèses
seed_data.py    domaines et documents de référence
templates/      pages Jinja (chat, données, tableau de bord)
static/dist/js/ interface (chat, données, composants communs)
src/input.css   styles Tailwind et composants
```

## Vérifications rapides

```powershell
python -m compileall -q app.py db.py llm.py sources.py analytics.py reporting.py
python app.py
```

Puis ouvrir `/api/health`, `/api/sources?domain=informatique`, `/dashboard` et
`/data`. Les exports sont accessibles depuis l'interface ou directement via
`/api/conversations/<id>/export/txt|json|pdf|summary`.
