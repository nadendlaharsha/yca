import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("No API key found in .env")
    exit()

genai.configure(api_key=api_key)

try:
    with open("models_list.txt", "w") as f:
        f.write("Available models:\n")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                f.write(f"- {m.name}\n")
    print("Models listed in models_list.txt")
except Exception as e:
    print(f"Error listing models: {e}")
