# list_gemini_models.py
"""Script để list các Gemini models hiện available."""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("📋 Available Gemini models for your account:\n")
for model in client.models.list():
    if "generateContent" in model.supported_actions:
        # Cắt bỏ prefix "models/"
        name = model.name.replace("models/", "")
        print(f"  • {name}")
