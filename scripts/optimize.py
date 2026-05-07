import pandas as pd
import os
import shutil
import time
from AI_agent import train_ppo
from run_ablation import run_simulation 


RESULTS_FILE = "data/grid_search_results.csv" #apotelesamta grid search
MODELS_DIR = "models"#montela pou ekpaidevontai

def run_grid_search():
    print("\nSTARTING GRID SEARCH OPTIMIZATION")
    
    learning_rates_to_test = [0.0001, 0.0003, 0.001]
    results = []#edw tha mpoun dictionaries mesa


    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)

    for lr in learning_rates_to_test:
        print(f"\n TESTING PARAMETER: Learning Rate = {lr}")
        

        lr_str = str(lr).replace('.', '_')
        model_filename = f"ppo_hev_lr_{lr_str}"

        save_path_request = os.path.join(MODELS_DIR, model_filename)
        

        print(f"Training:")
        train_ppo(steps=20000, lr=lr, save_path=save_path_request, traffic='normal')
        
        time.sleep(1) #na anasanei to systhma an xreiastoun polla training


        print("Evaluating:")
        

        possible_files = [
            save_path_request + ".zip",  #Prwta .zip
            save_path_request            #An den yparxei, psakse to sketo
        ]
        
        source_path = None#den kserw akoma poio einai to path
        for p in possible_files:#loop sta 2 pithan paths
            if os.path.exists(p):
                source_path = p#an to vrhkes apothikefse to ekei
                break
        
        target_path = os.path.join(MODELS_DIR, "ppo_hev.zip") #arxeio pou psaxnei to ablation

        if source_path:#an vrei kapoio arxeio to montelo
            print(f"[Debug] Found model file at: {source_path}")
            try:

                shutil.copy(source_path, target_path)
                

                fuel_consumed = run_simulation(mode='baseline')
                
                if fuel_consumed is not None:
                    print(f"Result: Fuel Consumed = {fuel_consumed:.4f} L")
                    results.append({
                        "Learning Rate": lr,
                        "Fuel Consumption (L)": fuel_consumed,
                        "Model Path": source_path
                    })
                else:
                    print("Simulation returned None.")

            except Exception as e:
                print(f"Error during evaluation: {e}")
        else:
            print(f"Error: Could not find model file! Checked: {possible_files}")

   
    print("\nGRID SEARCH RESULTS")
    
    if not results:
        print("No results collected.")
        return

    df_results = pd.DataFrame(results)
    

    try:
        df_results = df_results.sort_values(by="Fuel Consumption (L)", ascending=True)#dataframe pou exei oles tis dokimes tou grid search, h mikroterh katanalwsh mpainei prwth
        print(df_results)
        df_results.to_csv(RESULTS_FILE, index=False)#xwris arithmisi grammwn afou exoume index=False
        print(f"\nDetailed results saved to {RESULTS_FILE}")
        
        best_lr = df_results.iloc[0]["Learning Rate"]#prwth grammh tou taksinomhmenou dataframe, kai pernoume th sthlh "Learning Rate"
        print(f"\nRECOMMENDATION: The best Learning Rate is {best_lr}")
    except Exception as e:
        print(f"Error showing results: {e}")

if __name__ == "__main__":
    run_grid_search()