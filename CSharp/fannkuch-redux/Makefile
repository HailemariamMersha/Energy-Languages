LANG    = CSharp
TEST    = fannkuch-redux
SOURCE  = Program.cs
OUTPUT  = bin/Release/fannkuch-redux
ARG     = 12
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 7
REFERENCE_OUTPUT   = ../../reference/outputs/fannkuch-redux.txt

include ../../perfarena.mk
