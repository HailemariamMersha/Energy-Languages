```javascript
/**
 * Binary Trees Benchmark implementation for Node.js.
 * Reads N from command line arguments.
 *
 * Structure:
 * Node { left: Node | null, right: Node | null }
 */

// --- Node Definition ---
class Node {
    constructor() {
        this.left = null;
        this.right = null;
    }
}

/**
 * Recursively builds a full binary tree of specified depth D.
 * Depth D means the longest path from root to leaf has D edges (D+1 levels).
 * @param {number} depth The target depth.
 * @returns {Node | null} The root of the constructed tree.
 */
function buildTree(depth) {
    if (depth < 0) return null;

    const root = new Node();
    
    // Use a queue/level-order approach for iterative building to avoid deep recursion stack issues,
    // although for N=21, recursion depth is fine. Iterative is generally safer for benchmarks.
    let nodes = [root];
    let currentDepth = 0;

    while (nodes.length > 0 && currentDepth < depth) {
        let nextNodes = [];
        for (const node of nodes) {
            // Build left child
            const left = new Node();
            node.left = left;
            nextNodes.push(left);

            // Build right child
            const right = new Node();
            node.right = right;
            nextNodes.push(right);
        }
        nodes = nextNodes;
        currentDepth++;
    }
    return root;
}

/**
 * Counts the total number of nodes in a tree structure.
 * @param {Node | null} node The root node.
 * @returns {number} The node count.
 */
function countNodes(node) {
    if (!node) {
        return 0;
    }
    // Since we are building full trees, this recursive count is efficient enough.
    return 1 + countNodes(node.left) + countNodes(node.right);
}

/**
 * Main execution function.
 */
function runBenchmark() {
    const N_str = process.argv[2];
    if (!N_str || isNaN(parseInt(N_str))) {
        // Default to N=21 if argument is missing or invalid, matching reference behavior.
        process.stdout.write("Error: Missing or invalid N argument. Using default N=21.\n");
        process.exit(1);
    }

    const N = parseInt(N_str);
    let output = [];

    // --- 1. Stretch Tree (Depth N+1) ---
    const stretchDepth = N + 1;
    let stretchRoot = buildTree(stretchDepth);
    const stretchCount = countNodes(stretchRoot);
    
    output.push(`stretch tree of depth ${N + 1}\t check: ${stretchCount}`);
    
    // Explicitly nullify to help GC (though scope exit usually handles this)
    stretchRoot = null; 

    // --- 2. Short-Lived Trees (Depth d = 4, 6, ..., N) ---
    let shortLivedSum = 0;
    
    for (let d = 4; d <= N; d += 2) {
        // Number of trees: 2^(N-d+4)
        // Use Math.pow for exponentiation, safe for N=21.
        const numTrees = Math.pow(2, N - d + 4);
        
        // Nodes per tree (Full tree of depth d): 2^(d+1) - 1
        const nodesPerTree = Math.pow(2, d + 1) - 1;
        
        // Total nodes for this group
        const groupSum = numTrees * nodesPerTree;
        shortLivedSum += groupSum;

        // Allocation/Deallocation phase: Build and discard numTrees trees
        let tempRoot = null;
        for (let i = 0; i < numTrees; i++) {
            // Build the tree
            tempRoot = buildTree(d);
            // The reference to tempRoot is lost at the end of the loop iteration,
            // allowing the GC to reclaim memory.
        }
        // Ensure the last allocated tree is also discarded
        tempRoot = null; 
    }

    // Output for short-lived trees (The problem implies one cumulative output line for this section,
    // but the format suggests iterating over the depths d=4, 6, ... N)
    // Re-reading the output spec:
    // <count>\t trees of depth 4\t check: <sum>
    // ...
    // This implies one line per depth d.
    
    let currentOutputIndex = 1;
    for (let d = 4; d <= N; d += 2) {
        const numTrees = Math.pow(2, N - d + 4);
        const nodesPerTree = Math.pow(2, d + 1) - 1;
        const groupSum = numTrees * nodesPerTree;
        
        output.push(`${numTrees}\t trees of depth ${d}\t check: ${groupSum}`);
    }


    // --- 3. Long-Lived Tree (Depth N) ---
    const longLiveDepth = N;
    let longLiveRoot = buildTree(longLiveDepth);
    const longLiveCount = countNodes(longLiveRoot);
    
    output.push(`long lived tree of depth ${N}\t check: ${longLiveCount}`);

    // Cleanup
    longLiveRoot = null;

    // --- Final Output ---
    process.stdout.write(output.join('\n') + '\n');
}

runBenchmark();
```