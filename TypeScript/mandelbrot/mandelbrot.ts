const size = Number(process.argv[2] || 200);
const rowBytes = Math.ceil(size / 8);
const header = `P4\n${size} ${size}\n`;
const image = Buffer.alloc(Buffer.byteLength(header) + size * rowBytes);
let outputOffset = image.write(header);
for (let y = 0; y < size; y++) {
  for (let xb = 0; xb < rowBytes; xb++) {
    let value = 0;
    for (let bit = 0; bit < 8; bit++) {
      const x = xb * 8 + bit;
      value <<= 1;
      if (x >= size) continue;
      const cr = 2 * x / size - 1.5, ci = 2 * y / size - 1;
      let zr = 0, zi = 0, tr = 0, ti = 0, iteration = 0;
      while (iteration++ < 50 && tr + ti <= 4) {
        zi = 2 * zr * zi + ci; zr = tr - ti + cr;
        tr = zr * zr; ti = zi * zi;
      }
      if (tr + ti <= 4) value |= 1;
    }
    image[outputOffset++] = value;
  }
}
process.stdout.write(image);
