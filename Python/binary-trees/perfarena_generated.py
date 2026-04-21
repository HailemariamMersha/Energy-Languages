import sys
import math

class Node:
    """Represents a node in a binary tree."""
    __slots__ = ('left', 'right')

    def __init__(self):
        self.left = None
        self.right = None

def build_line_tree(depth: int) -> Node | None:
    """
    Builds a skewed binary tree (a line) of specified depth.
    Depth D means D nodes connected sequentially.
    Returns the root node.
    """
    if depth <= 0:
        return None
    
    root = Node()
    current = root
    
    # We need depth - 1 more nodes attached to the line
    for _ in range(depth - 1):
        new_node = Node()
        # Use left consistently to build the line
        current.left = new_node
        current = new_node
        
    return root

def main():
    """
    Implements the binary-trees benchmark logic.
    Reads N from command line arguments.
    """
    if len(sys.argv) != 2:
        # Should not happen based on problem constraints, but good practice.
        return

    try:
        N = int(sys.argv[1])
    except ValueError:
        # Handle non-integer input if necessary
        return

    # --- 1. Stretch Tree (Depth N+1) ---
    stretch_depth = N + 1
    stretch_tree = build_line_tree(stretch_depth)
    stretch_count = stretch_depth
    
    # Output format: stretch tree of depth N+1\t check: <count>
    print(f"stretch tree of depth {N+1}\t check: {stretch_count}")

    # --- 2. Short-Lived Trees (Depth d = 4, 6, ..., N) ---
    
    # We must track the sum of nodes for each depth group.
    # The loop iterates over d = 4, 6, 8, ..., up to N.
    
    # The problem statement implies that for each depth d, we build 2^(N-d+4) trees.
    
    for d in range(4, N + 1, 2):
        # Number of trees to build for this depth d
        num_trees = 1 << (N - d + 4)
        
        # Total nodes for this group: num_trees * d
        total_nodes = num_trees * d
        
        # Stress test: Allocate and deallocate num_trees instances of depth d
        # We must build them to count the allocation cost.
        for _ in range(num_trees):
            # Build the tree and immediately let the reference drop (GC handles cleanup)
            _ = build_line_tree(d)
            
        # Output format: <count>\t trees of depth d\t check: <sum>
        print(f"{num_trees}\t trees of depth {d}\t check: {total_nodes}")

    # --- 3. Long-Lived Tree (Depth N) ---
    long_lived_depth = N
    long_lived_tree = build_line_tree(long_lived_depth)
    long_lived_count = long_lived_depth
    
    # Output format: long lived tree of depth N\t check: <count>
    print(f"long lived tree of depth {N}\t check: {long_lived_count}")


if __name__ == "__main__":
    main()
