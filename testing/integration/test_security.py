import time
import random
from can_bus_firewall import CANBusFirewall

def start_hacking_simulation():
    print("ACTIVATING FULL SECURITY SUITE TEST...\n")
    
    #arxikopoihsh firewall
    firewall = CANBusFirewall(max_delta=50, max_packets=20)

    
    #authentication check
    print("Phase 1: Authentication Check")
    
    #hacking
    hacker_token = "HACKER_123"#eskemmena lathos kwdikos
    print(f"[HACKER] Trying to login with token: '{hacker_token}'")
    if firewall.verify_token(hacker_token):#synarthsh tou can_bus_firewall
        print("FAILURE: Hacker got access!")
    else:
        print("SUCCESS: Hacker blocked.")

    #swstos kwdikos
    driver_token = "SECRET_DRIVER_KEY_2026"
    print(f"[DRIVER] Trying to login with token: '{driver_token}'")
    if firewall.verify_token(driver_token):
        print("SUCCESS: Driver Access Granted.")
    else:
        print("FAILURE: Valid Driver blocked!")

    #spoofing
    print("\nPhase 2: Spoofing Attack (Teleport Check)")
    
    #normal odhghsh
    packet_id = 0x100 #engine id
    current_speed = 50.0
    
    #kaleis to firewall na to eleksei
    firewall.inspect_packet(packet_id, str(current_speed))

    fake_speed = 200.0
    print(f"[HACKER] Sending fake speed {fake_speed} km/h (Instant Jump)...")
    
    is_safe = firewall.inspect_packet(packet_id, str(fake_speed))
    
    if is_safe:
        print("FAILURE: The attack passed!")
    else:
        print("SUCCESS: Attack Blocked (Delta Check triggered).")

    #DoS attack
    print("\nPhase 3: DoS Attack (Flooding)")
    print("[HACKER] Flooding the bus with rapid messages...")
    
    blocked_count = 0
    #stelnoume astrapiaia 50 paketa xwris sleep
    for i in range(50):
        #vazoume epitrepto id gia na tsekaroume an einai fysiologiko, na apostelontai tosa paketa
        is_safe = firewall.inspect_packet(0x100, str(50 + i)) 
        if not is_safe:
            blocked_count += 1
            
    print(f"Firewall Blocked: {blocked_count}/50 packets.")
    if blocked_count > 0:
        print("SUCCESS: DoS Attack Detected & Mitigated.")
    else:
        print("FAILURE: Firewall didn't catch the flood.")

    print("\n" + "="*40)
    print("SECURITY AUDIT COMPLETE")
    print("="*40)

if __name__ == "__main__":
    start_hacking_simulation()