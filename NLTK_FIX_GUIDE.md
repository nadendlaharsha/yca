# 🔧 NLTK Error Fix Guide

## The Error You're Seeing

```
zipfile.BadZipFile: File is not a zip file
```

This happens when NLTK data files get corrupted during download.

---

## ✅ SOLUTION - 3 Methods

### Method 1: Use the Fix Script (EASIEST)

```bash
python fix_nltk.py
```

This will:
1. Clear corrupted NLTK data
2. Re-download required packages
3. Test the installation

---

### Method 2: Manual NLTK Download

**Step 1: Clear corrupted data**
```bash
# Windows
rmdir /s "%USERPROFILE%\nltk_data"

# Mac/Linux
rm -rf ~/nltk_data
```

**Step 2: Download NLTK data**
```bash
python -m nltk.downloader punkt
python -m nltk.downloader stopwords
```

**Step 3: Verify**
```python
python -c "from nltk.tokenize import sent_tokenize; print(sent_tokenize('Test.'))"
```

---

### Method 3: Use the Fixed App (NO NLTK NEEDED)

The file `app_enhanced_fixed.py` has built-in fallbacks and will work even if NLTK fails.

```bash
streamlit run app_enhanced_fixed.py
```

Features:
- ✅ Auto-downloads NLTK data on first run
- ✅ Falls back to simple tokenizer if NLTK fails
- ✅ Shows clear error messages
- ✅ Works without database (optional login)

---

## 📋 Step-by-Step Fix

### For Windows Users:

1. **Open Command Prompt as Administrator**

2. **Navigate to your project folder**
   ```cmd
   cd D:\projectwork\files (7)
   ```

3. **Run the fix script**
   ```cmd
   python fix_nltk.py
   ```

4. **When prompted, type 'y' to clear old data**

5. **Wait for downloads to complete**

6. **Run the app**
   ```cmd
   streamlit run app_enhanced_fixed.py
   ```

---

### For Mac/Linux Users:

1. **Open Terminal**

2. **Navigate to project folder**
   ```bash
   cd /path/to/your/project
   ```

3. **Run fix script**
   ```bash
   python3 fix_nltk.py
   ```

4. **Run the app**
   ```bash
   streamlit run app_enhanced_fixed.py
   ```

---

## 🔍 What Each File Does

| File | Purpose |
|------|---------|
| `app_enhanced_fixed.py` | Main app with NLTK error handling |
| `fix_nltk.py` | Script to fix NLTK data issues |
| `requirements_enhanced.txt` | All Python dependencies |

---

## 🐛 Still Having Issues?

### Error: "ModuleNotFoundError: No module named 'nltk'"
**Solution:**
```bash
pip install nltk
```

### Error: "Permission denied"
**Solution (Windows):** Run Command Prompt as Administrator  
**Solution (Mac/Linux):** Use `sudo` or change file permissions

### Error: "Cannot connect to database"
**Solution:** Database is optional! Just click "Continue without login" button

### Error: "GOOGLE_API_KEY not found"
**Solution:** Create `.env` file with:
```
GOOGLE_API_KEY=your_api_key_here
```

---

## ✨ Quick Test

After fixing, test if NLTK works:

```python
python -c "import nltk; from nltk.tokenize import sent_tokenize; print('✓ NLTK working!')"
```

Should output: `✓ NLTK working!`

---

## 📁 File Locations

### NLTK Data Location:
- **Windows:** `C:\Users\YourName\nltk_data\`
- **Mac/Linux:** `~/nltk_data/`

### If you need to manually delete:
1. Go to the location above
2. Delete the entire `nltk_data` folder
3. Run `python fix_nltk.py` again

---

## 🎯 Recommended Workflow

```
1. pip install -r requirements_enhanced.txt
   ↓
2. python fix_nltk.py
   ↓
3. Create .env file (add GOOGLE_API_KEY)
   ↓
4. streamlit run app_enhanced_fixed.py
   ↓
5. Click "Continue without login" (if no database)
   ↓
6. Start using the app!
```

---

## 💡 Why This Happens

NLTK downloads data files as ZIP archives. Sometimes:
- Download gets interrupted
- File gets corrupted
- Disk space runs out
- Permissions are wrong

The fix script clears these corrupted files and re-downloads them properly.

---

## 🆘 Last Resort

If nothing works, the app has a fallback mode that works without NLTK:

1. Run `app_enhanced_fixed.py`
2. The app will use a simple sentence tokenizer instead
3. TextRank will still work, just slightly less accurate

You'll see this message:
```
⚠️ NLTK not fully loaded. TextRank may have reduced accuracy.
```

But the app will still function!

---

## ✅ Success Checklist

After fixing, you should see:

- [✓] No more "BadZipFile" errors
- [✓] App starts successfully
- [✓] Can select TextRank method
- [✓] TextRank produces summaries
- [✓] PCA metrics display in sidebar

---

## 📞 Still Stuck?

Check these in order:

1. **Python version:** Should be 3.8 or higher
   ```bash
   python --version
   ```

2. **All packages installed:**
   ```bash
   pip list | grep -E "nltk|streamlit|scikit-learn"
   ```

3. **NLTK data exists:**
   ```bash
   # Windows
   dir %USERPROFILE%\nltk_data
   
   # Mac/Linux
   ls ~/nltk_data
   ```

4. **Run fix script:**
   ```bash
   python fix_nltk.py
   ```

---

**Remember:** The `app_enhanced_fixed.py` file is specifically designed to handle NLTK errors gracefully. Use this version instead of the original!
