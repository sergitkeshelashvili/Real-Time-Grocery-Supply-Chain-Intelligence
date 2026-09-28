import os, sys, json
from dotenv import load_dotenv
load_dotenv()
from src.ai.prompt_analysis import analyze_prompt
try:
    print(analyze_prompt("Test"))
except Exception as e:
    import traceback; traceback.print_exc()
