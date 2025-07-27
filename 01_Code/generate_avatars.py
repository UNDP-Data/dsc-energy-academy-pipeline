# Project setup
## Import dependencies
import pandas as pd
import requests
import json
import copy
import hashlib
import time
import requests
import os

from dotenv import load_dotenv
load_dotenv(".env")
api_key=os.getenv("HEYGEN_API_KEY")


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

def generate_video_payloads_from_template(df, avatars_json, voices_json, locales_json, template):
    avatars = avatars_json['data']['avatars']
    voices = voices_json['data']['voices']
    locales = locales_json['data']['locales']

    def find_avatar_id(name):
        for avatar in avatars:
            if avatar['avatar_name'].lower() == name.lower():
                return avatar['avatar_id']
        return None

    def find_voice_id(voice_name, language, gender):
        for voice in voices:
            if voice_name.strip().lower() == voice['name'].strip().lower():
                return voice['voice_id']
        return None
    
    def find_locale_id(accent):
        for locale in locales:
            if locale['value'].lower() == accent.lower():
                return locale['locale']
        return None
    

    payloads = []

    for _, row in df.iterrows():
        print(f"Processing row: {row['Lesson']}")
        voice_id = find_voice_id(row['Voice'], row['Language'], row['Gender'])
        avatar_id = find_avatar_id(row['Name'])
        if row['Accent'] != "Original":
            locales_id = find_locale_id(row['Accent'])
        else:
            locales_id = "Original"

        if not avatar_id:
            print(f"[WARN] Avatar ID not found for: {row['Name']}")

        if not voice_id:
            print(f"[WARN] Voice ID not found for: {row['Voice']}")

        if not locales_id:
            print(f"[WARN] Locale ID not found for: {row['Accent']}")

        script_text = row['Script']
        if not isinstance(script_text, str) or len(script_text.strip()) == 0:
            print(f"[WARN] Empty or invalid script for row {row}")

        if len(script_text) > 1500:
            print(f"[WARN] Script too long (>1500 chars).")

        if not avatar_id or not voice_id or not script_text or not locales_id or len(script_text) > 1500:
            continue

        payload = copy.deepcopy(template)

        # Replace placeholders
        payload['video_inputs'][0]['character']['avatar_id'] = avatar_id
        payload['video_inputs'][0]['voice']['voice_id'] = voice_id
        payload['video_inputs'][0]['voice']['input_text'] = script_text
        if not locales_id == "Original":
            payload['video_inputs'][0]['voice']['locale'] = locales_id 
  

        payloads.append({
            "lesson": row['Lesson'],
            "language": row['Language'],
            "payload": payload
        })

    return payloads



def generate_heygen_video(api_key: str, item: dict) -> dict:

    url = "https://api.heygen.com/v2/video/generate"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }

    lesson_id = item.get("lesson", "unknown")
    language = item.get("language", "unknown")
    payload = item.get("payload", {})

    log_prefix = f"Lesson [{lesson_id}] | Language [{language}]"
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
                    "video_id": video_id
                }
            else:
                print(f"❌ No video_id returned for {log_prefix}.")
                return {
                    "lesson": lesson_id,
                    "language": language,
                    "error": "No video_id in response"
                }
        else:
            error_message = response_data.get("error", "Unknown API error")
            print(f"❌ API error for {log_prefix}: {error_message}")
            return {
                "lesson": lesson_id,
                "language": language,
                "error": error_message
            }

    except requests.exceptions.RequestException as e:
        print(f"❌ Request exception for {log_prefix}: {e}")
        return {
            "lesson": lesson_id,
            "language": language,
            "error": str(e)
        }
    except ValueError:
        print(f"❌ JSON parsing error for {log_prefix}")
        return {
            "lesson": lesson_id,
            "language": language,
            "error": "Invalid JSON response"
        }


def generate_heygen_video_dummy(api_key: str, item: dict) -> dict:
    lesson_id = item.get("lesson", "unknown")
    language = item.get("language", "unknown")
    log_prefix = f"Lesson [{lesson_id}] | Language [{language}]"

    # Deterministic fake video_id using hash
    hash_input = f"{lesson_id}_{language}".encode()
    #fake_video_id = hashlib.md5(hash_input).hexdigest()
    fake_video_id = '022a93e92ff64e4bacd970ae2159c3a1'  # Example fixed ID for testing
    print(f"\n▶️ (Dummy) Processing {log_prefix}...")
    print(f"✅ (Dummy) Success for {log_prefix}: Video ID = {fake_video_id}")

    return {
        "lesson": lesson_id,
        "language": language,
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

def download_heygen_video(video_url: str, output_folder: str, lesson: str, language: str) -> bool:
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
    filename = f"Lesson-{safe_lesson}_{safe_language}.mp4"
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


def main():
    ## Define paths
    path_dataset = "../02_Inputs/avatars/Avatars.xlsx"
    path_api_key = "../02_Inputs/avatars/heygen-api-key.txt"
    path_avatars = "../02_Inputs/avatars/avatars.json"
    path_voices = "../02_Inputs/avatars/voices.json"
    path_locales = "../02_Inputs/avatars/locales.json"
    path_payload_template = "../02_Inputs/avatars/payload_template.json"
    video_output_path = "../03_Outputs/AI_Avatars"##this needs to be updated to directly push the video to the azure blob, so it isn't stored locally
    
    ## Load the dataset
    df = pd.read_excel(path_dataset, engine='openpyxl')

    # Fetch avatars and voices
    avatars = get_avatars(api_key, path_avatars)
    voices = get_voices(api_key, path_voices)
    locales = get_locales(api_key, path_locales)

    # Load the avatars and voices JSON files
    avatars_data = load_json_file(path_avatars)
    voices_data = load_json_file(path_voices)
    locales_data = load_json_file(path_locales)

    # Generate Video Gen Payload
    template = load_payload_template(path_payload_template)
    payloads = generate_video_payloads_from_template(df, avatars_data, voices_data, locales_data, template)
    print(json.dumps(payloads, indent=2))


    for payload in payloads:
        lesson = payload['lesson']
        language = payload['language']

        print(f"Generating video for lesson: {lesson}, language: {language}")


        # Check if this lesson/language is already generated
        mask = (df['Lesson'] == lesson) & (df['Language'] == language)
        if not df.loc[mask].empty and (df.loc[mask, 'Status'] == 'generated').any():
            print(f"Skipping already processed lesson: {lesson}, language: {language}")
            continue

        # Call the HeyGen API to generate the video
        video_id = generate_heygen_video(api_key, payload)

        # Check if video_id was returned successfully
        status = wait_for_video_completion(api_key, video_id['video_id'], poll_interval=60, max_retries=12)

        if status.get("status") == "completed": 
            print(f"Video completed successfully for lesson: {lesson}, language: {language}")

            download_successful = download_heygen_video(
                video_url=status['video_url'],
                output_folder=video_output_path,
                lesson=lesson,
                language=language
            )

            if download_successful:
                print("🎉 Video successfully downloaded.")
                # Update the DataFrame status to "generated" for this lesson and language
                df.loc[(df['Lesson'] == lesson) & (df['Language'] == language), 'Status'] = 'generated'
                
                # Save the updated DataFrame to an Excel file in the "test" directory
                df.to_excel(path_dataset, index=False)
            else:
                print("⚠️ Video download failed.")

        else:
            print(f"Video generation failed for lesson: {payload['lesson']}, language: {payload['language']}")
            print(f"Error: {status.get('error', 'Unknown error')}")

       
if __name__ == "__main__":
    main()
