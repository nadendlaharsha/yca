"""
NLTK Data Downloader and Fixer
Run this script to download and fix NLTK data issues
"""

import nltk
import os
import shutil
import sys

def clear_nltk_data():
    """Clear potentially corrupted NLTK data"""
    nltk_data_dir = os.path.join(os.path.expanduser('~'), 'nltk_data')
    
    print(f"NLTK data directory: {nltk_data_dir}")
    
    if os.path.exists(nltk_data_dir):
        response = input(f"Clear existing NLTK data at {nltk_data_dir}? (y/n): ")
        if response.lower() == 'y':
            print("Removing old NLTK data...")
            try:
                shutil.rmtree(nltk_data_dir)
                print("✓ Old data removed")
            except Exception as e:
                print(f"Error removing data: {e}")
                print("Try manually deleting:", nltk_data_dir)

def download_nltk_data():
    """Download required NLTK data packages"""
    print("\n" + "="*60)
    print("Downloading NLTK Data")
    print("="*60 + "\n")
    
    packages = ['punkt', 'stopwords']
    
    for package in packages:
        print(f"\nDownloading {package}...")
        try:
            nltk.download(package, quiet=False)
            print(f"✓ {package} downloaded successfully")
        except Exception as e:
            print(f"✗ Error downloading {package}: {e}")
            print(f"  Try: python -m nltk.downloader {package}")
    
    print("\n" + "="*60)
    print("Testing NLTK")
    print("="*60 + "\n")
    
    # Test punkt
    try:
        from nltk.tokenize import sent_tokenize
        result = sent_tokenize("This is a test. This is another sentence.")
        print(f"✓ Punkt tokenizer working: {result}")
    except Exception as e:
        print(f"✗ Punkt tokenizer failed: {e}")
    
    # Test stopwords
    try:
        from nltk.corpus import stopwords
        stops = stopwords.words('english')
        print(f"✓ Stopwords loaded: {len(stops)} words")
    except Exception as e:
        print(f"✗ Stopwords failed: {e}")
    
    print("\n" + "="*60)
    print("NLTK Setup Complete!")
    print("="*60 + "\n")

def main():
    print("="*60)
    print("NLTK Data Setup and Fix Tool")
    print("="*60 + "\n")
    
    print("This script will:")
    print("1. Optionally clear corrupted NLTK data")
    print("2. Download required packages (punkt, stopwords)")
    print("3. Test the installation")
    print()
    
    # Check if NLTK is installed
    try:
        import nltk
        print(f"✓ NLTK version: {nltk.__version__}")
    except ImportError:
        print("✗ NLTK not installed")
        print("  Run: pip install nltk")
        sys.exit(1)
    
    print()
    
    # Ask if user wants to clear existing data
    clear_nltk_data()
    
    # Download data
    download_nltk_data()
    
    print("\nYou can now run your Streamlit app!")
    print("Command: streamlit run app_enhanced_fixed.py")

if __name__ == "__main__":
    main()
