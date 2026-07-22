// Portable single-process CLBG Mandelbrot for current Node.js.
const n = Number(process.argv[2] || 200);
const bytes = Math.ceil(n / 8);
const out = Buffer.alloc(Buffer.byteLength(`P4\n${n} ${n}\n`) + n * bytes);
let offset = out.write(`P4\n${n} ${n}\n`);
for (let y = 0; y < n; y++) {
  for (let xb = 0; xb < bytes; xb++) {
    let value = 0;
    for (let bit = 0; bit < 8; bit++) {
      const x = xb * 8 + bit;
      value <<= 1;
      if (x >= n) continue;
      const cr = 2 * x / n - 1.5, ci = 2 * y / n - 1;
      let zr = 0, zi = 0, tr = 0, ti = 0, i = 0;
      while (i++ < 50 && tr + ti <= 4) {
        zi = 2 * zr * zi + ci; zr = tr - ti + cr;
        tr = zr * zr; ti = zi * zi;
      }
      if (tr + ti <= 4) value |= 1;
    }
    out[offset++] = value;
  }
}
process.stdout.write(out);
