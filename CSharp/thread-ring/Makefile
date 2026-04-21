LANG    = CSharp
TEST    = thread-ring
SOURCE  = Program.cs
OUTPUT  = bin/Release/thread-ring
ARG     = 50000000
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

include ../../perfarena.mk
