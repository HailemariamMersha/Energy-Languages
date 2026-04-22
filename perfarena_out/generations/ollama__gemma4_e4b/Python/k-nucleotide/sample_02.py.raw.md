```python
import sys
from collections import Counter
from typing import List, Tuple

def solve():
    """
    Reads a FASTA sequence from stdin, calculates 1-mer and 2-mer frequencies,
    and counts specific k-mers, printing the results according to the benchmark spec.
    """
    # 1. Read and preprocess the input sequence
    try:
        # Read all input from stdin
        data = sys.stdin.read()
    except Exception:
        # Handle case where stdin might be empty or inaccessible
        data = ""

    # Filter out header lines (starting with '>') and strip all whitespace
    sequence_lines = []
    for line in data.splitlines():
        line = line.strip()
        if line and not line.startswith('>'):
            sequence_lines.append(line)
    
    sequence = "".join(sequence_lines).upper()
    L = len(sequence)

    if L == 0:
        # If no sequence is read, print nothing and exit gracefully.
        return

    # --- 1. 1-mer Frequencies ---
    
    # Count all characters, then filter for A, C, G, T
    all_counts = Counter(sequence)
    one_mer_counts = {}
    for base in 'ACGT':
        one_mer_counts[base] = all_counts.get(base, 0)

    # Prepare for sorted output: list of (count, base) tuples
    one_mers_sorted: List[Tuple[int, str]] = []
    for base in 'ACGT':
        count = one_mer_counts[base]
        one_mers_sorted.append((-count, base)) # Use negative count for descending sort on count

    one_mers_sorted.sort()

    # Output 1-mer frequencies
    for neg_count, base in one_mers_sorted:
        print(f"{abs(neg_count)}")

    # --- 2. 2-mer Frequencies ---
    
    two_mers = []
    if L >= 2:
        # Efficiently generate all overlapping 2-mers
        two_mers = (sequence[i:i+2] for i in range(L - 1))
        two_mer_counts = Counter(two_mers)
    else:
        two_mer_counts = Counter()

    # Prepare for sorted output: list of (count, mer) tuples
    two_mers_sorted: List[Tuple[int, str]] = []
    for mer, count in two_mer_counts.items():
        two_mers_sorted.append((-count, mer)) # Use negative count for descending sort

    two_mers_sorted.sort()

    # Output 2-mer frequencies
    for neg_count, mer in two_mers_sorted:
        print(f"{abs(neg_count)}")

    # --- 3. Specific K-mer Counts ---
    
    target_kmers: List[str] = [
        "GGT",
        "GGTA",
        "GGTATT",
        "GGTATTTTAATT",
        "GGTATTTTAATTTATAGT"
    ]
    
    # Calculate counts using a sliding window approach for robustness
    target_counts = {}
    for kmer in target_kmers:
        k = len(kmer)
        count = 0
        if L >= k:
            for i in range(L - k + 1):
                if sequence[i:i+k] == kmer:
                    count += 1
        target_counts[kmer] = count

    # Output specific k-mer counts (Count\tKMER)
    for kmer in target_kmers:
        count = target_counts[kmer]
        # Use sys.stdout.write for precise control over output format (tab separation)
        sys.stdout.write(f"{count}\t{kmer}\n")

if __name__ == "__main__":
    solve()
```