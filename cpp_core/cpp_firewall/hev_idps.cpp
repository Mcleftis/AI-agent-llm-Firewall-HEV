#include "hev_idps.h"

inline float clamp_f(float val, float min_v, float max_v) {
    if (val < min_v) return min_v;
    if (val > max_v) return max_v;
    return val;
}

extern "C" __declspec(dllexport) bool apply_safety_guardrails(VehicleState* state) {
    bool intervened = false;

    // R1: Actuator Conflict (Brake + Throttle)
    if (state->requested_brake > 0.05f && state->requested_throttle > 0.05f) {
        state->requested_throttle = 0.0f; // Priority to brakes
        intervened = true;
    }

    // R2: Overspeed Limit
    if (state->current_speed_kmh >= 180.0f && state->requested_throttle > 0.0f) {
        state->requested_throttle = 0.0f;
        intervened = true;
    }

    // R3: Battery Protection (Low SoC)
    if (state->battery_soc < 5.0f && state->requested_throttle > 0.2f) {
        state->requested_throttle = 0.2f; // Force ECO mode
        intervened = true;
    }

    // Final Safety Clamp
    state->requested_throttle = clamp_f(state->requested_throttle, 0.0f, 1.0f);
    state->requested_brake    = clamp_f(state->requested_brake, 0.0f, 1.0f);

    return !intervened; // true if safe (no intervention)
}

extern "C" __declspec(dllexport) const char* get_idps_version(void) {
    return "HEV-IDPS 1.0.0 (Windows Native)";
}
