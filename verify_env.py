
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    print(f"GOOGLE_API_KEY found: {api_key[:5]}...{api_key[-5:]}")
else:
    print("GOOGLE_API_KEY not found or empty.")
