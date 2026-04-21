LANG    = CSharp
TEST    = k-nucleotide
SOURCE  = Program.cs
OUTPUT  = bin/Release/k-nucleotide
ARG     = 21
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 0
REFERENCE_OUTPUT   = ../../reference/outputs/k-nucleotide.txt
STDIN_FILE         = ../../reference/inputs/fasta-10000.txt

include ../../perfarena.mk
