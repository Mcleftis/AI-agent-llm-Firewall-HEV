import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig

# ── DATASET ───────────────────────────────────────────────────────────────────
raw_data = [
    "### User: Βιάζομαι πολύ να φτάσω νοσοκομείο ### Assistant: {\"urgency\": 5, \"intent\": \"emergency\"}",
    "### User: Πάμε χαλαρά μια βόλτα ### Assistant: {\"urgency\": 1, \"intent\": \"leisure\"}",
    "### User: Έχω αργήσει στη δουλειά ### Assistant: {\"urgency\": 4, \"intent\": \"work_rush\"}",
    "### User: Τρέχα γρήγορα είναι επείγον ### Assistant: {\"urgency\": 5, \"intent\": \"emergency\"}",
    "### User: Πήγαινέ με στο αεροδρόμιο με την ησυχία μου ### Assistant: {\"urgency\": 2, \"intent\": \"leisure\"}",
]

# Νέο TRL API: το dataset πρέπει να έχει "messages" ή απλά να κάνουμε
# tokenization χειροκίνητα με "input_ids". Ο πιο απλός τρόπος:
# δίνουμε "text" και το tokenize μόνοι μας.
dataset = Dataset.from_dict({"text": raw_data})

# ── TOKENIZER ─────────────────────────────────────────────────────────────────
model_id = "HuggingFaceTB/SmolLM-1.7B"

print("[1/4] Φόρτωση tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(model_id)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

# ── TOKENIZE DATASET (νέο API — χωρίς dataset_text_field) ────────────────────
def tokenize(batch):
    return tokenizer(
        batch["text"],
        truncation=True,
        max_length=128,
        padding="max_length",
    )

tokenized_dataset = dataset.map(tokenize, batched=True, remove_columns=["text"])
# Το SFTTrainer με pre-tokenized dataset θέλει "input_ids" ως labels
tokenized_dataset = tokenized_dataset.map(lambda x: {"labels": x["input_ids"]})

# ── MODEL ─────────────────────────────────────────────────────────────────────
print("[2/4] Φόρτωση μοντέλου (CPU)...")
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    dtype=torch.float32,   # float32 για CPU — float16 χρειάζεται CUDA
    device_map="cpu",
)

# ── LoRA ──────────────────────────────────────────────────────────────────────
print("[3/4] Εφαρμογή LoRA adapters...")
lora_config = LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# ── TRAINING ──────────────────────────────────────────────────────────────────
print("[4/4] Fine-Tuning σε εξέλιξη...")
trainer = SFTTrainer(
    model=model,
    train_dataset=tokenized_dataset,
    args=SFTConfig(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        max_steps=20,            # Αύξησε σε 100 για production
        learning_rate=2e-4,
        fp16=False,              # False σε CPU
        bf16=False,
        output_dir="outputs_hev_lora",
        logging_steps=5,
        save_steps=20,
        report_to="none",        # Απενεργοποιεί wandb
    ),
)

trainer.train()

# ── SAVE ──────────────────────────────────────────────────────────────────────
print("\n[DONE] Αποθήκευση LoRA adapters...")
trainer.model.save_pretrained("hev_llama_lora")
tokenizer.save_pretrained("hev_llama_lora")
print("[DONE] Αποθηκεύτηκε στο: hev_llama_lora/")