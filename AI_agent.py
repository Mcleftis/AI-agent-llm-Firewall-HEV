import os
os.environ["PYTHONUTF8"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import torch
import numpy as np
from stable_baselines3 import PPO
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

# =============================================================================
# 1. ΦΟΡΤΩΣΗ ΤΟΥ FINE-TUNED LLM (LoRA) ΓΙΑ INTENT RECOGNITION
# =============================================================================
def load_finetuned_llm():
    print("🧠 Φόρτωση του Fine-Tuned Agent (LoRA)...")

    base_model_id = "HuggingFaceTB/SmolLM-1.7B"
    adapter_dir   = "./hev_llama_lora"

    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        torch_dtype=torch.float32,
        device_map="cpu",
    )

    llm_model = PeftModel.from_pretrained(base_model, adapter_dir)
    llm_model.eval()

    print("✅ Το LLM είναι έτοιμο με τα LoRA adapters (CPU Mode)!")
    return llm_model, tokenizer


# =============================================================================
# 2. ΕΡΩΤΗΣΗ ΣΤΟ LLM (INFERENCE)
# =============================================================================
def ask_llm(model, tokenizer, user_input):
    prompt = f"### User: {user_input} ### Assistant:"
    inputs = tokenizer(prompt, return_tensors="pt").to("cpu")

    outputs = model.generate(
        **inputs,
        max_new_tokens=50,
        do_sample=False,   # greedy decoding — χωρίς temperature warning
    )

    response     = tokenizer.decode(outputs[0], skip_special_tokens=True)
    final_answer = response.split("### Assistant:")[-1].strip()
    return final_answer


# =============================================================================
# 3. ΦΟΡΤΩΣΗ ΤΟΥ RL PPO AGENT (ΓΙΑ ΟΔΗΓΗΣΗ / THROTTLE)
# =============================================================================
def load_rl_agent():
    print("🚗 Φόρτωση του PPO RL Agent...")
    model_path = os.path.join("models", "ppo_hev.zip")

    if not os.path.exists(model_path):
        print("❌ Το μοντέλο PPO δεν βρέθηκε! Βεβαιώσου ότι έχεις τρέξει την εκπαίδευση.")
        return None

    device   = "cuda" if torch.cuda.is_available() else "cpu"
    rl_model = PPO.load(model_path, device=device)
    print(f"✅ Ο RL Agent είναι έτοιμος! (device: {device})")
    return rl_model


# =============================================================================
# MAIN EXECUTION: ΕΝΩΝΟΝΤΑΣ ΤΟΥΣ ΔΥΟ ΕΓΚΕΦΑΛΟΥΣ
# =============================================================================
if __name__ == "__main__":
    print("=== ΕΝΑΡΞΗ ΥΒΡΙΔΙΚΟΥ AI ΣΥΣΤΗΜΑΤΟΣ (RL + LLM) ===")

    llm_model, tokenizer = load_finetuned_llm()
    rl_agent = load_rl_agent()

    print("\n" + "=" * 50)

    # --- 1. Τεστ LLM ---
    print("--- 1. Τεστ LLM (Intent & Urgency) ---")
    driver_input  = "Βιάζομαι πολύ να φτάσω νοσοκομείο"
    print(f"Φωνητική εντολή οδηγού: '{driver_input}'")

    llm_decision = ask_llm(llm_model, tokenizer, driver_input)
    print(f"Απόφαση LLM: {llm_decision}")

    print("-" * 50)

    # --- 2. Τεστ PPO Agent ---
    if rl_agent:
        print("--- 2. Τεστ PPO Agent (Vehicle Control) ---")

        # Observation shape (4,) — από το _get_obs() του full_system.py:
        # [speed_kmh, slope(0.0), distance_m, soc_%]
        speed_kmh   = 50.0
        slope       = 0.0    # flat road
        distance_m  = 100.0
        soc_pct     = 40.0

        obs = np.array([speed_kmh, slope, distance_m, soc_pct], dtype=np.float32)

        action, _states = rl_agent.predict(obs, deterministic=True)
        throttle = float(action[0])

        print(f"Τηλεμετρία: Speed={speed_kmh}km/h | Distance={distance_m}m | SOC={soc_pct}% | Slope={slope}°")
        if throttle > 0:
            print(f"Ενέργεια RL Agent: ΓΚΑΖΙ κατά {throttle:.2f}")
        else:
            print(f"Ενέργεια RL Agent: ΦΡΕΝΟ κατά {abs(throttle):.2f}")

    print("=" * 50)