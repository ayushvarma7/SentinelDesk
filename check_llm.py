import os
from google import genai
from config import LLM_MODEL

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
names = [m.name for m in client.models.list()]
print("flash models:", [n for n in names if "flash" in n][:15])
r = client.models.generate_content(model=LLM_MODEL, contents='Reply with exactly this JSON: {"ok": true}',
                                   config={"response_mime_type": "application/json"})
print(LLM_MODEL, "->", r.text)
