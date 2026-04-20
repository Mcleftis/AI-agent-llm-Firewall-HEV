import os
import pytest
import pandas as pd
from stable_baselines3 import PPO
from AI_agent import ProfessionalHybridEnv, DATA_FILENAME, _load_telemetry

class TestAIAgentExecution:
    
    # ---------------------------------------------------------
    # ΦΑΣΗ 1: Το Εργοστάσιο (Fixture) - Φορτώνει τα πάντα 1 φορά
    # ---------------------------------------------------------
    @pytest.fixture(scope="class")
    def ai_system(self):
        """Φορτώνει το Environment και το PPO Model για ένα γρήγορο τεστ."""
        
        # 1. Βεβαιωνόμαστε ότι τα δεδομένα υπάρχουν
        assert os.path.exists(DATA_FILENAME), f"Dataset {DATA_FILENAME} is missing!"
        
        df = pd.read_csv(DATA_FILENAME)
        df.columns = df.columns.str.strip()
        if 'Regenerative Braking Power (kW)' not in df.columns: 
            df['Regenerative Braking Power (kW)'] = 0.0
            
        # 2. Βεβαιωνόμαστε ότι το μοντέλο δεν διεγράφη κατά λάθος από το repo
        model_path = "models/ppo_hev"
        if not (os.path.exists(model_path + ".zip") or os.path.exists(model_path)):
            pytest.skip("AI Model missing. Please train the PPO agent first.")
            
        # Αν όλα πάνε καλά, τα φορτώνουμε στη μνήμη
        model = PPO.load(model_path)
        arrays = _load_telemetry()
        env = ProfessionalHybridEnv(arrays)
        
        return env, model

    # ---------------------------------------------------------
    # ΦΑΣΗ 2: Το Smoke Test (Εκτέλεση Αστραπή)
    # ---------------------------------------------------------
    def test_model_inference_smoke(self, ai_system):
        """
        Ελέγχει αν το AI μπορεί να διαβάσει το περιβάλλον (obs) και να 
        βγάλει μια απόφαση (action) χωρίς να κρασάρει η Python.
        """
        env, model = ai_system
        obs, _ = env.reset()
        
        # ΑΝΤΙ ΓΙΑ INFINITE LOOP: Τρέχουμε ΜΟΝΟ 5 βήματα!
        # Στο QA δεν μας νοιάζει να τερματίσει τη διαδρομή. 
        # Μας νοιάζει μόνο να δούμε ότι ο κώδικας δεν "σκάει".
        steps_to_test = 5 
        successful_steps = 0
        
        for _ in range(steps_to_test):
            try:
                # Το AI σκέφτεται...
                action, _ = model.predict(obs)
                
                # Το Περιβάλλον αντιδρά...
                obs, reward, terminated, truncated, info = env.step(action)
                successful_steps += 1
                
                if terminated or truncated:
                    break
            except Exception as e:
                pytest.fail(f"CRITICAL: AI Execution crashed during step {successful_steps + 1}. Error: {e}")
                
        # THE ASSERT: Επιβεβαιώνουμε ότι τρέξαμε τα βήματα με επιτυχία
        assert successful_steps > 0, "Model failed to take even a single step."
        
        print(f"\n-> AI Smoke Test Passed: Successfully executed {successful_steps} steps in milliseconds.")
