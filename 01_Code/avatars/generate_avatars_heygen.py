# Project setup
## Import dependencies
import pandas as pd
import requests
import json
import copy
import time
import requests
import os
from dotenv import load_dotenv

import ssl
import aiohttp
import asyncio
from azure.storage.blob.aio import ContainerClient
from azure.storage.blob import ContentSettings
from azure.core.pipeline.transport import AioHttpTransport

from docx import Document

USE_INSECURE_SSL = False
SAS_URL = None

def get_avatars(api_key, output_path):
    url = "https://api.heygen.com/v2/avatars"
    headers = {
        "accept": "application/json",
        "x-api-key": api_key
    }

    response = requests.get(url, headers=headers)
    print("Avatars Response Status Code:", response.status_code)

    if response.status_code == 200:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response.json(), f, indent=4)
        print(f"Avatars JSON saved to: {output_path}")
    else:
        print("Failed to fetch avatars.")
        print("Response:", response.text)

def get_voices(api_key, output_path):
    url = "https://api.heygen.com/v2/voices"
    headers = {
        "Accept": "application/json",
        "X-Api-Key": api_key
    }

    response = requests.get(url, headers=headers)
    print("Voices Response Status Code:", response.status_code)

    if response.status_code == 200:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response.json(), f, indent=4)
        print(f"Voices JSON saved to: {output_path}")
    else:
        print("Failed to fetch voices.")
        print("Response:", response.text)

def get_locales(api_key, output_path):
    url = "https://api.heygen.com/v2/voices/locales"
    headers = {
        "Accept": "application/json",
        "X-Api-Key": api_key
    }

    response = requests.get(url, headers=headers)
    print("Locales Response Status Code:", response.status_code)

    if response.status_code == 200:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(response.json(), f, indent=4)
        print(f"Locales JSON saved to: {output_path}")
    else:
        print("Failed to fetch locales.")
        print("Response:", response.text)

def get_assets(api_key, output_path, file_type=None, folder_id=None):
    """
    Fetch all assets from HeyGen API and save to a JSON file.

    Args:
        api_key (str): HeyGen API key (Bearer token)
        output_path (str): Path to save the JSON response
        file_type (str, optional): Filter by file type ('image', 'video', 'audio', etc.)
        folder_id (str, optional): Filter assets by folder ID
    """
    BASE_URL = "https://api.heygen.com/v1/asset/list"
    headers = {"Authorization": f"Bearer {api_key}"}
    all_assets = []
    token = None

    while True:
        params = {"limit": 100}
        if file_type:
            params["file_type"] = file_type
        if folder_id:
            params["folder_id"] = folder_id
        if token:
            params["token"] = token

        response = requests.get(BASE_URL, headers=headers, params=params)
        print("Assets Response Status Code:", response.status_code)

        if response.status_code != 200:
            print("Failed to fetch assets.")
            print("Response:", response.text)
            break

        data = response.json().get("data", {})
        assets = data.get("assets", [])
        all_assets.extend(assets)

        token = data.get("token")
        if not token:  # No more pages
            break

    # Save all fetched assets to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_assets, f, indent=4)

    print(f"Assets JSON saved to: {output_path}")
    print(f"Total assets fetched: {len(all_assets)}")


