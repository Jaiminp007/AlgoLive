
import os
from dotenv import load_dotenv
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

# Load environment variables
load_dotenv()

token = os.getenv("GITHUB_TOKEN")
if not token:
    print("Error: GITHUB_TOKEN not found in environment")
    exit(1)

endpoint = "https://models.github.ai/inference"

models_to_test = [
    "meta/Llama-3.1-8B-Instruct",
    "microsoft/Phi-4",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "openai/gpt-4o-mini" # Test one again just to be sure
]

print(f"Testing GitHub Token: {token[:4]}...{token[-4:]}")

for model_name in models_to_test:
    print(f"\nTesting model: {model_name}...")
    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
        )

        response = client.complete(
            messages=[
                SystemMessage(content="You are a helpful assistant."),
                UserMessage(content="Test message. Reply with 'OK'.")
            ],
            model=model_name
        )

        print(f"✅ Success! Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ Failed: {e}")
