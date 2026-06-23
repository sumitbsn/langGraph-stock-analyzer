import fs from 'fs';
import path from 'path';

const src = path.resolve('src', 'index.html');
const outDir = path.resolve('dist');
const out = path.resolve(outDir, 'index.html');
fs.mkdirSync(outDir, { recursive: true });
fs.copyFileSync(src, out);
console.log(`Built ${out}`);
