import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise ValueError("HF_TOKEN not found in .env")

API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"

headers = {
    "Authorization": f"Bearer {HF_TOKEN}"
}


def generate_image(prompt: str) -> bytes:
    """
    Generates an image using FLUX model and returns raw image bytes.
    """

    payload = {
        "inputs": prompt
    }

    response = requests.post(API_URL, headers=headers, json=payload)

    # Handle model loading (503)
    if response.status_code == 503:
        try:
            wait_time = response.json().get("estimated_time", 10)
            time.sleep(wait_time)
            return generate_image(prompt)
        except Exception:
            time.sleep(10)
            return generate_image(prompt)

    # Success
    if response.status_code == 200:
        return response.content

    # Failure
    raise Exception(f"Image generation failed: {response.status_code} - {response.text}")