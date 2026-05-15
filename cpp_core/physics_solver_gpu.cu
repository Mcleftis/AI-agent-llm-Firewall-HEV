#include <cuda_runtime.h>
#include <iostream>

// 1. Ο CUDA Kernel που τρέχει στην Κάρτα Γραφικών (Monte Carlo)
__global__ void monte_carlo_kernel(float* results, int iterations) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < iterations) {
        // ΕΔΩ ΜΠΑΙΝΕΙ Η MONTE CARLO ΛΟΓΙΚΗ ΣΟΥ
        // Προς το παρόν βάζουμε μια dummy τιμή
        results[idx] = 42.0f; 
    }
}

// 2. Το C-ABI Interface για να μιλάει με την Python (όπως το παλιό σου C++)
extern "C" __declspec(dllexport) void run_monte_carlo(float* host_results, int iterations) {
    float* device_results;
    
    // Α. Δέσμευση VRAM
    cudaError_t err = cudaMalloc((void**)&device_results, iterations * sizeof(float));
    if (err != cudaSuccess) {
        std::cerr << "CUDA Malloc Failed!" << std::endl;
        return;
    }

    // Β. Υπολογισμός Blocks & Threads (256 threads ανά SM)
    int threads_per_block = 256;
    int blocks = (iterations + threads_per_block - 1) / threads_per_block;

    // Γ. Εκτέλεση στην GPU
    monte_carlo_kernel<<<blocks, threads_per_block>>>(device_results, iterations);
    cudaDeviceSynchronize(); // Περιμένουμε να τελειώσει η GPU

    // Δ. Μεταφορά αποτελεσμάτων πίσω στη RAM (για την Python)
    cudaMemcpy(host_results, device_results, iterations * sizeof(float), cudaMemcpyDeviceToHost);

    // Ε. Καθαρισμός VRAM
    cudaFree(device_results);
}
