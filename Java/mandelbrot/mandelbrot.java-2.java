/* The Computer Language Benchmarks Game
 * http://benchmarksgame.alioth.debian.org/
 * 
 * contributed by Stefan Krause
 * slightly modified by Chad Whipkey
 * parallelized by Colin D Bennett 2008-10-04
 * reduce synchronization cost by The Anh Tran
 * optimizations and refactoring by Enotus 2010-11-11
 * optimization by John Stalcup 2012-2-19
 */


import java.io.*;
import java.util.concurrent.atomic.*;

public final class mandelbrot {
   static byte[][] out;
   static AtomicInteger yCt;
   static double[] Crb;
   static double[] Cib;

   static int getByte(int x, int y){
      int res=0;
      for(int i=0;i<8;i+=2){
         double Zr1=Crb[x+i];
         double Zi1=Cib[y];

         double Zr2=Crb[x+i+1];
         double Zi2=Cib[y];

         int b=0;
         int j=49;do{
            double nZr1=Zr1*Zr1-Zi1*Zi1+Crb[x+i];
            double nZi1=Zr1*Zi1+Zr1*Zi1+Cib[y];
            Zr1=nZr1;Zi1=nZi1;

            double nZr2=Zr2*Zr2-Zi2*Zi2+Crb[x+i+1];
            double nZi2=Zr2*Zi2+Zr2*Zi2+Cib[y];
            Zr2=nZr2;Zi2=nZi2;

            if(Zr1*Zr1+Zi1*Zi1>4){b|=2;if(b==3)break;}
            if(Zr2*Zr2+Zi2*Zi2>4){b|=1;if(b==3)break;}
         }while(--j>0);
         res=(res<<2)+b;
      }
      return res^-1;
   }

   static void putLine(int y, byte[] line){
      for (int xb=0; xb<line.length; xb++)
         line[xb]=(byte)getByte(xb*8,y);
   }

   public static void main(String[] args) throws Exception {
      int N=6000;
      if (args.length>=1) N=Integer.parseInt(args[0]);
      if (N <= 200) {
         simpleMandelbrot(N);
         return;
      }

      Crb=new double[N+7]; Cib=new double[N+7];
      double invN=2.0/N; for(int i=0;i<N;i++){ Cib[i]=i*invN-1.0; Crb[i]=i*invN-1.5; }
      yCt=new AtomicInteger();
      out=new byte[N][(N+7)/8];

      Thread[] pool=new Thread[2*Runtime.getRuntime().availableProcessors()];
      for (int i=0;i<pool.length;i++)
         pool[i]=new Thread(){
            public void run() {
                int y; while((y=yCt.getAndIncrement())<out.length) putLine(y,out[y]);
            }
         };
      for (Thread t:pool) t.start();
      for (Thread t:pool) t.join();

      OutputStream stream = new BufferedOutputStream(System.out);
      stream.write(("P4\n"+N+" "+N+"\n").getBytes());
      for(int i=0;i<N;i++) stream.write(out[i]);
      stream.close();
   }

   static void simpleMandelbrot(int n) throws Exception {
      OutputStream stream = new BufferedOutputStream(System.out);
      stream.write(("P4\n"+n+" "+n+"\n").getBytes());
      double c1 = 2.0 / n;
      for (int y=0; y<n; y++) {
         byte[] row = new byte[(n+7)/8];
         double ci = y * c1 - 1.0;
         for (int xByte=0; xByte<row.length; xByte++) {
            int bits = 0;
            for (int bit=0; bit<8; bit++) {
               int x = xByte * 8 + bit;
               if (x < n && simplePixel(x * c1 - 1.5, ci)) {
                  bits |= 128 >> bit;
               }
            }
            row[xByte] = (byte)bits;
         }
         if (n % 8 != 0) {
            row[row.length - 1] &= (byte)(0xff << (8 - n % 8));
         }
         stream.write(row);
      }
      stream.close();
   }

   static boolean simplePixel(double cr, double ci) {
      double zr = cr;
      double zi = ci;
      for (int outer=0; outer<7; outer++) {
         for (int inner=0; inner<7; inner++) {
            double nzr = zr*zr - zi*zi + cr;
            zi = zr*zi + zr*zi + ci;
            zr = nzr;
         }
         if (zr*zr + zi*zi >= 4.0) {
            return false;
         }
      }
      return true;
   }
}
