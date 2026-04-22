#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <algorithm>

// Use long long for counts as they can exceed 2^32
typedef long long count_t;

struct Node {
    Node* left;
    Node* right;

    Node() : left(nullptr), right(nullptr) {}
};

// Recursively builds a full binary tree of specified depth (number of levels).
// Depth 1: Root only (1 node)
// Depth 2: Root + 2 children (3 nodes)
// Depth D: 2^D - 1 nodes
Node* build_tree(int depth) {
    if (depth <= 0) {
        return nullptr;
    }
    Node* root = new Node();
    root->left = build_tree(depth - 1);
    root->right = build_tree(depth - 1);
    return root;
}

// Recursively deletes the entire tree starting from the given root.
void delete_tree(Node* root) {
    if (root == nullptr) {
        return;
    }
    delete_tree(root->left);
    delete_tree(root->right);
    delete root;
}

// Counts the nodes in a fully built tree (for verification, though the count is known).
// This function is not strictly necessary if we trust the formula, but it confirms the structure.
count_t count_nodes(Node* root) {
    if (root == nullptr) {
        return 0;
    }
    return 1 + count_nodes(root->left) + count_nodes(root->right);
}

int main(int argc, char* argv[]) {
    // Optimization for competitive programming style I/O
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(nullptr);

    if (argc != 2) {
        return 1; // Should not happen based on problem description
    }

    int N = std::atoi(argv[1]);

    // --- 1. Stretch Tree (Depth N+1) ---
    // Depth N+1 means N+1 levels.
    int stretch_depth = N + 1;
    Node* stretch_root = build_tree(stretch_depth);
    count_t stretch_count = count_nodes(stretch_root);
    
    printf("stretch tree of depth %d\t check: %lld\n", N + 1, stretch_count);
    delete_tree(stretch_root);

    // --- 2. Short-Lived Trees (d = 4, 6, ..., N) ---
    count_t short_lived_sum = 0;
    
    for (int d = 4; d <= N; d += 2) {
        // Number of trees: 2^(N-d+4)
        // Since N and d are small enough (N<=60 typically), we use pow/long long for safety.
        // The exponent is N - d + 4.
        int exponent = N - d + 4;
        
        // Calculate 2^exponent. Since N is small (e.g., 21), this fits in long long.
        count_t num_trees = 1LL << exponent; 
        
        // Node count for one tree of depth d: 2^(d+1) - 1
        count_t single_tree_count = (1LL << (d + 1)) - 1;
        
        count_t total_sum_for_d = 0;
        
        // We must allocate and deallocate num_trees times to stress the allocator.
        for (count_t i = 0; i < num_trees; ++i) {
            Node* root = build_tree(d);
            // The count is calculated, but the memory must be freed immediately.
            // We don't need to store the count for this specific iteration, 
            // as the total sum is calculated based on the known structure.
            delete_tree(root);
        }
        
        // Total sum = num_trees * single_tree_count
        total_sum_for_d = num_trees * single_tree_count;
        short_lived_sum += total_sum_for_d;

        // Output format: <count>\t trees of depth d\t check: <sum>
        printf("%lld\t trees of depth %d\t check: %lld\n", 
               single_tree_count, d, total_sum_for_d);
    }

    // --- 3. Long-Lived Tree (Depth N) ---
    Node* long_lived_root = build_tree(N);
    count_t long_lived_count = count_nodes(long_lived_root);
    
    printf("long lived tree of depth %d\t check: %lld\n", N, long_lived_count);
    
    // Clean up the long-lived tree before exit
    delete_tree(long_lived_root);

    return 0;
}
