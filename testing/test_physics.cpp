#include <iostream>
#include <cmath>
#include <chrono>

extern "C" {
    struct VehicleState {
        float speed_ms;
        float mass;
        float air_drag_coeff;
        float slope_deg;
        float soc;
        float temperature;
    };

    float calculate_acceleration(float throttle, VehicleState* v);
    void solve_battery_thermal_dynamics(float current_amps, float dt, VehicleState* v);
    float run_monte_carlo_safety_check(float current_speed_ms, float throttle, int num_simulations);
}

#define EXPECT_TRUE(condition, test_name) \
    if (!(condition)) { \
        std::cerr << "  [FAIL] " << test_name << std::endl; \
        test_passed = false; \
    } else { \
        std::cout << "  [PASS] " << test_name << std::endl; \
    }

// ---------------------------------------------------------
bool test_calculate_acceleration() {
    std::cout << "\n--- Logic Test: Acceleration ---" << std::endl;
    bool test_passed = true;

    VehicleState v1 = {0.0f, 1600.0f, 0.3f, 0.0f, 80.0f, 25.0f};
    float acc1 = calculate_acceleration(1.0f, &v1);
    EXPECT_TRUE(acc1 > 0.0f, "Max throttle gives positive acceleration");

    VehicleState v2 = {30.0f, 1600.0f, 0.3f, 0.0f, 80.0f, 25.0f};
    float acc2 = calculate_acceleration(0.0f, &v2);
    EXPECT_TRUE(acc2 < 0.0f, "Aerodynamic drag causes deceleration");

    return test_passed;
}

// ---------------------------------------------------------
bool test_edge_cases() {
    std::cout << "\n--- Reliability Test: Edge Cases ---" << std::endl;
    bool test_passed = true;

    // Σενάριο 1: Διαίρεση με το μηδέν (Zero Mass)
    // Ελέγχουμε ότι η συνάρτηση δεν κάνει crash — το inf είναι η αναμενόμενη C++ συμπεριφορά
    VehicleState v_zero_mass = {0.0f, 0.0f, 0.3f, 0.0f, 80.0f, 25.0f};
    float acc_zero = calculate_acceleration(1.0f, &v_zero_mass);
    EXPECT_TRUE(std::isinf(acc_zero), "Zero mass: does not crash, returns Infinity as expected");

    // Σενάριο 2: Εξωφρενική Ταχύτητα (1000 m/s ~ Mach 3)
    VehicleState v_fast = {1000.0f, 1600.0f, 0.3f, 0.0f, 80.0f, 25.0f};
    float acc_fast = calculate_acceleration(0.0f, &v_fast);
    EXPECT_TRUE(acc_fast < -90.0f, "Extreme drag at Mach 3 handled correctly (~-93.75 m/s^2)");

    return test_passed;
}

// ---------------------------------------------------------
bool test_performance_benchmarks() {
    std::cout << "\n--- Performance Benchmark: Speed ---" << std::endl;
    bool test_passed = true;

    VehicleState v_perf = {30.0f, 1600.0f, 0.3f, 0.0f, 80.0f, 25.0f};

    // volatile: αποτρέπει τον compiler να κάνει optimize out το loop σε release mode
    volatile float result = 0.0f;

    auto start_time = std::chrono::high_resolution_clock::now();

    const int iterations = 100000;
    for (int i = 0; i < iterations; i++) {
        result = calculate_acceleration(1.0f, &v_perf);
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);

    float avg_time_us = (float)duration.count() / iterations;

    std::cout << "    Avg execution time: " << avg_time_us << " microseconds" << std::endl;
    EXPECT_TRUE(avg_time_us < 1.0f, "Execution time is under 1 microsecond");

    return test_passed;
}

// ---------------------------------------------------------
int main() {
    std::cout << "================================================" << std::endl;
    std::cout << "NATIVE C++ PHYSICS ENGINE UNIT TESTS STARTING" << std::endl;
    std::cout << "================================================" << std::endl;

    int passed = 0;
    int failed = 0;

    if (test_calculate_acceleration()) passed++; else failed++;
    if (test_edge_cases())             passed++; else failed++;
    if (test_performance_benchmarks()) passed++; else failed++;

    std::cout << "\n================================================" << std::endl;
    if (failed == 0) {
        std::cout << "ALL TESTS PASSED (" << passed << "/" << passed + failed << ")" << std::endl;
    } else {
        std::cout << "TESTS FAILED! (" << failed << " failed, " << passed << " passed)" << std::endl;
    }
    std::cout << "================================================" << std::endl;

    return failed == 0 ? 0 : 1;
}