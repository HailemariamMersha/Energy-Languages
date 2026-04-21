LANG    = CSharp
TEST    = spectral-norm
SOURCE  = Program.cs
OUTPUT  = bin/Release/spectral-norm
ARG     = 5500
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 100
REFERENCE_OUTPUT   = ../../reference/outputs/spectral-norm.txt

include ../../perfarena.mk
