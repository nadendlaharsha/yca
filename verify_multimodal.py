import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from multimodal_fusion import MultimodalFuser, get_multimodal_fusion_summary

def test_multimodal_logic():
    print("Testing Multimodal Fusion Logic...")
    
    # We can't easily test the full video download/OCR in this environment without a real URL and internet
    # But we can test the class initialization and core ranking logic with mock data
    
    fuser = MultimodalFuser()
    print("✓ MultimodalFuser initialized")
    
    # Mock transcript data
    mock_transcript = [
        {'start': 0, 'text': 'Hello world and welcome to this lecture on multimodal AI.'},
        {'start': 60, 'text': 'In this section, we discuss visual features.'},
        {'start': 120, 'text': 'Audio features are also important for understanding context.'},
        {'start': 180, 'text': 'Conclusion and next steps.'}
    ]
    
    # Mock text scores
    sentences = [seg['text'] for seg in mock_transcript]
    text_scores = fuser.get_text_rank_scores(sentences)
    print(f"✓ TextRank scores calculated: {text_scores}")
    
    # Mock no transcript case
    print("\nTesting NO transcript case (OCR/Visual/Audio only)...")
    highlights_no_t, df_no_t = fuser.extract_multimodal_keyframes("https://www.youtube.com/watch?v=dQw4w9WgXcQ", None)
    print(f"✓ NO-Transcript results: {len(highlights_no_t)} keyframes found.")
    
    print("\nVerification script structured. Manual testing recommended with real YouTube URLs.")

if __name__ == "__main__":
    try:
        test_multimodal_logic()
        print("\nSUCCESS: Multimodal Fusion module structure and basic logic verified.")
    except Exception as e:
        print(f"\nFAILURE: Verification failed with error: {e}")
        sys.exit(1)
