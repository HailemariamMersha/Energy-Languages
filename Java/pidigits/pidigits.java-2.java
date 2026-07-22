/**
 * The Computer Language Benchmarks Game
 * http://benchmarksgame.alioth.debian.org/
 * contributed by Mike Pall
 * java port by Stefan Krause
*/
import java.math.BigInteger;

public class pidigits {
   
   final GmpInteger q = new GmpInteger(), r = new GmpInteger(),
   s = new GmpInteger(), t = new GmpInteger(); 
   final GmpInteger u = new GmpInteger(), v = new GmpInteger(),
   w = new GmpInteger(); 

   int i, k, c; 
   int digit;
   int d;
   StringBuffer strBuf = new StringBuffer(20);
   final int n;
   
   private pidigits(int n)
   {
      this.n=n;
   }
   
   private void compose_r(int bq, int br, int bs, int bt)
   {
     u.mul(r, bs);
     r.mul(r, bq);
     v.mul(t, br);
     r.add(r, v);
     t.mul(t, bt);
     t.add(t, u);
     s.mul(s, bt);
     u.mul(q, bs);
     s.add(s, u);
     q.mul(q, bq);
   }

   /* Compose matrix with numbers on the left. */
   private void compose_l(int bq, int br, int bs, int bt)
   {
     r.mul(r, bt);
     u.mul(q, br);
     r.add(r, u);
     u.mul(t, bs);
     t.mul(t, bt);
     v.mul(s, br);
     t.add(t, v);
     s.mul(s, bq);
     s.add(s, u);
     q.mul(q, bq);
   }

   /* Extract one digit. */
   private int extract(int j)
   {
     u.mul(q, j);
     u.add(u, r);
     v.mul(s, j);
     v.add(v, t);
     w.div(u, v);
     return w.intValue();
   }

   /* Print one digit. Returns 1 for the last digit. */
   private boolean prdigit(int y)
   {
      strBuf.append(y);
      if (++i % 10 == 0 || i == n) {
         if (i%10!=0) for (int j=10-(i%10);j>0;j--) { strBuf.append(" "); }
         strBuf.append("\t:");
         strBuf.append(i);
         System.out.println(strBuf);
         strBuf = new StringBuffer(20);
      }
      return i == n;
   }

   /* Generate successive digits of PI. */
   void pidigits()
   {
     int k = 1;
     d = 0;
     i = 0;
     q.set(1);
     r.set(0);
     s.set(0);
     t.set(1);
     for (;;) {
       int y = extract(3);
       if (y == extract(4)) {
         if (prdigit(y)) return;
         compose_r(10, -10*y, 0, 1);
       } else {
         compose_l(k, 4*k+2, 0, 2*k+1);
         k++;
       }
     }
   }
      
   public static void main(String[] args) {
      pidigits m = new pidigits(Integer.parseInt(args[0]));
      m.pidigits();
   }
}



class GmpInteger {
   private BigInteger value;

   public GmpInteger() { value = BigInteger.ZERO; }

   public GmpInteger(int value) {
      this();
      set(value);
   }
   
   public void set(int value) { this.value = BigInteger.valueOf(value); }

   public void mul(GmpInteger src, int val) { value = src.value.multiply(BigInteger.valueOf(val)); }
   
   public void add(GmpInteger op1, GmpInteger op2) { value = op1.value.add(op2.value); }
   
   public void div(GmpInteger op1, GmpInteger op2) { value = op1.value.divide(op2.value); }
   
   public int intValue() { return value.intValue(); }
   
   public double doubleValue() { return value.doubleValue(); }
}
