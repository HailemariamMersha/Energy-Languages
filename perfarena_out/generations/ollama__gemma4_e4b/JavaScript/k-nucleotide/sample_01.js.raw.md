```javascript
/**
 * k-nucleotide benchmark implementation for Node.js.
 * Reads DNA sequence from stdin, calculates 1-mer and 2-mer frequencies,
 * and counts specific k-mers.
 */

function solve() {
    let input = '';
    
    // Read all input from stdin
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => {
        input += chunk;
    });

    process.stdin.on('end', () => {
        // 1. Extract and Normalize Sequence
        let sequence = input.toUpperCase();
        let cleanSequence = '';
        for (let i = 0; i < sequence.length; i++) {
            const char = sequence[i];
            if (char === 'A' || char === 'C' || char === 'G' || char === 'T') {
                cleanSequence += char;
            }
        }
        
        const N = cleanSequence.length;

        if (N === 0) {
            // Handle empty sequence case gracefully
            process.stdout.write("");
            return;
        }

        // --- 1-mer Frequency Counting ---
        const oneMerCounts = { 'A': 0, 'C': 0, 'G': 0, 'T': 0 };
        for (let i = 0; i < N; i++) {
            const base = cleanSequence[i];
            if (oneMerCounts.hasOwnProperty(base)) {
                oneMerCounts[base]++;
            }
        }

        // --- 2-mer Frequency Counting ---
        const twoMerCounts = {};
        for (let i = 0; i < N - 1; i++) {
            const kmer = cleanSequence.substring(i, i + 2);
            twoMerCounts[kmer] = (twoMerCounts[kmer] || 0) + 1;
        }

        // --- Specific Fragment Counting ---
        const targetFragments = [
            { kmer: "GGT", count: 0 },
            { kmer: "GGTA", count: 0 },
            { kmer: "GGTATT", count: 0 },
            { kmer: "GGTATTTTAATT", count: 0 },
            { kmer: "GGTATTTTAATTTATAGT", count: 0 }
        ];

        for (const target of targetFragments) {
            let count = 0;
            const k = target.kmer.length;
            if (N >= k) {
                for (let i = 0; i <= N - k; i++) {
                    // Check substring equality efficiently
                    let match = true;
                    for (let j = 0; j < k; j++) {
                        if (cleanSequence[i + j] !== target.kmer[j]) {
                            match = false;
                            break;
                        }
                    }
                    if (match) {
                        count++;
                    }
                }
            }
            target.count = count;
        }

        // --- Output Generation ---
        let output = [];

        // 1. 1-mer frequencies (Sorted by descending count, then alphabetically)
        const oneMerEntries = Object.entries(oneMerCounts)
            .map(([k, v]) => ({ k, v }))
            .sort((a, b) => {
                if (b.v !== a.v) return b.v - a.v; // Descending count
                return a.k.localeCompare(b.k); // Ascending k (A, C, G, T)
            });

        for (const entry of oneMerEntries) {
            output.push(`${entry.v}\t${entry.k}`);
        }

        // 2. 2-mer frequencies (Sorted by descending count, then alphabetically)
        const twoMerEntries = Object.entries(twoMerCounts)
            .map(([k, v]) => ({ k, v }))
            .sort((a, b) => {
                if (b.v !== a.v) return b.v - a.v; // Descending count
                return a.k.localeCompare(b.k); // Ascending k
            });

        for (const entry of twoMerEntries) {
            output.push(`${entry.v}\t${entry.k}`);
        }

        // 3. Specific fragment counts
        for (const target of targetFragments) {
            output.push(`${target.count}\t${target.kmer}`);
        }

        // Write all output at once for performance
        process.stdout.write(output.join('\n') + '\n');
    });
}

solve();
```