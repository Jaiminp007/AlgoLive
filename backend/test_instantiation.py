
print("Test: Importing Modules...")
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
print("Test: Imports Successful.")

print("Test: Loading Model...")
try:
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    print("Test: Model Loaded Successfully.")
except Exception as e:
    print(f"Test: Model Load Error: {e}")
