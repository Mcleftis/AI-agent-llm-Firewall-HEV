import pandas as pd
import numpy as np
from stable_baselines3 import PPO
from AI_agent import ProfessionalHybridEnv, DATA_FILENAME
import os


MODEL_PATH = "models/ppo_hev"  #To monopati pou swsame to montelo
RESULTS_FILE = "data/ablation_results.csv"

def run_simulation(mode='baseline'):
    """
    Τρέχει μια προσομοίωση οδήγησης.
    mode: 'baseline' (Σκέτο PPO) ή 'neuro_symbolic' (PPO + LLM Logic)
    """
    print(f"Running Simulation Mode: [{mode.upper()}]")
    
    
    if not os.path.exists(DATA_FILENAME):#tsekaroume thn yparksh tou arxeiou
        print("Dataset not found!")
        return None

    df = pd.read_csv(DATA_FILENAME)

    df.columns = df.columns.str.strip()
    if 'Regenerative Braking Power (kW)' not in df.columns:
         df['Regenerative Braking Power (kW)'] = 0.0#an den hyparxei h regen sthlh, dhmiourghse th kai gemise th me 0.0
         
    env = ProfessionalHybridEnv(df)
    

    try:
        model = PPO.load(MODEL_PATH)
    except:
        print(f"Model not found at {MODEL_PATH}. Make sure you trained it first!")
        return None


    obs, _ = env.reset()#nea prosomoiwsh, fere mou thn arxikh katastash tou oxhmatos me th pavla, an kai einai proairetiko gia afto to vhma
    total_fuel = 0.0
    total_steps = 0
    
    done = False#flag pou ginetai true mono otan teleiwsei to dataset h oloklhrwthei to peisodio h an apofasisei to environment oti prepei na stamathsei
    while not done:

        action, _ = model.predict(obs)
        
        
        if mode == 'neuro_symbolic':


            current_speed = obs[0] #speed prwto stoixeio tou observation
            
            if current_speed < 20.0:

                action = np.array([0.0], dtype=np.float32)
        
        
        obs, reward, terminated, truncated, info = env.step(action) #observation, antamoivh, teleiwse fysiologika, teleiwse logo oriou,
        
        total_fuel += info['fuel']#dictionary pou periexei katanalwsh kafsimou se afto to vhma
        total_steps += 1
        done = terminated or truncated

    print(f"Simulation Finished. Total Fuel: {total_fuel:.4f} Liters")
    return total_fuel

def run_study():
    print("\nSTARTING ABLATION STUDY")
    print("Goal: Prove that LLM-guided logic improves efficiency compared to raw PPO.")
    
    results = {}
    

    print("\nTEST 1: Baseline PPO (No LLM)")
    fuel_baseline = run_simulation(mode='baseline')#episterefei posa litra kafsimou katanalwthikan
    results['Baseline (PPO Only)'] = fuel_baseline
    

    print("\nTEST 2: Neuro-Symbolic (PPO + LLM Rules)")
    fuel_hybrid = run_simulation(mode='neuro_symbolic')
    results['Neuro-Symbolic (Hybrid)'] = fuel_hybrid
    

    if fuel_baseline is not None and fuel_hybrid is not None:
        print("\nFINAL RESULTS REPORT")
        print(f"Fuel (Baseline):{fuel_baseline:.4f} L")
        print(f"Fuel (Neuro-Symbolic): {fuel_hybrid:.4f} L")
        
        improvement = fuel_baseline - fuel_hybrid
        percent = (improvement / fuel_baseline) * 100 if fuel_baseline > 0 else 0
        
        print(f"\nFuel Saved: {improvement:.4f} L")
        print(f"Efficiency Improvement: {percent:.2f}%")
        
        if improvement > 0:
            print("CONCLUSION: The Neuro-Symbolic system IS more efficient!")
        else:
            print("CONCLUSION: No improvement detected (Adjust the LLM rules).")
            

        df_res = pd.DataFrame([results])
        df_res.to_csv(RESULTS_FILE, index=False)
        print(f"Results saved to {RESULTS_FILE}")

if __name__ == "__main__":
    run_study()