```javascript
/**
 * k-nucleotide benchmark implementation.
 * Reads a FASTA sequence from stdin, calculates 1-mer and 2-mer frequencies,
 * and counts specific k-mers.
 */

function solve() {
    let input = '';
    
    // Read all input from stdin
    process.stdin.on('data', (chunk) => {
        input += chunk;
    });

    process.stdin.on('end', () => {
        // 1. Preprocessing: Extract and normalize the sequence
        // Remove headers (lines starting with '>') and non-ACGT characters, then uppercase.
        let sequence = input.toUpperCase().replace(/[^ACGT]/g, '');

        if (sequence.length === 0) {
            // Handle empty input gracefully
            process.stdout.write("");
            return;
        }

        // --- 2. Counting ---

        // 1-mer Frequencies
        const oneMerCounts = { 'A': 0, 'C': 0, 'G': 0, 'T': 0 };
        
        // 2-mer Frequencies
        const twoMerCounts = {};
        const twoMerKeys = ['AA', 'AC', 'AG', 'AT', 'CA', 'CC', 'CG', 'CT', 'GA', 'GC', 'GG', 'GT', 'TA', 'TC', 'TG', 'TT'];
        const twoMerMap = {}; // Use a map/object for O(1) access

        for (let i = 0; i < sequence.length; i++) {
            const base = sequence[i];
            
            // 1-mer count
            if (oneMerCounts.hasOwnProperty(base)) {
                oneMerCounts[base]++;
            }

            // 2-mer count (if possible)
            if (i < sequence.length - 1) {
                const twoMer = sequence.substring(i, i + 2);
                twoMerCounts[twoMer] = (twoMerCounts[twoMer] || 0) + 1;
            }
        }

        // Specific Fragment Counts
        const specificFragments = [
            { name: 'GGT', count: 0 },
            { name: 'GGTA', count: 0 },
            { name: 'GGTATT', count: 0 },
            { name: 'GGTATTTTAATT', count: 0 },
            { name: 'GGTATTTTAATTTATAGT', count: 0 }
        ];

        for (const frag of specificFragments) {
            let count = 0;
            let start = 0;
            while ((start = sequence.indexOf(frag.name, start)) !== -1) {
                count++;
                start += 1; // Move past the start of the found match to find overlaps
            }
            frag.count = count;
        }

        // --- 3. Output Generation ---
        let output = '';

        // Helper function to sort and format frequencies
        const formatFrequencies = (counts) => {
            // Convert to array of { key, count } objects
            const entries = Object.entries(counts).map(([key, count]) => ({ key, count }));
            
            // Sort: 1. Descending count. 2. Alphabetical key (for stable tie-breaking).
            entries.sort((a, b) => {
                if (b.count !== a.count) {
                    return b.count - a.count;
                }
                return a.key.localeCompare(b.key);
            });

            return entries.map(item => `${item.key} ${item.count}`).join('\n');
        };

        // 1-mer Output
        output += formatFrequencies(oneMerCounts) + '\n';

        // 2-mer Output
        // We must ensure all 16 possible 2-mers are considered, even if they didn't appear, 
        // to match the expected structure if the reference requires it. 
        // However, based on the prompt, we only report what was found, sorted by count.
        // We will use the calculated twoMerCounts.
        output += formatFrequencies(twoMerCounts) + '\n';

        // Specific Fragment Output
        for (const frag of specificFragments) {
            output += `${frag.count}\t${frag.name}\n`;
        }

        // Write all output at once for efficiency
        process.stdout.write(output);
    });
}

solve();
```