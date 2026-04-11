from dotenv import load_dotenv
import os
import requests
from PIL import Image, UnidentifiedImageError
import imagehash
import io
import csv
from datetime import datetime, timezone
from xml.etree import ElementTree
from tqdm import tqdm

load_dotenv()

BASE_URL = os.getenv("PIWIGO_BASE_URL")
USERNAME = os.getenv("PIWIGO_USERNAME")
PASSWORD = os.getenv("PIWIGO_PASSWORD")
REQUEST_TIMEOUT = 60
ATTEMPT_LOG_PATH = "attempt_log.csv"
OUTPUT_PATH = "output.csv"
RETRY_QUEUE_PATH = "retry_queue.csv"
SNAPSHOT_INTERVAL = 25
HASH_ALGORITHM = "crop_resistant_hash"
TARGET_CATEGORY_ID = 209
RUN_SCOPE = f"category:{TARGET_CATEGORY_ID}:recursive"

ATTEMPT_LOG_FIELDS = [
    "timestamp",
    "scope",
    "id",
    "status",
    "method",
    "hash_algorithm",
    "hash",
    "error_type",
    "error_detail",
    "next_action",
    "next_method",
]

session = requests.Session()


def parse_json_response(response):
    response.raise_for_status()
    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        body_preview = response.text.strip().replace("\n", " ")[:200]
        raise RuntimeError(
            f"Expected JSON response but got: {body_preview or '<empty body>'}"
        ) from exc
    if data.get("stat") != "ok":
        raise RuntimeError(
            f'Piwigo API error {data.get("err", "unknown")}: '
            f'{data.get("message", "unknown error")}'
        )
    return data


def ensure_api_success(response):
    response.raise_for_status()

    try:
        data = response.json()
    except requests.exceptions.JSONDecodeError:
        root = ElementTree.fromstring(response.text)
        if root.attrib.get("stat") != "ok":
            raise RuntimeError(f"Piwigo API error: {response.text.strip()[:200]}")
        return

    if data.get("stat") != "ok":
        raise RuntimeError(
            f'Piwigo API error {data.get("err", "unknown")}: '
            f'{data.get("message", "unknown error")}'
        )


def login():
    r = session.post(f"{BASE_URL}/ws.php", data={
        "method": "pwg.session.login",
        "username": USERNAME,
        "password": PASSWORD,
        "format": "json"
    }, timeout=REQUEST_TIMEOUT)
    ensure_api_success(r)
    print("Logged in")


def get_images():
    page = 0
    per_page = 500
    all_images = []
    while True:
        r = session.get(f"{BASE_URL}/ws.php", params={
            "method": "pwg.categories.getImages",
            "format": "json",
            "cat_id": TARGET_CATEGORY_ID,
            "recursive": "true",
            "per_page": per_page,
            "page": page
        }, timeout=REQUEST_TIMEOUT)
        data = parse_json_response(r)
        result = data["result"]
        images = result.get("images", [])
        if not images:
            break
        all_images.extend(images)
        total_count = result.get("paging", {}).get("total_count")
        if total_count is not None and len(all_images) >= total_count:
            break
        page += 1
    return all_images


