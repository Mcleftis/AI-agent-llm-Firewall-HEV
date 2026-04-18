#include <iostream>
#include <string>
#include <cstring>
#include <atomic>
#include <vector>
#include <algorithm>

#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT
#endif

const uint32_t SPOOFED_CAN_ID = 0x666;
const uint32_t MAX_STANDARD_CAN_ID = 0x7FF;
const float MIN_SAFE_SENSOR_VAL = -1000.0f;
const float MAX_SAFE_SENSOR_VAL = 10000.0f;

std::atomic<size_t> BLOCKED_COUNT(0);

const std::vector<std::string> MALICIOUS_PAYLOADS = {
    "MAX_THROTTLE", "DROP", "fuzz", "ignore all previous instructions", "system failure", "override"
};

extern "C" {
    DLL_EXPORT int inspect_can_packet(uint32_t packet_id, const unsigned char* payload, size_t payload_length) {
        if (payload == nullptr) { BLOCKED_COUNT++; return 0; }
        size_t required_size = sizeof(float) + sizeof(uint32_t);
        if (payload_length < required_size) { BLOCKED_COUNT++; return 0; }

        float sensor_value;
        uint32_t message_counter;
        std::memcpy(&sensor_value, payload, sizeof(float));
        std::memcpy(&message_counter, payload + sizeof(float), sizeof(uint32_t));

        if (packet_id == SPOOFED_CAN_ID || packet_id > MAX_STANDARD_CAN_ID) { BLOCKED_COUNT++; return 0; }
        if (sensor_value < MIN_SAFE_SENSOR_VAL || sensor_value > MAX_SAFE_SENSOR_VAL) { BLOCKED_COUNT++; return 0; }
        return 1;
    }

    DLL_EXPORT int validate_api_command(const char* command) {
        if (command == nullptr) return 0; 
        std::string cmd(command);
        std::transform(cmd.begin(), cmd.end(), cmd.begin(), ::tolower);
        
        for (const auto& payload : MALICIOUS_PAYLOADS) {
            std::string lower_payload = payload;
            std::transform(lower_payload.begin(), lower_payload.end(), lower_payload.begin(), ::tolower);
            if (cmd.find(lower_payload) != std::string::npos) {
                BLOCKED_COUNT++; return 0;
            }
        }
        return 1;
    }

    DLL_EXPORT size_t get_firewall_stats() { return BLOCKED_COUNT.load(); }
}
