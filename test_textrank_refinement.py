
import os
import google.generativeai as genai
from dotenv import load_dotenv
import streamlit as st

# Mock streamlit for testing
class MockSt:
    def error(self, msg): print(f"ST ERROR: {msg}")
    def warning(self, msg): print(f"ST WARNING: {msg}")
    def info(self, msg): print(f"ST INFO: {msg}")

st = MockSt()

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-flash-latest"

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

def call_gemini_safe(prompt):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None

def refine_textrank_summary(raw_summary):
    if not raw_summary or len(raw_summary.split()) < 10:
        return raw_summary
        
    try:
        refine_prompt = f"""
        Refine the following extractive summary into a professional, grammatically correct, and well-structured summary.
        
        RULES:
        1. Fix any grammar, punctuation, or capitalization issues.
        2. Maintain all key facts and insights from the original text.
        3. If the content is long, use bullet points for clarity.
        4. Ensure a smooth, logical flow between ideas.
        5. Keep the response concise but comprehensive.
        6. Do NOT add information not present in the original text.
        7. Output ONLY the refined text.
        
        Original Text:
        {raw_summary}
        
        Refined Summary:
        """
        
        refined_text = call_gemini_safe(refine_prompt)
        return refined_text if refined_text else raw_summary
    except Exception as e:
        print(f"Refinement error: {e}")
        return raw_summary

# Test Data
messy_summary = "so basically the code is working and we have a problem with the database it is not connecting and we need to fix it because if we dont then the app will crash and users will be unhappy so we should check the connection string and also the firewall settings which might be blocking it"

print("--- Testing Refinement ---")
print(f"Original: {messy_summary}\n")
refined = refine_textrank_summary(messy_summary)
print(f"Refined: {refined}")
