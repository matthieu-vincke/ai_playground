import serpapi
import os
import serpapi
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

client = serpapi.Client(api_key=os.getenv("SERP_API_KEY"))

s = client.search(
    q="Coffee",
    engine="google_light",
    location="London, England, United Kingdom",
    hl="en",
    gl="uk"
)

print(s)
