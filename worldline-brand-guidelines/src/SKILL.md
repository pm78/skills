---
name: worldline-brand-guidelines
description: Applies Worldline brand colors and typography to artifacts that benefit from a consistent Worldline look-and-feel (slides, docs, web UI). Use it when brand colors or style guidelines, visual formatting, or company design standards apply.
license: Complete terms in LICENSE.txt
---

# Worldline Brand Styling

## Overview

Use this skill to style artifacts according to Worldline's brand identity (colors, typography, and logo usage).

**Keywords**: branding, corporate identity, visual identity, styling, brand colors, typography, Worldline, visual formatting, visual design

## Brand Sources

- Worldline Image Library: `https://worldline.com/en/home/about-us/image-library.html`
- Logo (SVG): `https://worldline.com/content/dam/worldline/global/images/image-library/WL_Logo_MasterMint.svg`
- Brand identity notes (Master Mint, eco-conscious typography): `https://worldline.com/content/dam/worldline/global/documents/reports/worldline-integrated-report-2021.pdf`

## Brand Guidelines

### Colors

**Core Colors:**

- Master Mint: `#00B2A9` - Primary accent, highlights, key UI elements
- Dark Grey: `#2D2D2D` - Primary text, dark UI surfaces
- White: `#FFFFFF` - Primary background, text on dark
- Light Grey: `#F5F5F5` - Subtle backgrounds, separators (neutral)

**Accent Tints (derived from Master Mint):**

- Mint 80%: `#33C1BA`
- Mint 60%: `#66D1CB`

### Typography

Worldline’s public materials describe an eco-conscious typographic approach, but do not consistently publish a single, explicit typeface name.

- If you have Worldline’s official corporate typeface installed, use it.
- Otherwise, use a close, modern substitute:
  - **Headings**: Inter (variable) with Arial fallback
  - **Body Text**: Inter with Arial fallback

## Features

### Smart Font Application

- Applies Inter to headings (24pt and larger)
- Applies Inter to body text
- Automatically falls back to Arial if Inter is unavailable
- Preserves readability across systems

### Text Styling

- Headings (24pt+): Inter (Bold/Semibold preferred)
- Body text: Inter (Regular)
- Smart color selection based on background (Dark Grey vs White)
- Preserves text hierarchy and formatting

### Shape and Accent Colors

- Non-text shapes use Master Mint accents (and tints when variety helps)
- Maintains a minimal palette with strong brand consistency

## Assets

- Included logo: `assets/WL_Logo_MasterMint.svg` (Worldline Image Library)

## Technical Details

### Font Management

- Uses system-installed Inter when available
- Falls back to Arial when custom fonts are unavailable
- If you have Worldline’s official corporate typeface installed, prefer it over substitutes

### Color Application

- Core colors match the official logo SVG fills (`#00B2A9`, `#2D2D2D`)
- Apply as RGB/hex values depending on the target artifact/tooling
