# Compliance checklist (France, B2B-first)

This is an operational checklist, not legal advice. Validate your exact use case with French counsel before scaling.

## Scope first: what kind of number are you calling?

- **Corporate entity routing** (switchboard, standard company lines) is typically lower risk than calling private consumer lines.
- **Direct lines/mobile numbers tied to an individual** should be treated conservatively; some consumer-protection constraints can still apply in practice.
- Keep evidence of your lawful basis and business purpose for each list source.

## Baseline guardrails (always apply)

- Keep a durable suppression/DNC list in E.164 format and check it before every dial.
- Identify caller identity and purpose truthfully at the start of each call.
- Provide a simple opt-out in every first-turn opener.
- Do not use deceptive claims, fake urgency, or fabricated references.
- Keep data minimization strict: business contact info only, with clear usage purpose.

## France calling windows and retry limits

For campaigns that may touch consumer-like prospects, use the strict schedule by default:

- Call only Monday–Friday, 10:00–13:00 and 14:00–20:00 (prospect local time).
- Do not call Saturdays, Sundays, or public holidays.
- Do not exceed four solicitation attempts in 30 calendar days to the same person/number.
- After a refusal, stop for at least 60 days.

## Bloctel and upcoming consent shift

- Bloctel remains a central control point for French anti-solicitation enforcement.
- A major change takes effect on **August 11, 2026** for consumer cold-calling: prior consent requirements tighten significantly.
- For mixed or uncertain datasets, treat records as consent-required unless you can prove B2B-only applicability.

## Recording and AI disclosure

- If calls are recorded, use a clear consent phrase and stop recording if consent is denied.
- If asked whether the caller is AI, answer truthfully and continue only with clear permission.
- Avoid collecting sensitive personal data in call transcripts and notes.

## Operational controls to enforce

- Pre-dial suppression check (`dnc` file + CRM suppression table).
- Time-window gate by prospect timezone.
- Attempt counter per number over rolling 30 days.
- Refusal cooldown tag (60-day minimum) after explicit decline.
- Daily QA sample review for script adherence and disclosure behavior.

## Suggested opt-out phrases (French)

- "Bien sûr, je vous retire de nos appels et nous ne vous recontacterons plus."
- "Entendu, je note votre opposition et j'arrête ici. Bonne journée."

## Sources

- DGCCRF practical guidance: https://www.economie.gouv.fr/dgccrf/les-fiches-pratiques/se-proteger-du-demarchage-telephonique-abusif
- Decree n° 2022-1313 (official text): https://www.legifrance.gouv.fr/loda/id/JORFTEXT000046313317
- Service-Public update (August 11, 2026 change): https://www.service-public.fr/particuliers/actualites/A17459
- ARCEP numbering context: https://www.arcep.fr/la-regulation/grands-dossiers-reseaux-mobiles/les-numeros-polyvalents-verifies-npv.html
