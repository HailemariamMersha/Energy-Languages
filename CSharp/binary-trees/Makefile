LANG    = CSharp
TEST    = binary-trees
SOURCE  = Program.cs
OUTPUT  = bin/Release/binary-trees
ARG     = 21
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 10
REFERENCE_OUTPUT   = ../../reference/outputs/binary-trees.txt

include ../../perfarena.mk
