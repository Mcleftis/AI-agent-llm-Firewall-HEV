import pandas as pd
import numpy as np

SOC_MIN = 20       
SOC_MAX = 90       
SPEED_HIGH = 60    

def decision_agent(current_speed, current_soc, lstm_prediction_speed):
   
    if current_soc < SOC_MIN:
        return 1, "CRITICAL: Low Battery -> Engine ON"
    
    if current_soc > SOC_MAX:
        return 0, "PROTECTION: High Battery -> Force EV"

    if current_speed < SPEED_HIGH and lstm_prediction_speed > SPEED_HIGH:
        return 1, "PREDICTIVE: Acceleration Ahead -> Engine ON Early"
    
    if current_speed > SPEED_HIGH:
        return 1, "EFFICIENCY: High Speed -> Engine Optimized"
    else:
        return 0, "EFFICIENCY: Low Speed -> EV Mode"

if __name__ == "__main__":
    
    
    test_cases = [
        (10, 15, 20),   
        (50, 95, 60),   
        (30, 50, 80),   
        (100, 50, 100)  
    ]

    print("\nRunning Agent Safety Tests")
    
    
    for i, (speed, soc, pred) in enumerate(test_cases):
       
        action, reason = decision_agent(speed, soc, pred)
        mode = "ENGINE (1)" if action == 1 else "EV MODE (0)"
        print(f"Test Case {i+1}:")
        print(f"  Inputs: Speed={speed}, SOC={soc}%, Pred={pred}")
        print(f"  Result: {mode}")
        print(f"  Reason: {reason}")
        print("-" * 30)