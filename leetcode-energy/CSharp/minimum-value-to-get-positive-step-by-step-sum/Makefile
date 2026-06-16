LANGUAGE = csharp
LEETCODE_LANGUAGE = csharp
SLUG = minimum-value-to-get-positive-step-by-step-sum
SOURCE = solution.cs
MODEL_SLUG ?= manual__manual
WORKLOAD = ../../reference/workloads/$(SLUG).json
REFERENCE_OUTPUT = ../../reference/outputs/$(SLUG).json

.PHONY: compile validate measure clean

compile:
	perfarena leetcode-compile --language $(LANGUAGE) --source $(SOURCE) --result compile.json

validate:
	perfarena leetcode-workload-run --language $(LANGUAGE) --problem $(SLUG) --source $(SOURCE) --workload $(WORKLOAD) --expected $(REFERENCE_OUTPUT)

measure: validate
	perfarena leetcode-measure --language $(LANGUAGE) --problems $(SLUG) --model-slug $(MODEL_SLUG) --accepted-only

clean:
	rm -f compile.json result*.json energy_*.json
	rm -rf __pycache__ .pytest_cache
