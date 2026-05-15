#pragma once
#include <stdint.h>
#include <stdbool.h>

#pragma pack(1)
typedef struct {
    float current_speed_kmh;
    float requested_throttle;
    float requested_brake;
    float battery_soc;
    float battery_temp_celsius;
    float engine_temperature_celsius;
    float motor_temp_celsius;
    int32_t gear_position;
} VehicleState;
#pragma pack()

#ifdef __cplusplus
extern "C" {
#endif

__declspec(dllexport) bool apply_safety_guardrails(VehicleState* state);
__declspec(dllexport) const char* get_idps_version(void);

#ifdef __cplusplus
}
#endif
