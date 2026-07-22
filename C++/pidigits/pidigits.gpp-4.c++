#include <boost/multiprecision/cpp_int.hpp>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

using boost::multiprecision::cpp_int;

int main(int argc, char** argv) {
    int count = argc > 1 ? std::atoi(argv[1]) : 27;
    cpp_int q=1, r=0, t=1, k=1, next=3, l=3;
    std::string digits;
    for (int i=1; i<=count;) {
        if (4*q+r-t < next*t) {
            digits += next.convert_to<std::string>();
            if (i%10==0 || i==count) {
                std::cout << std::left << std::setw(10) << digits << "\t:" << i << '\n';
                digits.clear();
            }
            cpp_int nr=10*(r-next*t);
            next=(10*(3*q+r))/t-10*next;
            q*=10; r=nr; ++i;
        } else {
            cpp_int nr=(2*q+r)*l;
            next=(q*7*k+2+r*l)/(t*l);
            q*=k; t*=l; l+=2; ++k; r=nr;
        }
    }
}
