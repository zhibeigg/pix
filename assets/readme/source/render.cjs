// Requires Playwright with Chromium and Sharp; no application dependencies change.
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const sharp = require('sharp');

async function main() {
  const source = path.join(__dirname, 'hero-layout.svg');
  const output = path.join(__dirname, '..', 'hero.png');
  let svg = await fs.readFile(source, 'utf8');
  const references = [...new Set([...svg.matchAll(/href="([^"]+\.png)"/g)].map((m) => m[1]))];
  // Inline existing rasters only in memory so Chromium resolves every source.
  for (const reference of references) {
    const png = await fs.readFile(path.resolve(__dirname, reference));
    svg = svg.replaceAll(`href="${reference}"`, `href="data:image/png;base64,${png.toString('base64')}"`);
  }
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1200, height: 772 }, deviceScaleFactor: 2 });
    await page.setContent(`<html><head><meta charset="utf-8"><style>body{margin:0}svg{display:block}</style></head><body>${svg}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => [...document.querySelectorAll('image')].every((node) => node.getBBox().width > 0));
    const png = await page.locator('svg').screenshot({ animations: 'disabled' });
    await sharp(png).png({ compressionLevel: 9 }).toFile(output);
    const metadata = await sharp(output).metadata();
    const stat = await fs.stat(output);
    console.log(`${output}: ${metadata.width} x ${metadata.height}, ${Math.round(stat.size / 1024)} KiB`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
