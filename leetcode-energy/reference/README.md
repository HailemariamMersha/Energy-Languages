# LeetCode-Energy Reference Workloads

This directory mirrors the CLBG `reference/` pattern.

- `workloads/<slug>.json` stores a self-contained curated workload for one
  LeetCode problem: cases, entry point, Python validation harness, provenance,
  and a content hash.

The 93 files are synchronized from
`LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl`. They contain
9,152 retained cases after constraint checks and semantic-validator fixes.

Every future language adapter must execute the same stored cases and implement
the same semantic validation rules. LeetCode acceptance remains the correctness
authority; these files define the reproducible local energy workload.

Regenerate them from the `Energy-Languages` repository root:

```bash
perfarena leetcode-curated-sync \
  --dataset ../LeetCodeDataset93/curated/leetcode_energy_93_curated.jsonl \
  --prune
```
