import os
os.environ["PYTHONUTF8"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import torch
import torch.nn as nn
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

class CustomPPOActorCritic(nn.Module):
    def __init__(self, obs_dim=4, action_dim=1):
        super(CustomPPOActorCritic, self).__init__()
        
        self.actor = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, action_dim),
            nn.Tanh()
        )
        
        self.critic = nn.Sequential(
            nn.Linear(obs_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh(),
            nn.Linear(64, 1)
        )
        
        self.action_log_std = nn.Parameter(torch.zeros(1, action_dim))

    def forward(self, obs):
        return self.actor(obs), self.critic(obs)
        
    def predict(self, obs, deterministic=True):
        action_mean = self.actor(obs)
        
        if deterministic:
            return action_mean.detach().cpu().numpy()[0]
        else:
            action_std = torch.exp(self.action_log_std)
            dist = torch.distributions.Normal(action_mean, action_std)
            action = dist.sample()
            action = torch.clamp(action, -1.0, 1.0)
            return action.detach().cpu().numpy()[0]

def load_finetuned_llm():
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

    return llm_model, tokenizer

def ask_llm(model, tokenizer, user_input):
    prompt = f"### User: {user_input} ### Assistant:"
    inputs = tokenizer(prompt, return_tensors="pt").to("cpu")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=50,
            do_sample=False,   
        )

    response     = tokenizer.decode(outputs[0], skip_special_tokens=True)
    final_answer = response.split("### Assistant:")[-1].strip()
    return final_answer

def load_rl_agent():
    model_path = os.path.join("models", "ppo_hev_actor_critic.pth")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    rl_model = CustomPPOActorCritic(obs_dim=4, action_dim=1).to(device)

    if os.path.exists(model_path):
        rl_model.load_state_dict(torch.load(model_path, map_location=device))
        
    rl_model.eval()
    return rl_model, device

if __name__ == "__main__":
    llm_model, tokenizer = load_finetuned_llm()
    rl_agent, rl_device = load_rl_agent()

    driver_input  = "Βιάζομαι πολύ να φτάσω νοσοκομείο"

    llm_decision = ask_llm(llm_model, tokenizer, driver_input)

    if rl_agent:
        speed_kmh   = 50.0
        slope       = 0.0    
        distance_m  = 100.0
        soc_pct     = 40.0

        obs_np = np.array([speed_kmh, slope, distance_m, soc_pct], dtype=np.float32)
        obs_tensor = torch.tensor(obs_np).unsqueeze(0).to(rl_device)

        with torch.no_grad():
            action = rl_agent.predict(obs_tensor, deterministic=True)
            throttle = float(action[0])