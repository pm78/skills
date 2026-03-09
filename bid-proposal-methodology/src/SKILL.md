---
name: bid-proposal-methodology
description: >
  Méthodologie complète de gestion des propositions commerciales en 3 phases :
  Bid Collection, Strategy, Proposal Writing. Utiliser cette skill quand l'utilisateur
  demande de préparer une réponse à appel d'offres, de qualifier une opportunité,
  de construire une stratégie de réponse, de rédiger une proposition commerciale,
  de calculer un pricing, de vérifier la qualité d'une proposition avant soumission,
  ou de suivre le cycle de vie d'un bid. Couvre aussi les décisions go/no-go,
  la construction de prix, l'analyse concurrentielle bid-level, et le QC final.
  Langue des livrables externes : français. Documentation interne : anglais.
---

# Bid Proposal Methodology

## Principes directeurs

1. **Gagner ET être rentable** — toute proposition doit satisfaire les deux critères simultanément.
2. **Traçabilité des décisions** — chaque décision stratégique (go/no-go, pricing, staffing) est documentée avec date, auteur, et rationale.
3. **Qualité avant vitesse** — ne jamais soumettre sans passer la QC checklist.
4. **Réutilisabilité** — capitaliser les contenus (sections, pricing models, références clients) dans une bibliothèque interne.
5. **Langue** — livrables clients en français, documentation interne et technique en anglais.

## KPIs opérationnels

| KPI | Cible | Mesure |
|-----|-------|--------|
| Intake completeness | ≥ 90% des champs remplis | Dossier de travail Phase 1 |
| Qualification SLA | ≤ 48h entre réception et go/no-go | Timestamp décision |
| Go/No-go ratio | ≥ 60% go sur bids qualifiés | Registre des bids |
| Margin-floor compliance | 100% au-dessus du plancher | Pricing model vérifié |
| On-time submission | 100% | Timestamp soumission vs deadline |
| Win rate | ≥ 30% (cible Y1) | Post-mortem tracking |

## Vue d'ensemble des 3 phases

```
┌─────────────────────┐    ┌──────────────────────┐    ┌────────────────────────┐
│  PHASE 1            │    │  PHASE 2             │    │  PHASE 3               │
│  BID COLLECTION     │───▶│  STRATEGY            │───▶│  PROPOSAL WRITING      │
│                     │    │                      │    │                        │
│  Capturer           │    │  Itérer solution,    │    │  Rédiger, assembler,   │
│  Qualifier          │    │  coût, prix, marge   │    │  QC, exporter, valider │
│  Décision go/no-go  │    │  jusqu'à winning &   │    │  et soumettre          │
│                     │    │  profitable          │    │                        │
│  Gate: GO/NO-GO     │    │  Gate: PRICING LOCK  │    │  Gate: QC PASS         │
└─────────────────────┘    └──────────────────────┘    └────────────────────────┘
```

---

## Phase 1 — Bid Collection

**Objectif** : Capturer toute l'intelligence nécessaire et décider go/no-go en ≤ 48h.

### Entrées requises

Collecter avant de qualifier. Si des éléments manquent, les demander explicitement.

| Catégorie | Éléments |
|-----------|----------|
| Client | Nom, secteur, taille, géographie, contacts clés, historique relation |
| Appel d'offres | Source (portail, réseau, partenaire), date réception, deadline soumission, format attendu, critères d'évaluation pondérés |
| Périmètre | Description du besoin, lots, phases, livrables attendus, durée |
| Budget | Enveloppe connue ou estimée, modèle (forfait, régie, mixte) |
| Concurrence | Compétiteurs identifiés, position relative, historique |
| Contraintes | Juridiques, réglementaires, techniques, sécurité, sous-traitance |

### Matrice de qualification (scoring 0-100)

| Critère | Poids | Scoring |
|---------|-------|---------|
| Alignement stratégique | 25% | Fort=100, Moyen=50, Faible=0 |
| Capacité de livraison | 20% | Complète=100, Partielle=50, Insuffisante=0 |
| Avantage compétitif | 20% | Dominant=100, Comparable=50, Défavorable=0 |
| Probabilité de gain | 20% | >60%=100, 30-60%=50, <30%=0 |
| Rentabilité prévisible | 15% | >plancher+10pts=100, >plancher=50, <plancher=0 |

**Seuils de décision** :
- **GO** : Score ≥ 65 et aucun critère à 0
- **GO CONDITIONNEL** : Score 50-64 — escalade au sponsor
- **NO-GO** : Score < 50 ou un critère bloquant à 0

### Gate de sortie Phase 1

- [ ] Dossier de travail créé et rempli à ≥ 90%
- [ ] Scoring de qualification calculé et documenté
- [ ] Décision go/no-go signée (avec date, auteur, rationale)
- [ ] Équipe de réponse assignée
- [ ] Planning de réponse établi (jalons intermédiaires + deadline)
- [ ] Fichier nommé selon convention : `BID-YYYY-NNN_<Client>_<Intitulé-court>`

---

## Phase 2 — Strategy

**Objectif** : Itérer solution, coût de livraison, prix et marge jusqu'à obtenir une offre winning ET profitable.

### Boucle stratégique

```
      ┌──────────────────────────────────────────┐
      │                                          │
      ▼                                          │
  Solution ──▶ Coût de livraison ──▶ Prix ──▶ Marge
      │              │                │          │
      │     OK ?     │       OK ?     │   OK ?   │
      │    Non ──────┘       Non ────┘   Non ───┘
      │    Oui                Oui         Oui
      ▼                                   │
  PRICING LOCK ◀──────────────────────────┘
```

