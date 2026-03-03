#include <iostream>
#include <string>
#include <cstring>
#include <atomic>

std::atomic<size_t> BLOCKED_COUNT(0);

extern "C" {
    // 1. Για το can_bus_firewall.py (Ελέγχει τα δεδομένα της μπαταρίας/ταχύτητας)
    int inspect_packet(uint32_t packet_id, const unsigned char* payload) {
        // Η Python μας στέλνει 8 bytes: [4 bytes Float] + [4 bytes Unsigned Int]
        float value;
        uint32_t counter;
        std::memcpy(&value, payload, 4);
        std::memcpy(&counter, payload + 4, 4);

        // Περίεργα IDs (Hacking attempt)
        if (packet_id == 0x666 || packet_id > 0x7FF) {
            BLOCKED_COUNT++;
            return 0; // 0 = False = Block
        }

        // Φυσικοί Περιορισμοί (Ακραίες τιμές)
        if (value < -1000.0f || value > 10000.0f) {
            BLOCKED_COUNT++;
            return 0; // 0 = False = Block
        }

        return 1; // 1 = True = Safe
    }

    // 2. Για το server.py (Ελέγχει τις λέξεις στα text commands)
    int validate_command(const char* command) {
        std::string cmd(command);
        
        if (cmd.find("MAX_THROTTLE") != std::string::npos || 
            cmd.find("DROP") != std::string::npos || 
            cmd.find("fuzz") != std::string::npos) {
            BLOCKED_COUNT++;
            return 0; // 0 = False = Block
        }
        
        return 1; // 1 = True = Safe
    }

    // 3. Στατιστικά για το UI
    size_t get_firewall_stats() {
        return BLOCKED_COUNT.load();
    }
}