def load_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON - {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return None

def load_payload_template(template_path):
    with open(template_path, 'r') as f:
        return json.load(f)
    


def load_script(row, path_scripts):
    """
    Loads the script text from a Word document corresponding to the lesson.

    Args:
        row (pd.Series): A row from the dataframe.
        path_scripts (str): Base folder containing all modules.

    Returns:
        str: The extracted text from the Word document.
    """
    # Build the file path
    module_folder = f"Module {row['Lesson'][0]}"
    file_name = f"{row['Lesson']}-{row['Language']}_{row['Part']}.docx"
    file_path = os.path.join(path_scripts, module_folder, file_name)

    if not os.path.exists(file_path):
        #raise FileNotFoundError(f"Script file not found: {file_path}")
        #print("[WARN]: No script file found!")
        script_text = "NO SCRIPT FOUND"
        return script_text
    # Read the Word document
    doc = Document(file_path)
    script_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

    return script_text


def generate_heygen_video(api_key: str, item: dict) -> dict:

    url = "https://api.heygen.com/v2/video/generate"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }

    lesson_id = item.get("lesson", "unknown")
    language = item.get("language", "unknown")
    part = item.get("part", "unknown")
    payload = item.get("payload", {})

    log_prefix = f"Lesson [{lesson_id}] | Language [{language}] | Part [{part}]"
    print(f"\n▶️ Processing {log_prefix}...")

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()

        if response_data.get("error") is None:
            video_id = response_data.get("data", {}).get("video_id")
            if video_id:
                print(f"✅ Success for {log_prefix}: Video ID = {video_id}")
                return {
                    "lesson": lesson_id,
                    "language": language,
                    "part": part,
                    "video_id": video_id
                }
            else:
                print(f"❌ No video_id returned for {log_prefix}.")
                return {
                    "lesson": lesson_id,
                    "language": language,
                    "part": part,
                    "error": "No video_id in response"
                }
        else:
            error_message = response_data.get("error", "Unknown API error")
            print(f"❌ API error for {log_prefix}: {error_message}")
            return {
                "lesson": lesson_id,
                "language": language,
                "part": part,
                "error": error_message
            }

    except requests.exceptions.RequestException as e:
        print(f"❌ Request exception for {log_prefix}: {e}")
        return {
            "lesson": lesson_id,
            "language": language,
            "part": part,
            "error": str(e)
        }
    except ValueError:
        print(f"❌ JSON parsing error for {log_prefix}")
        return {
            "lesson": lesson_id,
            "language": language,
            "part": part,
            "error": "Invalid JSON response"
        }


def generate_heygen_video_dummy(api_key: str, item: dict) -> dict:
    lesson_id = item.get("lesson", "unknown")
    language = item.get("language", "unknown")
    part = item.get("part", "unknown")
    log_prefix = f"Lesson [{lesson_id}] | Language [{language}] | Part [{part}]"

    fake_video_id = '022a93e92ff64e4bacd970ae2159c3a1'  # Example fixed ID for testing
    print(f"\n▶️ (Dummy) Processing {log_prefix}...")
    print(f"✅ (Dummy) Success for {log_prefix}: Video ID = {fake_video_id}")

    return {
        "lesson": lesson_id,
        "language": language,
        "part": part,
        "video_id": fake_video_id
    }





def wait_for_video_completion(api_key: str, video_id: str, poll_interval: int = 60, max_retries: int = 30) -> dict:
    """
    Polls the HeyGen API every poll_interval seconds until the video status is 'completed',
    or returns error/times out based on updated HeyGen response format.

    Parameters:
        api_key (str): Your HeyGen API key.
        video_id (str): The ID of the video to monitor.
        poll_interval (int): Time (in seconds) between polling attempts.
        max_retries (int): Maximum number of polling attempts.

    Returns:
        dict: {
            "status": "completed" | "processing" | "failed" | "timeout",
            "video_url": str (if completed),
            "error": str (if failed or timeout)
        }
    """
    url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json"
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            json_response = response.json()

            code = json_response.get("code")
            data = json_response.get("data", {})
            status = data.get("status")
            error_info = data.get("error")

            print(f"[Attempt {attempt}] Video ID {video_id} status: {status}")

            if status == "completed":
                video_url = data.get("video_url")
                print(f"✅ Video completed! URL: {video_url}")
                return {
                    "status": "completed",
                    "video_url": video_url
                }

            elif status == "failed":
                error_message = error_info.get("message") if isinstance(error_info, dict) else "Unknown failure reason"
                print(f"❌ Video generation failed: {error_message}")
                return {
                    "status": "failed",
                    "error": error_message
                }

            elif status in {"pending", "waiting", "processing"}:
                print(f"⏳ Video still {status}. Waiting {poll_interval} seconds before retry...")
                time.sleep(poll_interval)

            else:
                print(f"⚠️ Unexpected status '{status}' for video ID {video_id}. Waiting before retry...")
                time.sleep(poll_interval)

        except requests.exceptions.RequestException as e:
            print(f"❌ Request error while checking video status: {e}")
            return {"status": "failed", "error": str(e)}

        except ValueError:
            print("❌ Failed to parse JSON response.")
            return {"status": "failed", "error": "Invalid JSON response"}

    # Timeout condition
    print(f"⚠️ Timeout: Video ID {video_id} did not complete after {max_retries} attempts.")
    return {"status": "timeout", "error": "Video generation timed out."}

