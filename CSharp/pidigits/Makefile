LANG    = CSharp
TEST    = pidigits
SOURCE  = Program.cs
OUTPUT  = bin/Release/pidigits
ARG     = 10000
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 27
REFERENCE_OUTPUT   = ../../reference/outputs/pidigits.txt

include ../../perfarena.mk
