```python
import sys
from collections import Counter

def solve():
    """
    Reads a DNA sequence from stdin (FASTA format), normalizes it, and reports
    1-mer frequencies, 2-mer frequencies, and counts for specific k-mers.
    """
    # 1. Read all input from stdin
    try:
        input_data = sys.stdin.read()
    except Exception:
        # Handle case where stdin might be empty or inaccessible in some testing environments
        input_data = ""

    # 2. Extract and normalize the sequence
    # Filter out header lines (starting with '>') and strip whitespace/newlines
    sequence_parts = []
    for line in input_data.splitlines():
        line = line.strip()
        if line and not line.startswith('>'):
            sequence_parts.append(line)
    
    sequence = "".join(sequence_parts).upper()

    if not sequence:
        # If no sequence is found, print nothing and exit gracefully.
        return

    # --- 1-mer Frequencies ---
    # Use Counter for efficient counting of characters
    one_mers = Counter(sequence)
    
    # Prepare 1-mer output: sorted by count (desc), then by key (asc for stable tie-breaking)
    sorted_one_mers = sorted(one_mers.items(), key=lambda item: (-item[1], item[0]))

    # --- 2-mer Frequencies ---
    # Use a generator expression with Counter for efficient sliding window count
    two_mers = Counter(sequence[i:i+2] for i in range(len(sequence) - 1))
    
    # Prepare 2-mer output: sorted by count (desc), then by key (asc)
    sorted_two_mers = sorted(two_mers.items(), key=lambda item: (-item[1], item[0]))

    # --- Specific Fragment Counts ---
    target_fragments = [
        "GGT",
        "GGTA",
        "GGTATT",
        "GGTATTTTAATT",
        "GGTATTTTAATTTATAGT"
    ]
    
    fragment_counts = {}
    for frag in target_fragments:
        # str.count() is highly optimized for substring counting
        fragment_counts[frag] = sequence.count(frag)

    # --- Output Generation ---
    output = []

    # 1-mer output
    for kmer, count in sorted_one_mers:
        output.append(f"{kmer} {count}")

    # 2-mer output
    for kmer, count in sorted_two_mers:
        output.append(f"{kmer} {count}")

    # Fragment output (Format: count\tFragmentName)
    for frag in target_fragments:
        count = fragment_counts[frag]
        # Using f-string formatting to ensure the tab separation
        output.append(f"{count}\t{frag}")

    sys.stdout.write("\n".join(output) + "\n")

if __name__ == "__main__":
    solve()
```