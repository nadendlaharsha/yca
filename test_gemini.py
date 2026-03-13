
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

print(f"Testing Gemini API with key: {api_key[:5]}...")

try:
    model = genai.GenerativeModel("gemini-1.5-flash") # Try explicit model name first
    response = model.generate_content("Hello, can you hear me?")
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"Error with gemini-1.5-flash: {e}")

try:
    model = genai.GenerativeModel("gemini-flash-latest") # Try the alias used in app
    response = model.generate_content("Hello, can you hear me?")
    print(f"Success with alias! Response: {response.text}")
except Exception as e:
    print(f"Error with gemini-flash-latest: {e}")