def hash_image(url):
    r = session.get(url, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    return str(imagehash.crop_resistant_hash(img))


def get_fetch_candidates(image):
    seen_urls = set()
    candidates = []

    def add_candidate(method, url):
        if not url or url in seen_urls:
            return
        seen_urls.add(url)
        candidates.append((method, url))

    add_candidate("element_url", image.get("element_url"))
    add_candidate("download_url", image.get("download_url"))

    derivatives = image.get("derivatives", {})
    for name in ["xxlarge", "xlarge", "large", "medium", "small", "thumb"]:
        derivative = derivatives.get(name, {})
        add_candidate(f"derivative:{name}", derivative.get("url"))

    return candidates


def classify_failure(exc, has_next_method):
    if isinstance(exc, requests.exceptions.HTTPError):
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        if status_code in {408, 429, 500, 502, 503, 504}:
            return f"http_{status_code}", "retry_same_method"
        if has_next_method:
            return f"http_{status_code}", "try_next_method"
        return f"http_{status_code}", "manual_review"

    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return exc.__class__.__name__, "retry_same_method"

    if isinstance(exc, UnidentifiedImageError):
        if has_next_method:
            return "unidentified_image", "try_next_method"
        return "unidentified_image", "manual_review"

    if isinstance(exc, OSError):
        if has_next_method:
            return "image_decode_error", "try_next_method"
        return "image_decode_error", "manual_review"

    if isinstance(exc, requests.exceptions.RequestException):
        return exc.__class__.__name__, "retry_same_method"

    if has_next_method:
        return exc.__class__.__name__, "try_next_method"
    return exc.__class__.__name__, "manual_review"


def load_attempt_state():
    state = {}
    if not os.path.exists(ATTEMPT_LOG_PATH):
        return state, False

    with open(ATTEMPT_LOG_PATH, newline="") as f:
        reader = csv.DictReader(f)
        required_fields = {"scope", "hash_algorithm"}
        if not reader.fieldnames or not required_fields.issubset(reader.fieldnames):
            return {}, True

        for row in reader:
            if row.get("scope") != RUN_SCOPE:
                return {}, True
            if row.get("hash_algorithm") != HASH_ALGORITHM:
                return {}, True

            image_id = int(row["id"])
            entry = state.setdefault(image_id, {
                "success": False,
                "hash": "",
                "attempted_methods": [],
                "last_method": "",
                "last_status": "",
                "last_next_action": "",
                "last_next_method": "",
                "error_type": "",
                "error_detail": "",
            })

            method = row.get("method", "")
            if method and method not in entry["attempted_methods"]:
                entry["attempted_methods"].append(method)

            entry["last_method"] = method
            entry["last_status"] = row.get("status", "")
            entry["last_next_action"] = row.get("next_action", "")
            entry["last_next_method"] = row.get("next_method", "")
            entry["error_type"] = row.get("error_type", "")
            entry["error_detail"] = row.get("error_detail", "")

            if row.get("status") == "success":
                entry["success"] = True
                entry["hash"] = row.get("hash", "")

    return state, False


def reset_progress_files():
    for path in [ATTEMPT_LOG_PATH, OUTPUT_PATH, RETRY_QUEUE_PATH]:
        if os.path.exists(path):
            os.remove(path)


def open_attempt_log():
    file_exists = os.path.exists(ATTEMPT_LOG_PATH)
    handle = open(ATTEMPT_LOG_PATH, "a", newline="")
    writer = csv.DictWriter(handle, fieldnames=ATTEMPT_LOG_FIELDS)
    if not file_exists or os.path.getsize(ATTEMPT_LOG_PATH) == 0:
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())
    return handle, writer


def append_attempt(handle, writer, state, row):
    writer.writerow(row)
    handle.flush()
    os.fsync(handle.fileno())

    image_id = row["id"]
    entry = state.setdefault(image_id, {
        "success": False,
        "hash": "",
        "attempted_methods": [],
        "last_method": "",
        "last_status": "",
        "last_next_action": "",
        "last_next_method": "",
        "error_type": "",
        "error_detail": "",
    })

    method = row["method"]
    if method and method not in entry["attempted_methods"]:
        entry["attempted_methods"].append(method)

    entry["last_method"] = method
    entry["last_status"] = row["status"]
    entry["last_next_action"] = row["next_action"]
    entry["last_next_method"] = row["next_method"]
    entry["error_type"] = row["error_type"]
    entry["error_detail"] = row["error_detail"]

    if row["status"] == "success":
        entry["success"] = True
        entry["hash"] = row["hash"]