def download_heygen_video(video_url: str, output_folder: str, lesson: str, language: str, part: str) -> bool:
    """
    Downloads the HeyGen video and saves it using lesson and language as filename.

    Parameters:
        video_url (str): The direct download URL for the video.
        output_folder (str): The folder path where the video should be saved.
        lesson (str): The lesson identifier used in the filename.
        language (str): The language identifier used in the filename.

    Returns:
        bool: True if download succeeds, False otherwise.
    """
    # Ensure output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Construct filename and full path
    safe_lesson = lesson.replace(" ", "_").replace("/", "-")
    safe_language = language.replace(" ", "_")
    filename = f"Lesson-{safe_lesson}_{safe_language}_{part}.mp4"
    output_path = os.path.join(output_folder, filename)

    print(f"⬇️ Downloading to: {output_path}")

    try:
        with requests.get(video_url, stream=True) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        print(f"✅ Download complete: {output_path}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Download failed: {e}")
        return False

def get_container_client():
    if not SAS_URL:
        raise ValueError("SAS_URL not configured")
    if USE_INSECURE_SSL:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        transport = AioHttpTransport(ssl_context=ssl_context)
        return ContainerClient.from_container_url(SAS_URL, transport=transport)
    return ContainerClient.from_container_url(SAS_URL)

async def upload_video_to_azure(video_url: str, blob_name: str) -> str:
    """
    Downloads video from HeyGen and uploads directly to Azure blob storage.
    
    Parameters:
        video_url (str): The direct download URL for the video from HeyGen
        blob_name (str): The blob name/path in Azure storage
    
    Returns:
        str: The Azure blob URL if successful, empty string if failed
    """
    print(f"⬇️ Downloading and uploading to Azure: {blob_name}")
    
    try:
        # Download video content
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url, timeout=300) as response:
                if response.status == 200:
                    video_data = await response.read()
                    
                    # Upload to Azure
                    async with get_container_client() as client:
                        blob = client.get_blob_client(blob_name)
                        await blob.upload_blob(
                            data=video_data,
                            overwrite=True,
                            content_settings=ContentSettings(content_type="video/mp4"),
                        )
                        azure_url = blob.url.split("?")[0]
                        print(f"✅ Upload complete: {azure_url}")
                        return azure_url
                else:
                    print(f"❌ Failed to download video: HTTP {response.status}")
                    return ""
                    
    except Exception as e:
        print(f"❌ Upload to Azure failed: {e}")
        return ""

def format_video_blob_name(lesson: str, language: str, part: str) -> str:
    """Format the blob name for the video file"""
    safe_lesson = lesson.replace(" ", "_").replace("/", "-")
    safe_language = language.replace(" ", "_")
    return f"AI_Avatars/Lesson-{safe_lesson}_{safe_language}_{part}.mp4"

async def download_and_upload_video(video_url: str, lesson: str, language: str, part: str) -> bool:
    """
    Downloads video from HeyGen and uploads directly to Azure blob storage.
    
    Parameters:
        video_url (str): The direct download URL for the video
        lesson (str): The lesson identifier
        language (str): The language identifier
    
    Returns:
        bool: True if upload succeeds, False otherwise
    """
    blob_name = format_video_blob_name(lesson, language, part)
    azure_url = await upload_video_to_azure(video_url, blob_name)
    return bool(azure_url)

