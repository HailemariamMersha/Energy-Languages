```cpp
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>
#include <cstdio>
#include <map>

// Helper function to map DNA char to index (A=0, C=1, G=2, T=3)
// Returns -1 if invalid.
inline int char_to_index(char c) {
    switch (std::toupper(static_cast<unsigned char>(c))) {
        case 'A': return 0;
        case 'C': return 1;
        case 'G': return 2;
        case 'T': return 3;
        default: return -1;
    }
}

// Structure to hold frequency data for sorting
struct Frequency {
    int count;
    std::string key;

    // Comparator for sorting: descending count, then lexicographically ascending key (for stable output)
    bool operator>(const Frequency& other) const {
        if (count != other.count) {
            return count > other.count;
        }
        return key < other.key;
    }
};

void solve() {
    // Fast I/O setup
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string sequence_buffer;
    std::string line;

    // 1. Read and build the sequence string from stdin (FASTA format)
    while (std::getline(std::cin, line)) {
        if (line.empty() || line[0] == '>') {
            continue; // Skip headers and empty lines
        }
        for (char c : line) {
            char upper_c = std::toupper(static_cast<unsigned char>(c));
            if (upper_c == 'A' || upper_c == 'C' || upper_c == 'G' || upper_c == 'T') {
                sequence_buffer += upper_c;
            }
        }
    }

    const std::string& S = sequence_buffer;
    size_t L = S.length();

    if (L == 0) {
        // Handle empty input case gracefully (minimal output required)
        // Since the problem implies specific output formats, we output nothing if L=0
        return;
    }

    // --- 2. Initialize Counters ---

    // 1-mer counts: A, C, G, T
    int counts_1[4] = {0};

    // 2-mer counts: 4*4 = 16 possible pairs. Index = 4*idx(P1) + idx(P2)
    int counts_2[16] = {0};

    // Target fragment counts
    const std::vector<std::string> targets = {
        "GGT",
        "GGTA",
        "GGTATT",
        "GGTATTTTAATT",
        "GGTATTTTAATTTATAGT"
    };
    std::vector<int> target_counts(targets.size(), 0);

    // --- 3. Single Pass Processing ---

    for (size_t i = 0; i < L; ++i) {
        char current_char = S[i];
        int idx = char_to_index(current_char);

        // 1-mer counting
        if (idx != -1) {
            counts_1[idx]++;
        }

        // 2-mer counting
        if (i + 1 < L) {
            char next_char = S[i+1];
            int next_idx = char_to_index(next_char);

            if (idx != -1 && next_idx != -1) {
                int two_mer_index = 4 * idx + next_idx;
                counts_2[two_mer_index]++;
            }
        }

        // Target fragment counting (Sliding Window)
        for (size_t t = 0; t < targets.size(); ++t) {
            const std::string& target = targets[t];
            size_t target_len = target.length();

            if (i + target_len <= L) {
                // Check substring starting at i
                if (S.substr(i, target_len) == target) {
                    target_counts[t]++;
                }
            }
        }
    }

    // --- 4. Output 1-mer Frequencies ---
    std::vector<Frequency> freqs_1;
    const char bases[] = {'A', 'C', 'G', 'T'};
    for (int i = 0; i < 4; ++i) {
        if (counts_1[i] > 0) {
            freqs_1.push_back({counts_1[i], std::string(1, bases[i])});
        }
    }

    std::sort(freqs_1.begin(), freqs_1.end(), std::greater<Frequency>());

    for (const auto& freq : freqs_1) {
        printf("%d\n", freq.count);
    }

    // --- 5. Output 2-mer Frequencies ---
    std::vector<Frequency> freqs_2;
    for (int i = 0; i < 16; ++i) {
        if (counts_2[i] > 0) {
            // Decode index i back to 2-mer string
            int idx1 = i / 4;
            int idx2 = i % 4;
            char p1 = bases[idx1];
            char p2 = bases[idx2];
            std::string key = "";
            key += p1;
            key += p2;
            freqs_2.push_back({counts_2[i], key});
        }
    }

    std::sort(freqs_2.begin(), freqs_2.end(), std::greater<Frequency>());

    for (const auto& freq : freqs_2) {
        printf("%d\n", freq.count);
    }

    // --- 6. Output Target Fragment Counts ---
    for (size_t i = 0; i < targets.size(); ++i) {
        printf("%d\t%s\n", target_counts[i], targets[i].c_str());
    }
}

int main() {
    solve();
    return 0;
}
```