def get_start_index(candidates, state_entry):
    if not candidates:
        return None

    methods = [method for method, _ in candidates]

    if not state_entry:
        return 0

    if state_entry.get("success"):
        return None

    next_action = state_entry.get("last_next_action")
    if next_action == "try_next_method":
        next_method = state_entry.get("last_next_method")
        if next_method in methods:
            return methods.index(next_method)
        return None

    if next_action == "retry_same_method":
        last_method = state_entry.get("last_method")
        if last_method in methods:
            return methods.index(last_method)
        return 0

    if next_action == "manual_review":
        return None

    attempted_methods = set(state_entry.get("attempted_methods", []))
    for index, method in enumerate(methods):
        if method not in attempted_methods:
            return index

    return 0


def write_output_files(state):
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "hash"])
        for image_id in sorted(state):
            entry = state[image_id]
            if entry.get("success"):
                writer.writerow([image_id, entry.get("hash", "")])

    with open(RETRY_QUEUE_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id",
            "last_method",
            "next_action",
            "next_method",
            "error_type",
            "error_detail",
        ])
        for image_id in sorted(state):
            entry = state[image_id]
            if entry.get("success"):
                continue
            writer.writerow([
                image_id,
                entry.get("last_method", ""),
                entry.get("last_next_action", ""),
                entry.get("last_next_method", ""),
                entry.get("error_type", ""),
                entry.get("error_detail", ""),
            ])


def build_log_row(image_id, status, method, hash_value="", error_type="", error_detail="",
                  next_action="", next_method=""):
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": RUN_SCOPE,
        "id": image_id,
        "status": status,
        "method": method,
        "hash_algorithm": HASH_ALGORITHM,
        "hash": hash_value,
        "error_type": error_type,
        "error_detail": error_detail,
        "next_action": next_action,
        "next_method": next_method,
    }


def process_image(image, state, log_handle, log_writer):
    image_id = image["id"]
    state_entry = state.get(image_id)
    candidates = get_fetch_candidates(image)
    start_index = get_start_index(candidates, state_entry)

    if start_index is None:
        return False

    for index in range(start_index, len(candidates)):
        method, url = candidates[index]
        try:
            hash_value = hash_image(url)
            append_attempt(
                log_handle,
                log_writer,
                state,
                build_log_row(
                    image_id=image_id,
                    status="success",
                    method=method,
                    hash_value=hash_value,
                    next_action="done",
                ),
            )
            tqdm.write(f"{image_id} = success")
            return True
        except Exception as exc:
            next_method = candidates[index + 1][0] if index + 1 < len(candidates) else ""
            error_type, next_action = classify_failure(exc, has_next_method=bool(next_method))
            error_detail = str(exc).replace("\n", " ")[:500]

            append_attempt(
                log_handle,
                log_writer,
                state,
                build_log_row(
                    image_id=image_id,
                    status="failure",
                    method=method,
                    error_type=error_type,
                    error_detail=error_detail,
                    next_action=next_action,
                    next_method=next_method if next_action == "try_next_method" else "",
                ),
            )
            tqdm.write(f"{image_id} = failure")

            if next_action == "try_next_method":
                continue
            return False

    return False


def main():
    login()
    images = get_images()
    state, reset_required = load_attempt_state()
    if reset_required:
        reset_progress_files()
        state = {}
        print(f"Resetting prior progress because it was for a different scope or hash algorithm")
    pending_images = [img for img in images if not state.get(img["id"], {}).get("success")]

    print(f"Album category: {TARGET_CATEGORY_ID}")
    print(f"Loaded {len(images)} images")
    print(f"Skipping {len(images) - len(pending_images)} images already marked successful")
    print(f"Processing {len(pending_images)} images")

    log_handle, log_writer = open_attempt_log()
    processed_since_snapshot = 0

    try:
        for img in tqdm(pending_images):
            process_image(img, state, log_handle, log_writer)
            processed_since_snapshot += 1
            if processed_since_snapshot >= SNAPSHOT_INTERVAL:
                write_output_files(state)
                processed_since_snapshot = 0
    finally:
        log_handle.close()

    write_output_files(state)


if __name__ == "__main__":
    main()
