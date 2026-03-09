# Twilio + France dialing notes

Use this as a practical checklist when pairing Retell with Twilio SIP/Voice for French outbound campaigns.

## Numbering and caller identity

- Use a caller ID format and number type accepted for your use case in France.
- Keep caller identity stable per campaign; avoid rotating numbers to bypass opt-outs.
- Ensure every displayed number can receive callbacks or has a clear callback process.

## Routing and deliverability

- Use E.164 formatting for all inputs (`+33...`).
- Validate carrier permissions for outbound international calls and SIP trunk configuration.
- Test with internal French numbers first, then limited pilot cohorts before scaling.

## Compliance operations

- Enforce suppression lists before each dial.
- Enforce local-time windows for each lead.
- Keep per-number attempt counters and refusal cooldown tracking.

## Twilio references

- France voice guideline index: https://www.twilio.com/en-us/guidelines/fr/voice
- Twilio SIP trunking docs: https://www.twilio.com/docs/sip-trunking

## France regulatory references

- DGCCRF guidance: https://www.economie.gouv.fr/dgccrf/les-fiches-pratiques/se-proteger-du-demarchage-telephonique-abusif
- ARCEP numbering context (NPV): https://www.arcep.fr/la-regulation/grands-dossiers-reseaux-mobiles/les-numeros-polyvalents-verifies-npv.html
