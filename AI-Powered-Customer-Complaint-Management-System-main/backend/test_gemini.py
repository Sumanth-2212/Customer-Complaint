from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(
    api_key=os.getenv("AIzaSyAJezUFSZqyk_WghbkLj3VAdawN3tsFlEc")
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with exactly: Gemini is working!"
)

print(response.text)