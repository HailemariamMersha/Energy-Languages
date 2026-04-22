import sys
from collections import Counter

def solve():
    """
    Reads a FASTA sequence from stdin, calculates 1-mer and 2-mer frequencies,
    and counts occurrences of specific k-mers, printing results according
    to the benchmark specification.
    """
    # Read all input from stdin
    input_data = sys.stdin.read()

    # 1. Extract and normalize the sequence
    sequence_lines = []
    in_sequence = False
    
    # Simple FASTA parser: assumes the sequence is contiguous after headers
    for line in input_data.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('>'):
            # Start of a new record, set flag
            in_sequence = True
            continue
        
        if in_sequence:
            # Append sequence data, ensuring uppercase
            sequence_lines.append(line.upper())

    sequence = "".join(sequence_lines)
    
    if not sequence:
        # Handle empty input case gracefully
        return

    L = len(sequence)

    # --- 1-mer Frequencies ---
    # Use Counter on the string itself for efficiency
    one_mers = Counter(sequence)
    
    # Prepare 1-mer output: sort by count (desc), then key (asc)
    # Items are (key, count)
    sorted_1mers = sorted(one_mers.items(), key=lambda item: (-item[1], item[0]))

    # --- 2-mer Frequencies ---
    # Generate all 2-mers using a generator expression for memory efficiency
    two_mers = (sequence[i:i+2] for i in range(L - 1))
    two_mers_counter = Counter(two_mers)

    # Prepare 2-mer output: sort by count (desc), then key (asc)
    sorted_2mers = sorted(two_mers_counter.items(), key=lambda item: (-item[1], item[0]))

    # --- Specific K-mer Counts ---
    target_kmers = [
        "GGT",
        "GGTA",
        "GGTATT",
        "GGTATTTTAATT",
        "GGTATTTTAATTTATAGT"
    ]
    
    target_counts = {}
    
    for kmer in target_kmers:
        count = 0
        k_len = len(kmer)
        if k_len > L:
            target_counts[kmer] = 0
            continue
            
        # Count occurrences of the specific kmer
        # This is generally faster than repeated slicing/comparison in a loop
        # for fixed, short patterns, but we stick to explicit iteration 
        # to guarantee correctness across all Python versions/implementations
        for i in range(L - k_len + 1):
            if sequence[i:i+k_len] == kmer:
                count += 1
        target_counts[kmer] = count

    # --- Output Generation ---

    # 1. 1-mer frequencies
    for kmer, count in sorted_1mers:
        print(f"{kmer} {count}")

    # 2. 2-mer frequencies
    for kmer, count in sorted_2mers:
        print(f"{kmer} {count}")

    # 3. Specific K-mer counts
    for kmer in target_kmers:
        count = target_counts[kmer]
        # Output format: <count>\t<kmer>
        print(f"{count}\t{kmer}")

if __name__ == "__main__":
    solve()