def save_payloads(payloads, folder):
    """
    Save each payload as a separate JSON file in the specified folder.
    Prints a message for each saved payload including lesson and language.
    """

    os.makedirs(folder, exist_ok=True)

    for i, item in enumerate(payloads, start=1):
        lesson = str(item.get("lesson", f"lesson_{i}")).replace(" ", "_")
        language = str(item.get("language", "unknown")).replace(" ", "_")
        part = str(item.get("part", "unknown")).replace(" ", "_")
        filename = f"{lesson}_{language}_{part}.json"
        filepath = os.path.join(folder, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(item["payload"], f, ensure_ascii=False, indent=2)

        # Print lesson, language, and filepath
        print(f"💾 Saved payload for Lesson: '{lesson}', Language: '{language}', Part: '{part}' → {filepath}")
def load_payloads(folder):
    """
    Load payloads from JSON files in the specified folder.
    Reconstructs objects with lesson, language, part, and payload keys.
    """
    payloads = []
    for file in os.listdir(folder):
        if file.endswith(".json"):
            filepath = os.path.join(folder, file)
            
            # Split filename into lesson, language, and part
            name, _ = os.path.splitext(file)
            parts = name.split("_", 2)  # lesson, language, part (allow underscores in part)
            if len(parts) == 3:
                lesson, language, part = parts
            else:
                lesson, language, part = parts[0], "unknown", "unknown"
            
            with open(filepath, "r", encoding="utf-8") as f:
                payload = json.load(f)
            
            payloads.append({
                "lesson": lesson,
                "language": language,
                "part": part,
                "payload": payload
            })
    return payloads

async def main():
    global SAS_URL
    load_dotenv("../.env")
    api_key = os.getenv("HEYGEN_API_KEY")
    SAS_URL = os.getenv("SAS_URL")
    
    # Validate required environment variables
    if not api_key:
        raise EnvironmentError("❌ Missing HEYGEN_API_KEY")
    if not SAS_URL:
        raise EnvironmentError("❌ Missing SAS_URL")

    # Define paths (remove video_output_path since we're not storing locally)
    path_dataset = "../../02_Inputs/avatars/Avatars.xlsx"
    path_payload_storage = "../../03_Outputs/avatars/payloads"


    # Load the dataset
    df = pd.read_excel(path_dataset, engine='openpyxl')


    payloads = load_payloads(path_payload_storage)
    print(f"Total payloads loaded: {len(payloads)}")
    
    for payload in payloads:
        lesson = payload['lesson']
        language = payload['language']
        part = str(payload['part'])

        print(f"Generating video for lesson: {lesson}, language: {language}, part: {part}")

        # Check if this lesson/language is already generated
        mask = (df['Lesson'] == lesson) & (df['Language'] == language) & (df['Part'].astype(str) == str(part))
        if not df.loc[mask].empty and (df.loc[mask, 'Status'] == 'generated').any():
            print(f"Skipping already processed lesson: {lesson}, language: {language}")
            continue

        # Call the HeyGen API to generate the video
        video_result = generate_heygen_video(api_key, payload)
        if 'error' in video_result:
            print(f"Failed to generate video for lesson: {lesson}, language: {language}, part: {part}")
            print(f"Error: {video_result['error']}")
            continue

        elif 'video_id' in video_result:
            # Wait for video completion
            status = wait_for_video_completion(api_key, video_result['video_id'], poll_interval=30, max_retries=120)

            if status.get("status") == "completed": 
                print(f"Video completed successfully for lesson: {lesson}, language: {language}, part: {part}")

                # Upload directly to Azure
                upload_successful = await download_and_upload_video(
                    video_url=status['video_url'],
                    lesson=lesson,
                    language=language,
                    part = part
                )

                if upload_successful:
                    print("🎉 Video successfully uploaded to Azure.")
                    # Update the DataFrame status to "generated" for this lesson and language
                    df.loc[(df['Lesson'] == lesson) & (df['Language'] == language)& (df['Part'].astype(str) == str(part)), 'Status'] = 'generated'
                    
                    # Save the updated DataFrame to Excel file
                    df.to_excel(path_dataset, index=False)
                else:
                    print("⚠️ Video upload to Azure failed.")
            else:
                print(f"Video generation failed for lesson: {lesson}, language: {language}, part: {part}")
                print(f"Error: {status.get('error', 'Unknown error')}")
        else:
            print(f"Failed to get video_id for lesson: {lesson}, language: {language}, part: {part}")
            print(f"Error: {video_result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(main())  # Use asyncio.run instead of calling main() directly