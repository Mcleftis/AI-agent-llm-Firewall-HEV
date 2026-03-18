#include <iostream>
#include <string>
#include <cstring>
#include <atomic>
#include <vector>
#include <algorithm>

// ========================================================================
// WINDOWS COMPATIBILITY (ABI)
// ========================================================================
#ifdef _WIN32
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT
#endif

// ========================================================================
// ΣΤΑΘΕΡΕΣ & ΠΕΡΙΟΡΙΣΜΟΙ
// ========================================================================
const uint32_t SPOOFED_CAN_ID = 0x666;
const uint32_t MAX_STANDARD_CAN_ID = 0x7FF;

const float MIN_SAFE_SENSOR_VAL = -1000.0f;
const float MAX_SAFE_SENSOR_VAL = 10000.0f;

// Global Counter (Thread-Safe)
std::atomic<size_t> BLOCKED_COUNT(0);

const std::vector<std::string> MALICIOUS_PAYLOADS = {
    "MAX_THROTTLE", 
    "DROP", 
    "fuzz", 
    "ignore all previous instructions", 
    "system failure", 
    "override"
};

extern "C" {

    // 1. HARDWARE LAYER
    // [PRO FIX]: Προσθέσαμε το size_t payload_length
    DLL_EXPORT int inspect_can_packet(uint32_t packet_id, const unsigned char* payload, size_t payload_length) {
        
        // [MEMORY SAFETY 1]: Null Pointer Check
        if (payload == nullptr) {
            BLOCKED_COUNT++;
            return 0; 
        }

        // [MEMORY SAFETY 2]: Buffer Overread / Bounds Checking
        // Ξέρουμε ότι θέλουμε να διαβάσουμε έναν float (4) και έναν uint32_t (4) = 8 bytes.
        size_t required_size = sizeof(float) + sizeof(uint32_t);
        if (payload_length < required_size) {
            // Αν το πακέτο είναι μικρότερο από 8 bytes, είναι "κομμένο" (Malicious / Corrupted).
            // Το πετάμε κατευθείαν για να μη διαβάσει το memcpy μνήμη εκτός ορίων.
            BLOCKED_COUNT++;
            return 0; 
        }

        float sensor_value;
        uint32_t message_counter;
        
        // Τώρα το memcpy είναι 100% ασφαλές.
        std::memcpy(&sensor_value, payload, sizeof(float));
        std::memcpy(&message_counter, payload + sizeof(float), sizeof(uint32_t));

        // A. Έλεγχος ID (Spoofing Detection)
        if (packet_id == SPOOFED_CAN_ID || packet_id > MAX_STANDARD_CAN_ID) {
            BLOCKED_COUNT++;
            return 0; // BLOCK
        }

        // B. Έλεγχος Φυσικών Περιορισμών (Anomaly Detection)
        if (sensor_value < MIN_SAFE_SENSOR_VAL || sensor_value > MAX_SAFE_SENSOR_VAL) {
            BLOCKED_COUNT++;
            return 0; // BLOCK
        }

        return 1; // SAFE
    }

    // 2. APPLICATION LAYER
    DLL_EXPORT int validate_api_command(const char* command) {
        // [MEMORY SAFETY 3]: Null Pointer
        if (command == nullptr) return 0; 
        
        // [MEMORY SAFETY 4]: RAII (Αυτόματο Free/Delete, χωρίς Memory Leaks)
        std::string cmd(command);
        
        std::transform(cmd.begin(), cmd.end(), cmd.begin(), ::tolower);
        
        for (const auto& payload : MALICIOUS_PAYLOADS) {
            std::string lower_payload = payload;
            std::transform(lower_payload.begin(), lower_payload.end(), lower_payload.begin(), ::tolower);
            
            if (cmd.find(lower_payload) != std::string::npos) {
                // [CONCURRENCY SAFETY]: Ασφαλής αύξηση счетчика (Atomic) χωρίς Race Conditions
                BLOCKED_COUNT++;
                return 0; // BLOCK
            }
        }
        
        return 1; // SAFE
    }

    // 3. Στατιστικά
    DLL_EXPORT size_t get_firewall_stats() {
        return BLOCKED_COUNT.load();
    }
}