// CLBG pidigits using the unbounded spigot algorithm and native BigInt.
const n = Number(process.argv[2] || 27);
let q = 1n, r = 0n, t = 1n, k = 1n, nn = 3n, l = 3n;
let digits = "";
for (let i = 1; i <= n;) {
  if (4n * q + r - t < nn * t) {
    digits += nn.toString();
    if (i % 10 === 0 || i === n) {
      const shown = i % 10 === 0 ? digits : digits.padEnd(10, " ");
      console.log(`${shown}\t:${i}`);
      digits = "";
    }
    const nr = 10n * (r - nn * t);
    nn = ((10n * (3n * q + r)) / t) - 10n * nn;
    q *= 10n; r = nr; i++;
  } else {
    const nr = (2n * q + r) * l;
    const nnn = (q * (7n * k) + 2n + r * l) / (t * l);
    q *= k; t *= l; l += 2n; k += 1n; r = nr; nn = nnn;
  }
}
