package main

import (
    "fmt"
    "math/big"
    "os"
    "strconv"
)

func main() {
    count := 27
    if len(os.Args) > 1 { count, _ = strconv.Atoi(os.Args[1]) }
    q, r, t := big.NewInt(1), big.NewInt(0), big.NewInt(1)
    k, next, l := big.NewInt(1), big.NewInt(3), big.NewInt(3)
    digits := ""
    four, ten := big.NewInt(4), big.NewInt(10)
    for i := 1; i <= count; {
        left := new(big.Int).Sub(new(big.Int).Add(new(big.Int).Mul(four, q), r), t)
        if left.Cmp(new(big.Int).Mul(next, t)) < 0 {
            digits += next.String()
            if i%10 == 0 || i == count { fmt.Printf("%-10s\t:%d\n", digits, i); digits = "" }
            nr := new(big.Int).Mul(ten, new(big.Int).Sub(r, new(big.Int).Mul(next, t)))
            next = new(big.Int).Sub(new(big.Int).Quo(new(big.Int).Mul(ten, new(big.Int).Add(new(big.Int).Mul(big.NewInt(3), q), r)), t), new(big.Int).Mul(ten, next))
            q.Mul(q, ten); r = nr; i++
        } else {
            nr := new(big.Int).Mul(new(big.Int).Add(new(big.Int).Mul(big.NewInt(2), q), r), l)
            numerator := new(big.Int).Add(new(big.Int).Add(new(big.Int).Mul(new(big.Int).Mul(big.NewInt(7), q), k), big.NewInt(2)), new(big.Int).Mul(r, l))
            next = new(big.Int).Quo(numerator, new(big.Int).Mul(t, l))
            q.Mul(q, k); t.Mul(t, l); l.Add(l, big.NewInt(2)); k.Add(k, big.NewInt(1)); r = nr
        }
    }
}
