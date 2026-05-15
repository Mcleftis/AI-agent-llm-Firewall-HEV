#include <cmath>
#include <random> 
#include <omp.h>  

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT
#endif

// ========================================================================
// ΣΤΑΘΕΡΕΣ ΦΥΣΙΚΗΣ & ΟΧΗΜΑΤΟΣ (ΟΧΙ ΠΙΑ MAGIC NUMBERS)
// ========================================================================
const float MAX_POWER_W = 200000.0f;          // 200 kW κινητήρας
const float GRAVITY_MS2 = 9.81f;              // Επιτάχυνση Βαρύτητας
const float PI_VAL = 3.14159265f;             // Π

const float BATT_INTERNAL_RESISTANCE = 0.05f; // Εσωτερική αντίσταση (Ohms)
const float BATT_HEAT_CAPACITY = 500.0f;      // Θερμοχωρητικότητα 
const float AMBIENT_TEMP_C = 25.0f;           // Εξωτερική θερμοκρασία (Celsius)
const float BATT_COOLING_RATE = 0.1f;         // Ρυθμός ψύξης
const float BATT_CAPACITY_AH = 50.0f;         // Χωρητικότητα Μπαταρίας (Ah)
const float SECONDS_PER_HOUR = 3600.0f;       // Για μετατροπές χρόνου

const float DEFAULT_VEHICLE_MASS = 1600.0f;   // Βάρος οχήματος (kg)
const float DEFAULT_SOC = 80.0f;              // Αρχικό State of Charge (%)
const float MAX_SAFE_SPEED_MS = 50.0f;        // Όριο ταχύτητας για το Monte Carlo

extern "C" {
    
    struct VehicleState {
        float speed_ms;
        float mass;
        float air_drag_coeff;
        float slope_deg;
        float soc;
        float temperature;
    };

    DLL_EXPORT float calculate_acceleration(float throttle, VehicleState* v) { 
        // [DEFENSIVE PROGRAMMING 1]: Αποφυγή διαίρεσης με το μηδέν (SIGFPE/Infinity)
        if (v->mass < 1.0f) {
            v->mass = 1.0f; // Αναγκαστικό clamp στο 1 κιλό για ασφάλεια στα μαθηματικά
        }

        float force_propulsion = (throttle * MAX_POWER_W) / (v->speed_ms + 1.0f);
        float force_gravity = v->mass * GRAVITY_MS2 * sin(v->slope_deg * PI_VAL / 180.0f);
        float force_drag = 0.5f * v->air_drag_coeff * (v->speed_ms * v->speed_ms);
        
        float net_force = force_propulsion - (force_gravity + force_drag);
        return net_force / v->mass;
    }

    DLL_EXPORT void solve_battery_thermal_dynamics(float current_amps, float dt, VehicleState* v) {
        float heat_generated = (current_amps * current_amps) * BATT_INTERNAL_RESISTANCE;
        float heat_dissipated = BATT_COOLING_RATE * (v->temperature - AMBIENT_TEMP_C);
        float delta_temp = ((heat_generated - heat_dissipated) / BATT_HEAT_CAPACITY) * dt;
        
        v->temperature += delta_temp;
        v->soc -= ((current_amps * (dt / SECONDS_PER_HOUR)) / BATT_CAPACITY_AH) * 100.0f;
    }

    DLL_EXPORT float run_monte_carlo_safety_check(float current_speed_ms, float throttle, int num_simulations) {
        // [DEFENSIVE PROGRAMMING 2]: Προστασία από CPU DoS (Denial of Service)
        if (num_simulations <= 0) return 0.0f;
        if (num_simulations > 10000) num_simulations = 10000; // Hard Limit!

        int danger_count = 0;

        #pragma omp parallel for reduction(+:danger_count)
        for (int i = 0; i < num_simulations; ++i) {
            std::mt19937 rng(1337 + i); 
            std::uniform_real_distribution<float> noise_dist(-0.2f, 0.2f); 

            float sim_speed = current_speed_ms;
            float dt = 0.1f;
            
            // Φτιάχνουμε το Avatar χρησιμοποιώντας τις Σταθερές
            VehicleState v_sim;
            v_sim.mass = DEFAULT_VEHICLE_MASS;
            v_sim.slope_deg = 0.0f;
            v_sim.soc = DEFAULT_SOC;
            v_sim.temperature = AMBIENT_TEMP_C;
            
            for (int step = 0; step < 30; ++step) {
                float random_drag_noise = 1.0f + noise_dist(rng);
                float random_friction_noise = 1.0f + noise_dist(rng);

                v_sim.speed_ms = sim_speed;
                v_sim.air_drag_coeff = 0.3f * random_drag_noise;

                float noisy_throttle = throttle * random_friction_noise;
                if(noisy_throttle > 1.0f) noisy_throttle = 1.0f;
                if(noisy_throttle < 0.0f) noisy_throttle = 0.0f;

                float acceleration = calculate_acceleration(noisy_throttle, &v_sim);
                sim_speed += acceleration * dt;

                // Χρήση της σταθεράς MAX_SAFE_SPEED_MS
                if (sim_speed > MAX_SAFE_SPEED_MS || sim_speed < 0.0f) {
                    danger_count++;
                    break; 
                }
            }
        }
        return (float)danger_count / (float)num_simulations;
    }
}