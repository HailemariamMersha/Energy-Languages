LANG    = CSharp
TEST    = n-body
SOURCE  = Program.cs
OUTPUT  = bin/Release/n-body
ARG     = 50000000
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 1000
REFERENCE_OUTPUT   = ../../reference/outputs/n-body.txt

include ../../perfarena.mk
