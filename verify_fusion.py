import py_compile
import os

files_to_check = [
    'engagement_fusion.py',
    'app_enhanced_fixed.py'
]

passed = True
for f in files_to_check:
    print(f"Checking {f}...")
    try:
        py_compile.compile(f, doraise=True)
        print(f"✅ {f} passed.")
    except Exception as e:
        print(f"❌ {f} failed: {e}")
        passed = False

if passed:
    print("\nAll syntax checks passed! 🚀")
else:
    exit(1)
