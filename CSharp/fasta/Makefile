LANG    = CSharp
TEST    = fasta
SOURCE  = Program.cs
OUTPUT  = bin/Release/fasta
ARG     = 25000000
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/fasta.txt

include ../../perfarena.mk
