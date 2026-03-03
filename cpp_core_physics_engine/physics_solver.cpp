#include <cmath>
#include <random> // Απαραίτητο για τον τυχαίο θόρυβο του Monte Carlo
#include <omp.h>  // Απαραίτητο για την παραλληλοποίηση (OpenMP)

// Το extern "C" διατηρεί το όνομα της συνάρτησης καθαρό στη μνήμη (C-ABI)
extern "C" {
    
    //acceleration calc
    
    float calculate_acceleration(float throttle, float current_speed_ms, float mass, float air_drag_coeff, float slope_deg) {
        float max_power = 200000.0f; // 200kW
        float gravity = 9.81f;
        float pi = 3.14159265f;

        // Δύναμη Προώθησης
        float force_propulsion = (throttle * max_power) / (current_speed_ms + 1.0f);
        
        // Αντιστάσεις
        float force_gravity = mass * gravity * sin(slope_deg * pi / 180.0f);
        float force_drag = 0.5f * air_drag_coeff * (current_speed_ms * current_speed_ms);
        
        // 2ος Νόμος Νεύτωνα
        float net_force = force_propulsion - (force_gravity + force_drag);
        float acceleration = net_force / mass;

        return acceleration;
    }

    
    // 2. Επίλυση Θερμικής Δυναμικής Μπαταρίας (Με Pointers)
    
    void solve_battery_thermal_dynamics(float current_amps, float dt, float* soc, float* temperature) {
        
        float internal_resistance = 0.05f; // Ohms
        float heat_capacity = 500.0f;      // J/K
        float ambient_temp = 25.0f;        // Κελσίου
        float cooling_rate = 0.1f;         // Συντελεστής ψύξης
        
        // 1. Θερμότητα από το ρεύμα (Joule heating)
        float heat_generated = (current_amps * current_amps) * internal_resistance;
        
        // 2. Επίλυση Διαφορικής Εξίσωσης (Euler Method)
        float heat_dissipated = cooling_rate * (*temperature - ambient_temp);
        float delta_temp = ((heat_generated - heat_dissipated) / heat_capacity) * dt;
        
        // 3. Ενημέρωση μεταβλητών απευθείας στη μνήμη (Dereferencing)
        *temperature = *temperature + delta_temp;
        
        float capacity_Ah = 50.0f;
        *soc = *soc - ((current_amps * (dt / 3600.0f)) / capacity_Ah) * 100.0f;
    }

    //Monte Carlo Parallel Safety Solver (OpenMP)
    
    float run_monte_carlo_safety_check(float current_speed_ms, float throttle, int num_simulations) {
        
        int danger_count = 0;

        // Λέμε στον επεξεργαστή: Σπάσε τα simulations σε όλα τα Threads.
        // Το reduction(+:danger_count) αποτρέπει τα race conditions.
        #pragma omp parallel for reduction(+:danger_count)
        for (int i = 0; i < num_simulations; ++i) {
            
            // Κάθε Thread έχει τη δική του γεννήτρια θορύβου (για ρεαλισμό)
            std::mt19937 rng(1337 + i); 
            std::uniform_real_distribution<float> noise_dist(-0.2f, 0.2f); // +/- 20% θόρυβος

            float sim_speed = current_speed_ms;
            float dt = 0.1f;
            
            // Προσομοιώνουμε 30 βήματα (3 δευτερόλεπτα στο μέλλον)
            for (int step = 0; step < 30; ++step) {
                float random_drag_noise = 1.0f + noise_dist(rng);
                float random_friction_noise = 1.0f + noise_dist(rng);

                // Φυσική με στοχαστικό θόρυβο
                float acceleration = (throttle * 10.0f * random_friction_noise) - (0.05f * sim_speed * sim_speed * random_drag_noise);
                sim_speed += acceleration * dt;

                // ΚΡΙΤΗΡΙΟ ΑΤΥΧΗΜΑΤΟΣ: Αν ξεπεράσει τα 180 km/h (50 m/s) ή κάνει τετακέ (< 0 m/s)
                if (sim_speed > 50.0f || sim_speed < 0.0f) {
                    danger_count++;
                    break; 
                }
            }
        }

        // Επιστρέφουμε την ΠΙΘΑΝΟΤΗΤΑ κινδύνου (από 0.0 έως 1.0)
        return (float)danger_count / (float)num_simulations;
    }
}