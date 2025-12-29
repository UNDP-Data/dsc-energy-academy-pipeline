import os
from dotenv import load_dotenv
from azure.storage.blob import ContainerClient

# Load environment variables
load_dotenv()

sas_url = os.getenv("SAS_URL")
if not sas_url:
    raise ValueError("SAS_URL not found in .env file")

# Connect to the container with SAS URL
container_client = ContainerClient.from_container_url(sas_url)

# Just list all blobs under AI_Avatars/
print("📂 Listing contents in 'AI_Avatars/' folder:")
for blob in container_client.list_blobs(name_starts_with="AI_Avatars/"):
    print(f"- {blob.name}")
