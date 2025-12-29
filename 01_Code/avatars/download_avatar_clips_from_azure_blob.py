import os
from dotenv import load_dotenv
from azure.storage.blob import ContainerClient

# Load environment variables
load_dotenv()

sas_url = os.getenv("SAS_URL")
if not sas_url:
    raise ValueError("SAS_URL not found in .env file")

# Connect to the container using SAS URL
container_client = ContainerClient.from_container_url(sas_url)

# Define local download path
download_folder = os.path.join("..", "..", "03_Outputs", "avatars", "downloads")
os.makedirs(download_folder, exist_ok=True)

# Define video extensions to download
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm")

print("📥 Downloading video files from 'AI_Avatars/' folder...\n")

# List and download all video blobs
for blob in container_client.list_blobs(name_starts_with="AI_Avatars/"):
    if blob.name.lower().endswith(VIDEO_EXTENSIONS):
        blob_name = blob.name.split("/")[-1]  # Get file name only
        local_path = os.path.join(download_folder, blob_name)

        # Skip if file already exists
        if os.path.exists(local_path):
            print(f"✅ Skipping (already exists): {blob_name}")
            continue

        print(f"⬇️  Downloading: {blob_name} ...")

        # Download blob content
        blob_client = container_client.get_blob_client(blob)
        with open(local_path, "wb") as file:
            data = blob_client.download_blob()
            file.write(data.readall())

        print(f"   ✔️ Saved to: {local_path}")

print("\n🎉 All video downloads complete!")
