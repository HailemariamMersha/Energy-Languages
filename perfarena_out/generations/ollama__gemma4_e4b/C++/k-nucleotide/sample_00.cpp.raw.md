```cpp
#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <cstdio>
#include <utility>
#include <cctype>

using namespace std;

// Helper function to convert char to uppercase and check if it's a valid DNA base
char to_upper_dna(char c) {
    if (c >= 'a' && c <= 'z') {
        c = toupper(c);
    }
    if (c == 'A' || c == 'C' || c == 'G' || c == 'T') {
        return c;
    }
    return '\0'; // Invalid character marker
}

// Comparator for sorting pairs by count (first element) in descending order
struct CompareCount {
    bool operator()(const pair<int, string>& a, const pair<int, string>& b) const {
        if (a.first != b.first) {
            return a.first > b.first; // Descending count
        }
        // Tie-breaker: sort by key lexicographically (optional, but good practice)
        return a.second < b.second;
    }
};

void solve() {
    // Fast I/O setup
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    string sequence_buffer;
    string line;

    // 1. Read and Concatenate Sequence
    while (getline(cin, line)) {
        if (line.empty() || line[0] == '>') {
            continue; // Skip empty lines or FASTA headers
        }
        for (char c : line) {
            char upper_c = to_upper_dna(c);
            if (upper_c != '\0') {
                sequence_buffer += upper_c;
            }
        }
    }

    const string& S = sequence_buffer;
    size_t L = S.length();

    if (L == 0) {
        // If no sequence is read, print nothing and exit.
        return;
    }

    // --- 1-mer Frequencies ---
    map<char, int> one_mer_counts;
    for (char c : S) {
        one_mer_counts[c]++;
    }

    // Prepare for sorted output
    vector<pair<int, string>> one_mer_results;
    for (const auto& pair : one_mer_counts) {
        one_mer_results.push_back({pair.second, string(1, pair.first)});
    }
    sort(one_mer_results.begin(), one_mer_results.end(), [](const auto& a, const auto& b) {
        return a.first > b.first;
    });

    // Output 1-mer frequencies
    for (const auto& pair : one_mer_results) {
        printf("%d\n", pair.first);
    }

    // --- 2-mer Frequencies ---
    map<string, int> two_mer_counts;
    for (size_t i = 0; i < L - 1; ++i) {
        string two_mer = S.substr(i, 2);
        two_mer_counts[two_mer]++;
    }

    // Prepare for sorted output
    vector<pair<int, string>> two_mer_results;
    for (const auto& pair : two_mer_counts) {
        two_mer_results.push_back({pair.second, pair.first});
    }
    sort(two_mer_results.begin(), two_mer_results.end(), [](const auto& a, const auto& b) {
        return a.first > b.first;
    });

    // Output 2-mer frequencies
    for (const auto& pair : two_mer_results) {
        printf("%d\n", pair.first);
    }

    // --- Specific K-mer Counts ---
    const vector<string> target_kmers = {
        "GGT",
        "GGTA",
        "GGTATT",
        "GGTATTTTAATT",
        "GGTATTTTAATTTATAGT"
    };

    vector<int> specific_counts(target_kmers.size(), 0);

    for (size_t k = 0; k < target_kmers.size(); ++k) {
        const string& target = target_kmers[k];
        size_t target_len = target.length();
        int count = 0;

        if (L >= target_len) {
            for (size_t i = 0; i <= L - target_len; ++i) {
                // Check substring equality efficiently
                if (S.compare(i, target_len, target) == 0) {
                    count++;
                }
            }
        }
        specific_counts[k] = count;
    }

    // Output specific k-mer counts
    for (size_t k = 0; k < target_kmers.size(); ++k) {
        printf("%d\t%s\n", specific_counts[k], target_kmers[k].c_str());
    }
}

int main() {
    solve();
    return 0;
}
```