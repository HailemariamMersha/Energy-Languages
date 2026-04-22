/**
 * Spectral Norm Benchmark Implementation
 * Estimates the spectral norm of matrix A using the power method.
 * A[i][j] = 2 / ((i+j) * (3i + j + 3))
 * Matrix size M is fixed at 1000, as required by the benchmark context.
 */

function solve() {
    // Read N from command-line arguments
    const N = parseInt(process.argv[2]);

    if (isNaN(N) || N <= 0) {
        // Defaulting to the reference value if input is invalid, though the prompt implies valid input.
        // For robustness, we handle the case, but the benchmark expects N > 0.
        process.exit(1);
    }

    // Fixed matrix size M based on benchmark context
    const M = 1000;

    // --- Matrix A Construction ---
    // Store A in row-major order: A[i*M + j] = A[i][j]
    const A = new Float64Array(M * M);

    for (let i = 0; i < M; i++) {
        for (let j = 0; j < M; j++) {
            const sum_ij = i + j;
            // Denominator: (i+j) * (3i + j + 3)
            const denominator = sum_ij * (3.0 * i + j + 3.0);
            
            // A[i][j] = 2 / denominator
            A[i * M + j] = 2.0 / denominator;
        }
    }

    // --- Vector Initialization ---
    // v_k: current vector (unit vector)
    const v = new Float64Array(M);
    // w_k: result of A * v_{k-1}
    const w = new Float64Array(M);
    // v_new: result of A^T * w_k
    const v_new = new Float64Array(M);

    // Initialize v to a unit vector (1/sqrt(M))
    const invSqrtM = 1.0 / Math.sqrt(M);
    for (let i = 0; i < M; i++) {
        v[i] = invSqrtM;
    }

    let currentEstimate = 0.0;

    // --- Power Iteration Loop ---
    for (let k = 0; k < N; k++) {
        // 1. Calculate w = A * v (w[i] = sum_j A[i][j] * v[j])
        for (let i = 0; i < M; i++) {
            let sum = 0.0;
            for (let j = 0; j < M; j++) {
                // A[i][j] is stored at index i*M + j
                sum += A[i * M + j] * v[j];
            }
            w[i] = sum;
        }

        // 2. Calculate v_new = A^T * w (v_new[j] = sum_i A[i][j] * w[i])
        // Note: A^T[j][i] = A[i][j]
        for (let j = 0; j < M; j++) {
            let sum = 0.0;
            for (let i = 0; i < M; i++) {
                // A[i][j] is stored at index i*M + j
                sum += A[i * M + j] * w[i];
            }
            v_new[j] = sum;
        }

        // 3. Normalize v_new to get v_k
        let normSq = 0.0;
        for (let i = 0; i < M; i++) {
            normSq += v_new[i] * v_new[i];
        }
        const norm = Math.sqrt(normSq);

        // Update v for the next iteration
        for (let i = 0; i < M; i++) {
            v[i] = v_new[i] / norm;
        }

        // The estimate for the spectral norm is the norm calculated in this step.
        currentEstimate = norm;
    }

    // Output the final estimate formatted to nine decimal places.
    process.stdout.write(currentEstimate.toFixed(9) + '\n');
}

solve();
