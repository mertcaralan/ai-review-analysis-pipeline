import requests
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Test the setup
print("✅ Packages imported successfully!")

# Test environment variable
api_key = os.environ.get("API_KEY", "not-set")
print(f"✅ API_KEY: {api_key}")

# Test requests
response = requests.get("https://api.github.com")
print(f"✅ GitHub API status: {response.status_code}")
