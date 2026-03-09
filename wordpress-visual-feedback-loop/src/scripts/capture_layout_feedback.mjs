#!/usr/bin/env node
import fs from 'fs';
import path from 'path';

function arg(name, fallback = null) {
  const i = process.argv.indexOf(name);
  if (i === -1 || i + 1 >= process.argv.length) return fallback;
  return process.argv[i + 1];
}

const urlsRaw = arg('--urls');
const zoomsRaw = arg('--zooms', '75,80,100');
const outDir = arg('--out-dir', `/tmp/wp-feedback-${Date.now()}`);

if (!urlsRaw) {
  console.error('Missing --urls "https://site/page1,https://site/page2"');
  process.exit(1);
}

const urls = urlsRaw.split(',').map(s => s.trim()).filter(Boolean);
const zooms = zoomsRaw.split(',').map(s => Number(s.trim())).filter(n => Number.isFinite(n) && n > 0);

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  console.error('playwright is required. Install with: npm i playwright');
  process.exit(2);
}

fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 2200 } });

const report = [];

for (const url of urls) {
  for (const zoom of zooms) {
    const page = await context.newPage();
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });

    const zoomScale = (zoom / 100).toFixed(2);
    await page.evaluate((z) => {
      document.body.style.zoom = String(z);
    }, zoomScale);

    await page.waitForTimeout(500);

    const metrics = await page.evaluate(() => {
      const nav = document.querySelector('.main-navigation');
      const menu = nav?.querySelector('.primary-menu');
      const items = menu ? Array.from(menu.querySelectorAll(':scope > li')) : [];
      const itemTops = items.map(el => Math.round(el.getBoundingClientRect().top));
      const menuRows = new Set(itemTops).size || 0;

      const masthead = document.querySelector('#masthead') || document.querySelector('.site-header');
      const branding = document.querySelector('.site-branding');
      const content = document.querySelector('#content') || document.querySelector('.site-content');

      const navRect = nav?.getBoundingClientRect();
      const mastRect = masthead?.getBoundingClientRect();
      const brandRect = branding?.getBoundingClientRect();
      const contentRect = content?.getBoundingClientRect();

      const headerOverlapRisk = !!(navRect && mastRect && navRect.bottom > mastRect.bottom + 1);
      const heroVisibilityRisk = !!(brandRect && mastRect && brandRect.bottom > mastRect.bottom + 1);
      const contentNarrowRisk = !!(contentRect && contentRect.width < 900);

      return {
        menu_rows: menuRows,
        header_overlap_risk: headerOverlapRisk,
        hero_visibility_risk: heroVisibilityRisk,
        content_narrow_risk: contentNarrowRisk,
        content_width: contentRect ? Math.round(contentRect.width) : null
      };
    });

    const safeName = url.replace(/^https?:\/\//, '').replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const shotPath = path.join(outDir, `${safeName}__z${zoom}.png`);
    await page.screenshot({ path: shotPath, fullPage: true });

    report.push({ url, zoom, screenshot: shotPath, ...metrics });
    await page.close();
  }
}

await browser.close();

const outReport = path.join(outDir, 'report.json');
fs.writeFileSync(outReport, JSON.stringify(report, null, 2));

const failures = report.filter(r => r.menu_rows > 1 || r.header_overlap_risk || r.hero_visibility_risk || r.content_narrow_risk);
console.log(`Saved report: ${outReport}`);
console.log(`Total checks: ${report.length}`);
console.log(`Failures: ${failures.length}`);
if (failures.length) {
  for (const f of failures) {
    console.log(`- FAIL ${f.url} zoom=${f.zoom} rows=${f.menu_rows} overlap=${f.header_overlap_risk} hero=${f.hero_visibility_risk} narrow=${f.content_narrow_risk}`);
  }
  process.exit(3);
}
console.log('All checks passed.');
