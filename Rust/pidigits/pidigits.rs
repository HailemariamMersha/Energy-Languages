extern crate num_bigint;

use num_bigint::BigInt;

fn main() {
    let count: usize = std::env::args().nth(1).and_then(|v| v.parse().ok()).unwrap_or(27);
    let (mut q, mut r, mut t) = (BigInt::from(1), BigInt::from(0), BigInt::from(1));
    let (mut k, mut next, mut l) = (BigInt::from(1), BigInt::from(3), BigInt::from(3));
    let mut digits = String::new();
    let mut i = 1;
    while i <= count {
        if 4 * &q + &r - &t < &next * &t {
            digits.push_str(&next.to_string());
            if i % 10 == 0 || i == count {
                println!("{:<10}\t:{}", digits, i);
                digits.clear();
            }
            let nr = 10 * (&r - &next * &t);
            next = (10 * (3 * &q + &r)) / &t - 10 * &next;
            q *= 10;
            r = nr;
            i += 1;
        } else {
            let nr = (2 * &q + &r) * &l;
            next = (&q * 7 * &k + 2 + &r * &l) / (&t * &l);
            q *= &k;
            t *= &l;
            l += 2;
            k += 1;
            r = nr;
        }
    }
}