### Étapes clés

1. **Solution design** : Définir l'approche technique, méthodologique, et organisationnelle.
2. **Staffing plan** : Profils, séniorité, taux, disponibilité.
3. **Costing** : Calculer le coût de revient complet (voir `references/pricing-framework.md`).
4. **Pricing** : Appliquer la stratégie de prix (value-based, compétitif, cost-plus).
5. **Margin check** : Vérifier respect du plancher de marge.
6. **Win themes** : 3-5 messages clés différenciants.
7. **Risk register** : Risques identifiés + mitigations + provisions.

### Gate de sortie Phase 2

- [ ] Solution design validée
- [ ] Pricing model verrouillé (voir `references/pricing-framework.md`)
- [ ] Marge ≥ plancher (documentation justificative si dérogation)
- [ ] Win themes définis (3-5)
- [ ] Risk register complété
- [ ] Accord du sponsor sur le prix final

---

## Phase 3 — Proposal Writing

**Objectif** : Rédiger, assembler, QC, exporter et soumettre dans les délais.

### Mode de sortie par défaut: `CLIENT-READY` (obligatoire)

Le livrable final doit être prêt à envoi client, pas un plan interne. Interdire explicitement les sorties "plan-only" et "bullet-only".

Exigences minimales:
- DOCX proposition avec narration explicative complète (pas seulement des listes).
- PPTX executive deck avec storyline C-level et décisions attendues.
- Annexes opérationnelles: pricing détaillé, conformité, RACI, risques.

### Contrat de livrables (Definition of Done)

**Ne jamais marquer DONE sans ces artefacts minimum**:
- `...Proposition-<version>.docx`
- `...Executive-Deck-<version>.pptx`
- `COMPLIANCE-MATRIX-<version>.csv`
- `RACI-<version>.csv`
- `PRICING-TABLES-<version>.csv` (ou xlsx)
- `QC-REPORT-<version>.md`

### Templates et branding (obligatoire)

Si des templates de marque sont fournis (docx/potx/guidelines), ils doivent être appliqués aux livrables. Le rapport QC doit inclure une section `Template Compliance` avec:
- Template(s) utilisé(s)
- Contrôles passés/échoués
- Écarts résiduels éventuels

### Gate qualité bloquant

Exécuter la checklist de `references/qc-checklist.md`.
Si un critère bloquant échoue, statut final = `FAILED_QC` (pas `DONE`).

### Workflow de rédaction

1. **Plan de proposition** : Définir la structure (voir `references/proposal-template.md`).
2. **Assignation** : Répartir les sections entre rédacteurs.
3. **Rédaction** : Produire les sections en respectant le template.
4. **Revue croisée** : Chaque section relue par un pair.
5. **Intégration** : Assembler le document complet.
6. **QC** : Appliquer la checklist (voir `references/qc-checklist.md`).
7. **Export** : Générer le livrable final (.docx, .pdf, .pptx selon demande).
8. **Validation finale** : Approbation du sponsor.
9. **Soumission** : Déposer avant la deadline avec accusé de réception.

### Règles de rédaction

- Ton professionnel, affirmatif, orienté bénéfices client.
- Pas de jargon interne non expliqué.
- Chaque section doit répondre directement à un critère d'évaluation.
- Preuves : références clients, chiffres, certifications.
- Respecter la limite de pages si imposée.

### Gate de sortie Phase 3

- [ ] QC checklist 100% conforme (voir `references/qc-checklist.md`)
- [ ] Document exporté dans le format requis
- [ ] Relecture finale par le sponsor
- [ ] Soumission effectuée avant deadline
- [ ] Accusé de réception archivé
- [ ] Post-mortem planifié (J+7 après notification résultat)

---

## Anti-erreurs fréquentes

| Erreur | Prévention |
|--------|------------|
| Soumission sans go/no-go formel | Gate Phase 1 obligatoire |
| Prix sous le plancher de marge | Contrôle automatique dans le pricing model |
| Copier-coller d'une ancienne proposition sans adapter | QC checklist item : vérifier cohérence nom client/projet |
| Oublier un critère d'évaluation dans la réponse | Matrice de traçabilité critères → sections |
| Dépasser la deadline | Planning avec jalon J-3 pour buffer |
| Sous-estimer l'effort de livraison | Validation du staffing plan par le COO/delivery |
| Ignorer les risques juridiques | Section risques obligatoire + revue CLO si > seuil |

---

## Références

- **Dossier de travail** : `references/dossier-checklist.md` — checklist complète du dossier de travail par phase
- **Template de proposition** : `references/proposal-template.md` — gabarit des sections obligatoires
- **Cadre pricing/marge** : `references/pricing-framework.md` — inputs, scénarios, marge plancher, sécurités
- **QC checklist** : `references/qc-checklist.md` — contrôles qualité avant soumission
- **Snippets prompts** : `references/prompt-snippets.md` — prompts réutilisables pour chaque étape clé
- **Convention de nommage** : `references/naming-conventions.md` — format de nommage interne/externe

## Dépendances skills

- **docx** : Génération du document de proposition (.docx)
- **pptx** : Génération de la présentation de soutenance (.pptx)
- **xlsx** : Génération des annexes financières et tableaux de pricing (.xlsx)
- **pdf** : Export PDF final si requis
- **strategy-intelligence-suite** : Intelligence marché et concurrentielle en amont
- **prospecting-intelligence** : Données comptes/contacts si bid proactif
