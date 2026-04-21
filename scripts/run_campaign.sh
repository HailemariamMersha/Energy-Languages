#!/bin/bash
# PerfArena full campaign runner.
#
# Generates N samples for every (language, problem) cell using the
# specified model, then validates and optionally measures each one.
#
# Usage:
#   ./scripts/run_campaign.sh                          # defaults
#   ./scripts/run_campaign.sh --samples 10             # more samples
#   ./scripts/run_campaign.sh --languages python,cpp   # subset
#   ./scripts/run_campaign.sh --problems binary-trees   # subset
#   ./scripts/run_campaign.sh --no-measure             # skip measurement
#
# Environment:
#   OLLAMA_HOST   URL of the Ollama endpoint (required for ollama provider)
#   PROVIDER      LLM provider (default: ollama)
#   MODEL         Model name (default: gemma4:e4b)
#   SAMPLES       Samples per cell (default: 3)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR"

# Defaults
PROVIDER="${PROVIDER:-ollama}"
MODEL="${MODEL:-gemma4:e4b}"
SAMPLES="${SAMPLES:-3}"
TEMPERATURE="${TEMPERATURE:-0.2}"
VIA_AGENT="--via-agent"
DO_MEASURE=true

ALL_LANGS="python javascript typescript java csharp cpp php go rust ruby"
ALL_PROBS="binary-trees fannkuch-redux fasta k-nucleotide mandelbrot n-body pidigits regex-redux reverse-complement spectral-norm"

LANGS="$ALL_LANGS"
PROBS="$ALL_PROBS"

# Parse flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --samples)     SAMPLES="$2"; shift 2 ;;
        --languages)   LANGS="$(echo "$2" | tr ',' ' ')"; shift 2 ;;
        --problems)    PROBS="$(echo "$2" | tr ',' ' ')"; shift 2 ;;
        --provider)    PROVIDER="$2"; shift 2 ;;
        --model)       MODEL="$2"; shift 2 ;;
        --temperature) TEMPERATURE="$2"; shift 2 ;;
        --no-agent)    VIA_AGENT=""; shift ;;
        --no-measure)  DO_MEASURE=false; shift ;;
        *)             echo "Unknown flag: $1" >&2; exit 1 ;;
    esac
done

N_LANGS=$(echo $LANGS | wc -w | tr -d ' ')
N_PROBS=$(echo $PROBS | wc -w | tr -d ' ')
TOTAL_CELLS=$((N_LANGS * N_PROBS))
TOTAL_GENS=$((TOTAL_CELLS * SAMPLES))

echo "============================================"
echo "PerfArena campaign"
echo "============================================"
echo "Provider:    $PROVIDER"
echo "Model:       $MODEL"
echo "Languages:   $N_LANGS ($LANGS)"
echo "Problems:    $N_PROBS"
echo "Samples:     $SAMPLES per cell"
echo "Total:       $TOTAL_GENS generations across $TOTAL_CELLS cells"
echo "Agent:       ${VIA_AGENT:-disabled}"
echo "Measure:     $DO_MEASURE"
echo "============================================"
echo ""

# Results tracking
RESULTS_DIR="perfarena_out/campaign_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"
LOG="$RESULTS_DIR/campaign.log"

GEN_PASS=0
GEN_FAIL=0
VAL_PASS=0
VAL_FAIL=0

for lang in $LANGS; do
    for prob in $PROBS; do
        echo "--- $lang / $prob ---" | tee -a "$LOG"

        # Generate
        if perfarena generate \
            --provider "$PROVIDER" \
            --model "$MODEL" \
            --problem "$prob" \
            --language "$lang" \
            --samples "$SAMPLES" \
            --temperature "$TEMPERATURE" \
            $VIA_AGENT 2>&1 | tee -a "$LOG"; then
            GEN_PASS=$((GEN_PASS + 1))
        else
            GEN_FAIL=$((GEN_FAIL + 1))
            echo "  GENERATION FAILED: $lang/$prob" | tee -a "$LOG"
            continue
        fi

        # Validate each sample
        MODEL_SLUG="$(echo "${PROVIDER}__${MODEL}" | sed 's/[^a-zA-Z0-9._-]/_/g')"
        LANG_FOLDER=$(python3 -c "
from perfarena.config import load_config
cfg = load_config()
print(cfg.get_language('$lang').folder)
")
        EXT=$(python3 -c "
from perfarena.config import load_config
cfg = load_config()
print(cfg.get_language('$lang').file_extension)
")

        for i in $(seq 0 $((SAMPLES - 1))); do
            SAMPLE_FILE="perfarena_out/generations/${MODEL_SLUG}/${LANG_FOLDER}/${prob}/sample_$(printf '%02d' $i)${EXT}"
            STAGED="perfarena_generated${EXT}"

            if [ ! -f "$SAMPLE_FILE" ]; then
                echo "  sample $i: source file missing, skipping" | tee -a "$LOG"
                continue
            fi

            CELL_DIR="${LANG_FOLDER}/${prob}"
            cp "$SAMPLE_FILE" "${CELL_DIR}/${STAGED}" 2>/dev/null || continue

            # Validate
            if (cd "$CELL_DIR" && make validate SOURCE="$STAGED" 2>&1) | tee -a "$LOG" | grep -q "PASS"; then
                VAL_PASS=$((VAL_PASS + 1))
                echo "  sample $i: PASS" | tee -a "$LOG"
            else
                VAL_FAIL=$((VAL_FAIL + 1))
                echo "  sample $i: FAIL" | tee -a "$LOG"
            fi
        done
        echo "" | tee -a "$LOG"
    done
done

echo "============================================" | tee -a "$LOG"
echo "CAMPAIGN RESULTS" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
echo "Generation:  $GEN_PASS cells OK, $GEN_FAIL failed" | tee -a "$LOG"
echo "Validation:  $VAL_PASS samples PASS, $VAL_FAIL FAIL" | tee -a "$LOG"
echo "Pass rate:   $(python3 -c "t=$VAL_PASS+$VAL_FAIL; print(f'{$VAL_PASS/t*100:.1f}%' if t else 'n/a')")" | tee -a "$LOG"
echo "Log:         $LOG" | tee -a "$LOG"
echo "============================================" | tee -a "$LOG"
