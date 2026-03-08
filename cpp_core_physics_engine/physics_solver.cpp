#include <cmath>
#include <random> 
#include <omp.h>  

extern "C" {
    
    struct VehicleState {
        float speed_ms;
        float mass;
        float air_drag_coeff;
        float slope_deg;
        float soc;
        float temperature;
    };

    
    float calculate_acceleration(float throttle, VehicleState* v) { //deikths p deixnei p einai to struct sth mnhmh
        float max_power = 200000.0f; // 200kW
        float gravity = 9.81f;
        float pi = 3.14159265f;

        
        float force_propulsion = (throttle * max_power) / (v->speed_ms + 1.0f);
        float force_gravity = v->mass * gravity * sin(v->slope_deg * pi / 180.0f);
        float force_drag = 0.5f * v->air_drag_coeff * (v->speed_ms * v->speed_ms);
        
        float net_force = force_propulsion - (force_gravity + force_drag);
        return net_force / v->mass;
    }

    
    void solve_battery_thermal_dynamics(float current_amps, float dt, VehicleState* v) {
        float internal_resistance = 0.05f; 
        float heat_capacity = 500.0f;      
        float ambient_temp = 25.0f;        
        float cooling_rate = 0.1f;         
        
        float heat_generated = (current_amps * current_amps) * internal_resistance;
        float heat_dissipated = cooling_rate * (v->temperature - ambient_temp);
        float delta_temp = ((heat_generated - heat_dissipated) / heat_capacity) * dt;
        
        // Τροποποιούμε (γράφουμε) τη μνήμη της Python από τη C++ !
        v->temperature += delta_temp;
        
        float capacity_Ah = 50.0f;
        v->soc -= ((current_amps * (dt / 3600.0f)) / capacity_Ah) * 100.0f;
    }

    // 4. MONTE CARLO (Παραμένει ίδιο, παίρνει απλές τιμές)
    float run_monte_carlo_safety_check(float current_speed_ms, float throttle, int num_simulations) {
        int danger_count = 0;

        #pragma omp parallel for reduction(+:danger_count)
        for (int i = 0; i < num_simulations; ++i) {
            std::mt19937 rng(1337 + i); 
            std::uniform_real_distribution<float> noise_dist(-0.2f, 0.2f); 

            float sim_speed = current_speed_ms;
            float dt = 0.1f;
            
            for (int step = 0; step < 30; ++step) {
                float random_drag_noise = 1.0f + noise_dist(rng);
                float random_friction_noise = 1.0f + noise_dist(rng);

                float acceleration = (throttle * 10.0f * random_friction_noise) - (0.05f * sim_speed * sim_speed * random_drag_noise);
                sim_speed += acceleration * dt;

                if (sim_speed > 50.0f || sim_speed < 0.0f) {
                    danger_count++;
                    break; 
                }
            }
        }
        return (float)danger_count / (float)num_simulations;
    }
}