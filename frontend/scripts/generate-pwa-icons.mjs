#!/usr/bin/env node
// Generates the raster PWA/iOS icons from an inline SVG source using sharp.
//
// The brand mark is the same cream square + serif "p" + teal dot as
// public/favicon.svg. favicon.svg itself is rendered edge-to-edge, which is
// fine for a browser tab favicon but wrong for a maskable icon (Android's
// adaptive-icon mask can crop up to 20% off each edge) and wrong for iOS
// (which wants a fully opaque square with no rounded corners of its own — iOS
// applies its own mask). So this script renders three variants from one full
// bleed source SVG:
//   - pwa-192x192.png / pwa-512x512.png (purpose "any"): mark fills most of
//     the canvas, no safe-zone shrink needed.
//   - pwa-maskable-512x512.png (purpose "maskable"): full-bleed background,
//     mark shrunk to fit inside the inner 80% safe zone.
//   - apple-touch-icon.png (180x180): full-bleed background, no transparency,
//     same safe-zone treatment as maskable so it also survives iOS's own
//     rounded-corner mask.
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.join(__dirname, "..", "public");

const BACKGROUND = "#faf8f2";
const INK = "#1a1815";
const TEAL = "#1f6b6e";

/**
 * Builds the full-bleed brand mark SVG. `scale` shrinks the mark toward the
 * canvas center (1 = fills the canvas like favicon.svg; ~0.8 keeps it inside
 * the maskable/iOS safe zone).
 */
function buildIconSvg(scale) {
  const size = 64;
  const center = size / 2;
  return `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}">
      <rect width="${size}" height="${size}" fill="${BACKGROUND}" />
      <g transform="translate(${center} ${center}) scale(${scale}) translate(${-center} ${-center})">
        <text x="16" y="47" font-family="Georgia, 'Times New Roman', serif" font-size="46" fill="${INK}">p</text>
        <circle cx="47" cy="43" r="5" fill="${TEAL}" />
      </g>
    </svg>
  `.trim();
}

const targets = [
  { file: "pwa-192x192.png", size: 192, scale: 1 },
  { file: "pwa-512x512.png", size: 512, scale: 1 },
  { file: "pwa-maskable-512x512.png", size: 512, scale: 0.8 },
  { file: "pwa-maskable-192x192.png", size: 192, scale: 0.8 },
  { file: "apple-touch-icon.png", size: 180, scale: 0.8 },
];

async function main() {
  await mkdir(publicDir, { recursive: true });

  for (const { file, size, scale } of targets) {
    const svg = Buffer.from(buildIconSvg(scale));
    const outPath = path.join(publicDir, file);
    await sharp(svg, { density: 384 })
      .resize(size, size)
      .flatten({ background: BACKGROUND }) // no transparency — required for apple-touch-icon
      .png()
      .toFile(outPath);
    console.log(`wrote ${path.relative(process.cwd(), outPath)}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
