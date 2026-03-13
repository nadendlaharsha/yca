import py_compile
try:
    py_compile.compile('d:/babu/app_enhanced_fixed.py', doraise=True)
    print("Syntax checks passed.")
except py_compile.PyCompileError as e:
    print(f"Syntax error: {e}")
except Exception as e:
    print(f"Error: {e}")
