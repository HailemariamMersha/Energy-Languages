/**
 * k-nucleotide benchmark implementation.
 * Reads a FASTA sequence from stdin, calculates 1-mer and 2-mer frequencies,
 * and counts specific target fragments.
 */

function solve() {
    // Read all input synchronously from standard input, as is common in benchmarks.
    let input;
    try {
        const fs = require('fs');
        input = fs.readFileSync(0, 'utf8'); // File descriptor 0 is stdin
    } catch (e) {
        // Handle case where stdin might not be available in certain testing environments
        return;
    }

    // 1. Extract and Normalize Sequence
    let sequence = '';
    const lines = input.split('\n');
    for (const line of lines) {
        const trimmedLine = line.trim();
        if (trimmedLine.length > 0 && !trimmedLine.startsWith('>')) {
            // Normalize to uppercase and filter out non-ACGT characters
            let cleanLine = '';
            for (let i = 0; i < trimmedLine.length; i++) {
                const char = trimmedLine[i].toUpperCase();
                if ('ACGT'.includes(char)) {
                    cleanLine += char;
                }
            }
            sequence += cleanLine;
        }
    }

    const L = sequence.length;
    if (L === 0) {
        return;
    }

    // --- 1-mer Frequency Counting ---
    const oneMerCounts = { 'A': 0, 'C': 0, 'G': 0, 'T': 0 };
    for (let i = 0; i < L; i++) {
        const base = sequence[i];
        if (oneMerCounts.hasOwnProperty(base)) {
            oneMerCounts[base]++;
        }
    }

    // --- 2-mer Frequency Counting ---
    const twoMerCounts = {};
    for (let i = 0; i < L - 1; i++) {
        const mer = sequence.substring(i, i + 2);
        twoMerCounts[mer] = (twoMerCounts[mer] || 0) + 1;
    }

    // --- Specific Fragment Counting ---
    const targetFragments = [
        { name: 'GGT', count: 0 },
        { name: 'GGTA', count: 0 },
        { name: 'GGTATT', count: 0 },
        { name: 'GGTATTTTAATT', count: 0 },
        { name: 'GGTATTTTAATTTATAGT', count: 0 }
    ];

    for (const target of targetFragments) {
        const pattern = target.name;
        let count = 0;
        let startIndex = 0;
        while ((startIndex = sequence.indexOf(pattern, startIndex)) !== -1) {
            count++;
            startIndex += 1; // Move past the start of the found pattern to find overlaps
        }
        target.count = count;
    }

    // --- Output Generation ---

    // 1. 1-mer frequencies (Sorted by descending count)
    const oneMerEntries = Object.entries(oneMerCounts)
        .map(([mer, count]) => ({ mer, count }))
        .sort((a, b) => b.count - a.count);

    for (const entry of oneMerEntries) {
        process.stdout.write(`${entry.mer} ${entry.count}\n`);
    }

    // 2. 2-mer frequencies (Sorted by descending count)
    const twoMerEntries = Object.entries(twoMerCounts)
        .map(([mer, count]) => ({ mer, count }))
        .sort((a, b) => b.count - a.count);

    for (const entry of twoMerEntries) {
        process.stdout.write(`${entry.mer} ${entry.count}\n`);
    }

    // 3. Specific fragment counts
    for (const target of targetFragments) {
        process.stdout.write(`${target.count}\t${target.name}\n`);
    }
}

solve();
