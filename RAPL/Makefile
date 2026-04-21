

all: main perfarena_runner

main : main.c rapl.o
	gcc -O2 -Wall -o main main.c rapl.o -lm
	chmod 777 main

perfarena_runner : perfarena_runner.c rapl.o rapl.h
	gcc -O2 -Wall -o perfarena_runner perfarena_runner.c rapl.o -lm
	chmod 777 perfarena_runner

rapl.o : rapl.c rapl.h
	gcc -O2 -Wall -c rapl.c  -lm

clean:
	rm -rf main.o rapl.o main perfarena_runner
