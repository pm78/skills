---
name: research-to-draft-coaching
version: 0.1.0
description: Reçoit un topic, recherche automatiquement des sources récentes (< 1 semaine), les dépose dans la DB Sources, génère un brouillon «Written» dans My Articles, puis envoie le lien du draft pour revue.
---

# Recherche + Draft coaching hebdomadaire

Ce skill automatise une boucle complète de contenu :
1. recherche récente (web, publications, études, forums) pour un sujet,
2. crée des entrées Sources dans la DB `Sources` si elles n'existent pas,
3. rédige un draft long formaté (`Content`) dans `My Articles` avec statut `Written`,
4. lie les sources au draft,
5. envoie le lien du draft à des emails de relecture.

## Utilisation

```bash
python3 scripts/research_to_draft.py \
  --topic "marché coaching exécutif B2B" \
  --hours 168 \
  --max-sources 12 \
  --dry-run
```

## Variables d'environnement

- `NOTION_TOKEN` (obligatoire)
- `SOURCES_DB_ID` (défaut: `30a11393-09f8-8137-9cab-d82dff672715`)
- `MY_ARTICLES_DB_ID` (défaut: `1dc11393-09f8-8049-82eb-e18d8d012f96`)
- `OPENAI_API_KEY` (pour la rédaction automatique)
- `OPENAI_MODEL` (optionnel, défaut `gpt-4o-mini`)
- `BRAVE_API_KEY` (optionnel, utilisé si présent pour recherche web)
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `MAIL_TO` (optionnel pour notification email)

## Comportement

- Recherche uniquement les contenus capturés sur les ~7 derniers jours (`--hours 168` par défaut),
- Évite les doublons Sources (vérifie l’URL),
- Génère un titre, un `Summary`, un `SEO Description`, un `Slug` et un `Content` Markdown,
- Statuts:
  - source: `Inbox` (par défaut),
  - article: `Written`,
- ajoute une relation `Source Materials` au draft.

## Sorties

Le script affiche:
- nombre de sources trouvées/ajoutées,
- titre et URL du draft créé,
- statut final du run (ok / erreurs).
