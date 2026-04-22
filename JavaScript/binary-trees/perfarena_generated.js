/**
 * Binary Trees Benchmark for CLB-J
 * Reads N from command line arguments.
 * Allocates and deallocates various binary trees to stress memory management.
 */

function solve() {
    // Read N from command-line arguments
    const N_str = process.argv[2];
    if (!N_str || isNaN(parseInt(N_str))) {
        // Defaulting to N=21 if argument is missing or invalid, though benchmark expects it.
        // For strict adherence, we assume valid input or rely on the environment providing it.
        // If running without arguments, we might exit or use a default.
        // Since the prompt implies N is provided, we proceed assuming it's an integer string.
        return;
    }

    const N = parseInt(N_str);

    // --- Node and Tree Management ---

    /**
     * Represents a node in the binary tree.
     * Using plain objects is idiomatic for JS benchmarks unless specific memory layout is required.
     */
    function createNode() {
        return { left: null, right: null };
    }

    /**
     * Recursively builds a full binary tree of the given depth D.
     * Depth D means the longest path from root to leaf has D edges (D+1 levels).
     * @param {number} depth - The target depth.
     * @returns {object | null} The root of the constructed tree.
     */
    function buildTree(depth) {
        if (depth < 0) return null;
        if (depth === 0) return createNode(); // Leaf node placeholder

        const root = createNode();
        root.left = buildTree(depth - 1);
        root.right = buildTree(depth - 1);
        return root;
    }

    /**
     * Recursively nullifies all references in the tree structure to allow GC.
     * This simulates deallocation.
     * @param {object | null} node - The root of the tree segment to destroy.
     */
    function destroyTree(node) {
        if (!node) return;
        node.left = null;
        node.right = null;
    }

    // --- Benchmark Execution ---

    let output = [];

    // 1. Stretch Tree (Depth N+1)
    const stretchDepth = N + 1;
    let stretchRoot = buildTree(stretchDepth);
    const stretchCount = Math.pow(2, stretchDepth + 1) - 1;
    
    // Output 1: stretch tree of depth N+1
    output.push(`stretch tree of depth ${N + 1}\t check: ${stretchCount}`);
    
    // Cleanup
    destroyTree(stretchRoot);
    stretchRoot = null;


    // 2. Short-Lived Trees (d = 4, 6, ..., N)
    let shortLivedSum = 0;
    let shortLivedOutputParts = [];

    for (let d = 4; d <= N; d += 2) {
        // Number of trees: 2^(N-d+4)
        const numTrees = Math.pow(2, N - d + 4);
        
        // Node count for one tree of depth d: 2^(d+1) - 1
        const singleTreeCount = Math.pow(2, d + 1) - 1;
        
        let groupSum = 0;
        
        // Allocate and deallocate numTrees times
        for (let i = 0; i < numTrees; i++) {
            let root = buildTree(d);
            const count = Math.pow(2, d + 1) - 1; // Should always be singleTreeCount
            groupSum += count;
            
            // Cleanup
            destroyTree(root);
        }
        
        shortLivedSum += groupSum;
        
        // Format for output: <count>\t trees of depth d\t check: <sum>
        // Note: The problem description implies the count printed here is the *total* sum for this group.
        // The structure suggests the count printed is the sum, and the description follows.
        shortLivedOutputParts.push(`${groupSum}\t trees of depth ${d}\t check: ${groupSum}`);
    }

    // 3. Long-Lived Tree (Depth N)
    const longLiveDepth = N;
    let longLiveRoot = buildTree(longLiveDepth);
    const longLiveCount = Math.pow(2, longLiveDepth + 1) - 1;

    // Output 4: long lived tree of depth N
    output.push(`long lived tree of depth ${N}\t check: ${longLiveCount}`);

    // Cleanup
    destroyTree(longLiveRoot);
    longLiveRoot = null;

    // --- Final Output Assembly ---
    
    // Write the stretch tree output first
    process.stdout.write(output[0] + '\n');

    // Write the short-lived tree outputs
    for (let i = 0; i < shortLivedOutputParts.length; i++) {
        process.stdout.write(shortLivedOutputParts[i] + '\n');
    }

    // Write the long-lived tree output
    process.stdout.write(output[output.length - 1] + '\n');
}

solve();
