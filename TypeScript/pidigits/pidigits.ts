// CLBG pidigits using the unbounded spigot algorithm and native bigint.
const count = Number(process.argv[2] || 27);
let q = 1n, r = 0n, t = 1n, k = 1n, next = 3n, l = 3n;
let digits = "";
for (let i = 1; i <= count;) {
  if (4n * q + r - t < next * t) {
    digits += next.toString();
    if (i % 10 === 0 || i === count) {
      console.log(`${i % 10 === 0 ? digits : digits.padEnd(10, " ")}\t:${i}`);
      digits = "";
    }
    const nr = 10n * (r - next * t);
    next = (10n * (3n * q + r)) / t - 10n * next;
    q *= 10n; r = nr; i++;
  } else {
    const nr = (2n * q + r) * l;
    next = (q * 7n * k + 2n + r * l) / (t * l);
    q *= k; t *= l; l += 2n; k += 1n; r = nr;
  }
}
