LANG    = CSharp
TEST    = mandelbrot
SOURCE  = Program.cs
OUTPUT  = bin/Release/mandelbrot
ARG     = 16000
RUN_CMD = dotnet run --configuration Release -- $(ARG)

COMPILE_CMD = dotnet build --configuration Release --nologo

VALIDATION_N       = 200
REFERENCE_OUTPUT   = ../../reference/outputs/mandelbrot.pbm
BINARY_OUTPUT      = 1

include ../../perfarena.mk
