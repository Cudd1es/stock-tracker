from dotenv import load_dotenv
import os
from openai import OpenAI

# load llm api key in .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)

def ask_llm(prompt: str, model: str = "gpt-4o") -> str:
    """
    send prompt to openai model and return its output
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a professional stock-tracking assistant."},
                {"role": "user", "content": prompt}
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM Error] {e}")
        return ""

