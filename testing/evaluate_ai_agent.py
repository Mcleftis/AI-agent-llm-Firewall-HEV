import os
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.evaluation import evaluate_policy

# Εισαγωγή των συναρτήσεων σου από το AI_agent.py
from AI_agent import _load_telemetry, _build_vec_env, MODEL_SAVE_DIR, MODEL_NAME

def run_comprehensive_evaluation(episodes=100):
    print("🚀 [INFO] Ξεκινάει η Σκληρή Αξιολόγηση του PPO Agent...")

    # 1. Φόρτωση Περιβάλλοντος (Validation Set πρακτικά)
    # Σε production, εδώ θα φορτώναμε ένα UNSEEN dataset (Test Set), ΟΧΙ αυτό που εκπαιδεύτηκε
    arrays = _load_telemetry() 
    eval_env = _build_vec_env(arrays)

    # 2. Φόρτωση του εκπαιδευμένου Μοντέλου
    model_path = os.path.join(MODEL_SAVE_DIR, MODEL_NAME + ".zip")
    if not os.path.exists(model_path):
        print(f"❌ [ERROR] Το μοντέλο {model_path} δεν βρέθηκε!")
        return

    model = PPO.load(model_path, env=eval_env)

    # =========================================================================
    # METRIC 1 & 2: Standard SB3 Evaluation (Mean Reward & Std)
    # =========================================================================
    print(f"📊 [METRIC] Τρέχουμε {episodes} Επεισόδια Αξιολόγησης (Standard Metrics)...")
    mean_reward, std_reward = evaluate_policy(model, eval_env, n_eval_episodes=episodes, deterministic=True)
    
    # =========================================================================
    # METRIC 3 & 4: Custom Control Metrics (Smoothness, Length, Guardrail Blocks)
    # =========================================================================
    print("⚙️ [METRIC] Υπολογισμός Domain-Specific Metrics (Smoothness, Length)...")
    
    episode_lengths = []
    action_variances = []
    
    for _ in range(episodes):
        obs = eval_env.reset()
        done = False
        steps = 0
        actions_taken = []

        # Τρέχουμε 1 ολόκληρο επεισόδιο
        # Επειδή χρησιμοποιείς VecEnv, το done είναι array από booleans
        while steps < 1000: # Βάζουμε ένα hard limit για να μην κολλήσει
            # deterministic=True σημαίνει ότι παίρνει την ΚΑΛΥΤΕΡΗ απόφαση (όχι τυχαία εξερεύνηση)
            action, _states = model.predict(obs, deterministic=True)
            actions_taken.append(action[0]) # Αποθηκεύουμε την εντολή (π.χ. γκάζι/φρένο)
            
            obs, rewards, dones, info = eval_env.step(action)
            steps += 1
            
            if dones.any(): # Αν το περιβάλλον τερματίσει
                break
                
        episode_lengths.append(steps)
        
        # Υπολογισμός Jerk (Πόσο "απότομα" αλλάζει τις εντολές του)
        actions_np = np.array(actions_taken)
        if len(actions_np) > 1:
            action_diffs = np.diff(actions_np, axis=0) # Διαφορά από το προηγούμενο step
            action_variance = np.var(action_diffs)
            action_variances.append(action_variance)

    # --- Υπολογισμός Τελικών Custom Metrics ---
    mean_ep_length = np.mean(episode_lengths)
    mean_action_variance = np.mean(action_variances) if action_variances else 0.0

    print("\n" + "="*50)
    print("🏆 ΤΕΛΙΚΟ ΑΝΑΛΥΤΙΚΟ REPORT ΑΞΙΟΛΟΓΗΣΗΣ (PPO AGENT) 🏆")
    print("="*50)
    print(f"✔️ Mean Cumulative Reward : {mean_reward:.2f} (Όσο υψηλότερο, τόσο πιο 'έξυπνος' ο Agent)")
    print(f"✔️ Reward Std Deviation   : {std_reward:.2f} (Ιδανικά κοντά στο 0. Χαμηλό = Σταθερότητα)")
    print(f"✔️ Mean Episode Length    : {mean_ep_length:.2f} steps (Ιδανικά φτάνει το Max Steps χωρίς να κρασάρει)")
    print(f"✔️ Action Smoothness (Var): {mean_action_variance:.4f} (Χαμηλό = Ομαλή οδήγηση, Υψηλό = Απότομο/Επικίνδυνο)")
    print("="*50)
    print("💡 Senior Note: Η απόλυτη σταθερότητα εξασφαλίζεται μόνο όταν αυτά τα metrics")
    print("συνδυάζονται με το C++ Firewall (Neuro-Symbolic) για zero-day protection.")

if __name__ == "__main__":
    run_comprehensive_evaluation()