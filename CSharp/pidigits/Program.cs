using System;
using System.Numerics;
using System.Text;

public static class PiDigits
{
    public static void Main(string[] args)
    {
        int count = args.Length == 0 ? 27 : int.Parse(args[0]);
        BigInteger q = 1, r = 0, t = 1, k = 1, next = 3, l = 3;
        var digits = new StringBuilder(10);
        for (int i = 1; i <= count;)
        {
            if (4 * q + r - t < next * t)
            {
                digits.Append(next);
                if (i % 10 == 0 || i == count)
                {
                    Console.Write(digits.ToString().PadRight(10));
                    Console.WriteLine("\t:{0}", i);
                    digits.Clear();
                }
                BigInteger nr = 10 * (r - next * t);
                next = 10 * (3 * q + r) / t - 10 * next;
                q *= 10;
                r = nr;
                i++;
            }
            else
            {
                BigInteger nr = (2 * q + r) * l;
                next = (q * 7 * k + 2 + r * l) / (t * l);
                q *= k;
                t *= l;
                l += 2;
                k++;
                r = nr;
            }
        }
    }
}
