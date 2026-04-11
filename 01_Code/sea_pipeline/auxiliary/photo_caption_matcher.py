from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse, urlsplit, urlunsplit

import numpy as np
import requests
from PIL import Image

from sea_pipeline.shared.io_json import load_json, save_json


AZURE_BLOB_HOST = "sehseadata.blob.core.windows.net"
EXCLUDED_IMAGE_PATH_MARKERS = (
    "/images/Resources/",
    "/images/Avatars/",
    "/images/Videos/",
)
INFOGRAPHIC_TEMPLATE_ID = "infographic"
CONNECTION_TEMPLATE_PREFIXES = ("connection_",)
EXCLUDED_TEMPLATE_IDS = {
    "infographic",
    "learning_objectives",
    "key_takeaways",
    "module_cover",
    "chapter_cover",
    "lesson_cover",
}
MATCH_BIT_ERROR_RATE = 0.10
MIN_DIRECT_MATCH_REGIONS = 1
MIN_CANDIDATE_REGION_COVERAGE = 0.80
SINGLE_REGION_MAX_AVG_ERROR = 0.08
STRONG_PARTIAL_MIN_MATCHED_REGIONS = 2
STRONG_PARTIAL_MAX_UNMATCHED_REGIONS = 1
STRONG_PARTIAL_MAX_AVG_ERROR = 0.03
MULTI_REGION_AMBIGUOUS_AVG_ERROR_MARGIN = 0.015
MULTI_REGION_AMBIGUOUS_SCORE_MARGIN = 0.20
AMBIGUOUS_COVERAGE_MARGIN = 0.10
PIWIGO_CATEGORY_ID = 209
PIWIGO_HASH_SHORTLIST_SIZE = 12
MATCH_STRATEGY_HASH = "hash"
MATCH_STRATEGY_HYBRID_AKAZE = "hybrid_akaze"
AKAZE_RATIO_TEST = 0.80
AKAZE_RANSAC_REPROJECTION_THRESHOLD = 5.0
AKAZE_MIN_GOOD_MATCHES = 12
AKAZE_MIN_INLIERS = 8
AKAZE_MIN_INLIER_RATIO = 0.30
AKAZE_MIN_CANDIDATE_COVERAGE = 0.08
AKAZE_AMBIGUOUS_INLIER_MARGIN = 2
AKAZE_AMBIGUOUS_SCORE_MARGIN = 1.0


@dataclass
class PhotoCaptionChange:
    lesson_path: str
    image_path: str
    src: str
    old_caption: str
    new_caption: str
    match_status: str
    computed_hash: str | None


@dataclass
class PiwigoHashRecord:
    photo_id: str
    hash_value: str
    parsed_hash: Any


@dataclass
class HashMatchMetrics:
    photo_id: str
    matched_regions: int
    candidate_regions: int
    available_regions: int
    candidate_coverage: float
    avg_bit_error: float
    score: float


@dataclass
class PiwigoMatchDecision:
    accepted_photo_id: str
    status: str
    best_photo_id: str | None
    best_metrics: Any | None


@dataclass
class PiwigoImageInfo:
    photo_id: str
    image_url: str | None
    page_url: str | None
    raw: dict[str, Any]


@dataclass
class PiwigoImageRecord:
    photo_id: str
    image_url: str | None
    page_url: str | None
    raw: dict[str, Any]


@dataclass
class FeatureMatchMetrics:
    photo_id: str
    good_matches: int
    inliers: int
    inlier_ratio: float
    candidate_coverage: float
    mean_distance: float
    keypoints: int
    target_keypoints: int
    score: float


def should_process_caption(caption: Any, skip_unknowns: bool) -> bool:
    value = "" if caption is None else str(caption).strip()
    if value == "":
        return True
    if not skip_unknowns and value.lower() == "unknown":
        return True
    return False


def is_photo_candidate_src(src: str) -> bool:
    if not src:
        return False
    parsed = urlparse(src)
    if AZURE_BLOB_HOST not in parsed.netloc:
        return False
    if any(marker in parsed.path for marker in EXCLUDED_IMAGE_PATH_MARKERS):
        return False
    filename = Path(parsed.path).name.lower()
    if filename.startswith("lesson") and filename.endswith("_frame.webp"):
        return False
    return parsed.path.startswith("/images/")


def iter_lesson_image_candidates(lesson_json: dict[str, Any], skip_unknowns: bool) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    first_header_image_skipped = False
    for segment_index, segment in enumerate(lesson_json.get("segments", [])):
        template_id = str(segment.get("template_id", "") or "")
        if template_id in EXCLUDED_TEMPLATE_IDS:
            continue
        if any(template_id.startswith(prefix) for prefix in CONNECTION_TEMPLATE_PREFIXES):
            continue

        def walk(node: Any, path: str) -> None:
            nonlocal first_header_image_skipped
            if isinstance(node, dict):
                if {"src", "caption"} <= set(node.keys()):
                    src = str(node.get("src", ""))
                    parsed = urlparse(src)
                    if "/images/HeaderImages/" in parsed.path and not first_header_image_skipped:
                        first_header_image_skipped = True
                        return
                    if is_photo_candidate_src(src) and should_process_caption(node.get("caption", ""), skip_unknowns):
                        candidates.append((path, node))
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for idx, value in enumerate(node):
                    walk(value, f"{path}[{idx}]")

        walk(segment.get("content", {}), f"segments[{segment_index}].content")
    return candidates


def _get_imagehash_module() -> Any:
    try:
        import imagehash  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "imagehash is required for photo caption matching. Install it with `pip3 install ImageHash`."
        ) from exc
    return imagehash


def parse_crop_resistant_hash(hash_value: str) -> Any:
    return _get_imagehash_module().hex_to_multihash(hash_value)


def _get_cv2_module() -> Any:
    try:
        import cv2  # type: ignore
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "opencv-python is required for AKAZE photo matching. Install it with `pip3 install opencv-python`."
        ) from exc
    return cv2


def normalize_piwigo_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid Piwigo base URL: {base_url}")

    path = parsed.path.rstrip("/")
    if path.endswith("/picture.php"):
        path = path[: -len("/picture.php")]
    elif path.endswith("/ws.php"):
        path = path[: -len("/ws.php")]
    elif path == "/picture.php":
        path = ""
    elif path == "/ws.php":
        path = ""

    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def _extract_piwigo_image_url(info: dict[str, Any]) -> str | None:
    direct_fields = (
        "element_url",
        "file_url",
        "download_url",
        "high_url",
        "tn_url",
    )
    for field in direct_fields:
        value = info.get(field)
        if isinstance(value, str) and value:
            return value

    derivatives = info.get("derivatives")
    if isinstance(derivatives, dict):
        preferred_sizes = (
            "xxlarge",
            "xlarge",
            "large",
            "medium",
            "small",
            "square",
            "thumb",
        )
        for size_name in preferred_sizes:
            derivative = derivatives.get(size_name)
            if isinstance(derivative, dict):
                value = derivative.get("url")
                if isinstance(value, str) and value:
                    return value
        for derivative in derivatives.values():
            if isinstance(derivative, dict):
                value = derivative.get("url")
                if isinstance(value, str) and value:
                    return value
    return None


def _parse_piwigo_json_response(response: requests.Response) -> dict[str, Any]:
    response.raise_for_status()
    payload = response.json()
    if payload.get("stat") != "ok":
        raise ValueError(f"Piwigo API error: {payload}")
    return payload


def create_piwigo_session(
    base_url: str,
    *,
    username: str | None = None,
    password: str | None = None,
    timeout_seconds: int = 30,
) -> requests.Session:
    normalized_base_url = normalize_piwigo_base_url(base_url)
    session = requests.Session()
    if not username:
        return session

    response = session.post(
        f"{normalized_base_url}/ws.php?format=json",
        data={
            "method": "pwg.session.login",
            "username": username,
            "password": password or "",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("stat") != "ok":
        raise ValueError(f"Piwigo login failed: {payload}")
    return session


def fetch_piwigo_image_info(
    base_url: str,
    photo_id: str,
    *,
    session: requests.Session | None = None,
    timeout_seconds: int = 30,
) -> PiwigoImageInfo:
    normalized_base_url = normalize_piwigo_base_url(base_url)
    active_session = session or requests.Session()
    response = active_session.post(
        f"{normalized_base_url}/ws.php?format=json",
        data={
            "method": "pwg.images.getInfo",
            "image_id": photo_id,
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("stat") != "ok":
        raise ValueError(f"Piwigo getInfo failed for image {photo_id}: {payload}")

    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError(f"Unexpected Piwigo getInfo payload for image {photo_id}: {payload}")

    return PiwigoImageInfo(
        photo_id=photo_id,
        image_url=_extract_piwigo_image_url(result),
        page_url=result.get("page_url") if isinstance(result.get("page_url"), str) else None,
        raw=result,
    )


def fetch_piwigo_category_images(
    base_url: str,
    category_id: int = PIWIGO_CATEGORY_ID,
    *,
    session: requests.Session | None = None,
    recursive: bool = True,
    per_page: int = 500,
    timeout_seconds: int = 30,
) -> list[PiwigoImageRecord]:
    normalized_base_url = normalize_piwigo_base_url(base_url)
    active_session = session or requests.Session()
    all_images: list[PiwigoImageRecord] = []
    page = 0

    while True:
        response = active_session.get(
            f"{normalized_base_url}/ws.php",
            params={
                "method": "pwg.categories.getImages",
                "format": "json",
                "cat_id": category_id,
                "recursive": "true" if recursive else "false",
                "per_page": per_page,
                "page": page,
            },
            timeout=timeout_seconds,
        )
        payload = _parse_piwigo_json_response(response)
        result = payload.get("result") or {}
        images = result.get("images") or []
        if not images:
            break

        for image in images:
            if not isinstance(image, dict):
                continue
            photo_id = str(image.get("id", "")).strip()
            if not photo_id:
                continue
            all_images.append(
                PiwigoImageRecord(
                    photo_id=photo_id,
                    image_url=_extract_piwigo_image_url(image),
                    page_url=image.get("page_url") if isinstance(image.get("page_url"), str) else None,
                    raw=image,
                )
            )

        paging = result.get("paging") or {}
        total_count = paging.get("total_count")
        if total_count is not None and len(all_images) >= int(total_count):
            break
        page += 1

    return all_images


def load_piwigo_hash_records(
    csv_path: str | Path,
    *,
    hash_parser: Callable[[str], Any] | None = None,
) -> list[PiwigoHashRecord]:
    parser = hash_parser or parse_crop_resistant_hash
    records: list[PiwigoHashRecord] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            photo_id = str(row.get("id", "")).strip()
            hash_value = str(row.get("hash", "")).strip().lower()
            if not photo_id or not hash_value:
                continue
            records.append(
                PiwigoHashRecord(
                    photo_id=photo_id,
                    hash_value=hash_value,
                    parsed_hash=parser(hash_value),
                )
            )
    return records


def fetch_image_bytes(src: str, timeout_seconds: int = 60) -> bytes:
    response = requests.get(src, timeout=timeout_seconds)
    response.raise_for_status()
    return response.content


def fetch_remote_image_bytes(
    src: str,
    *,
    session: requests.Session | None = None,
    timeout_seconds: int = 60,
) -> bytes:
    active_session = session or requests.Session()
    response = active_session.get(src, timeout=timeout_seconds)
    response.raise_for_status()
    return response.content


def compute_crop_resistant_hash(image_bytes: bytes) -> str:
    imagehash = _get_imagehash_module()
    with Image.open(BytesIO(image_bytes)) as image:
        return str(imagehash.crop_resistant_hash(image)).lower()


def decode_image_bytes_to_gray(image_bytes: bytes) -> np.ndarray:
    cv2 = _get_cv2_module()
    with Image.open(BytesIO(image_bytes)) as image:
        rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)


def compute_akaze_features(image_bytes: bytes) -> tuple[tuple[int, int], Any, Any]:
    cv2 = _get_cv2_module()
    gray = decode_image_bytes_to_gray(image_bytes)
    extractor = cv2.AKAZE_create()
    keypoints, descriptors = extractor.detectAndCompute(gray, None)
    return (gray.shape[1], gray.shape[0]), keypoints, descriptors


def _compute_candidate_point_coverage(points: np.ndarray, image_size: tuple[int, int]) -> float:
    width, height = image_size
    if width <= 0 or height <= 0 or points.size == 0:
        return 0.0

    x_coords = points[:, 0]
    y_coords = points[:, 1]
    span_x = max(float(x_coords.max() - x_coords.min()), 1.0)
    span_y = max(float(y_coords.max() - y_coords.min()), 1.0)
    return min((span_x * span_y) / (width * height), 1.0)


def evaluate_akaze_match(
    candidate_image_bytes: bytes,
    target_image_bytes: bytes,
    *,
    ratio_test: float = AKAZE_RATIO_TEST,
    ransac_reprojection_threshold: float = AKAZE_RANSAC_REPROJECTION_THRESHOLD,
) -> FeatureMatchMetrics | None:
    cv2 = _get_cv2_module()
    candidate_size, candidate_keypoints, candidate_descriptors = compute_akaze_features(candidate_image_bytes)
    _, target_keypoints, target_descriptors = compute_akaze_features(target_image_bytes)

    if candidate_descriptors is None or target_descriptors is None:
        return FeatureMatchMetrics(
            photo_id="",
            good_matches=0,
            inliers=0,
            inlier_ratio=0.0,
            candidate_coverage=0.0,
            mean_distance=float("inf"),
            keypoints=0 if candidate_keypoints is None else len(candidate_keypoints),
            target_keypoints=0 if target_keypoints is None else len(target_keypoints),
            score=float("-inf"),
        )

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw_matches = matcher.knnMatch(candidate_descriptors, target_descriptors, k=2)
    good_matches = []
    for pair in raw_matches:
        if len(pair) < 2:
            continue
        first, second = pair
        if first.distance < ratio_test * second.distance:
            good_matches.append(first)

    if not good_matches:
        return FeatureMatchMetrics(
            photo_id="",
            good_matches=0,
            inliers=0,
            inlier_ratio=0.0,
            candidate_coverage=0.0,
            mean_distance=float("inf"),
            keypoints=len(candidate_keypoints),
            target_keypoints=len(target_keypoints),
            score=float("-inf"),
        )

    mean_distance = float(sum(match.distance for match in good_matches) / len(good_matches))
    inliers = 0
    inlier_ratio = 0.0
    candidate_coverage = 0.0

    if len(good_matches) >= 4:
        source_points = np.float32([candidate_keypoints[match.queryIdx].pt for match in good_matches]).reshape(-1, 1, 2)
        destination_points = np.float32([target_keypoints[match.trainIdx].pt for match in good_matches]).reshape(-1, 1, 2)
        _, mask = cv2.findHomography(
            source_points,
            destination_points,
            cv2.RANSAC,
            ransac_reprojection_threshold,
        )
        if mask is not None:
            inlier_mask = mask.ravel().astype(bool)
            inliers = int(inlier_mask.sum())
            inlier_ratio = inliers / len(good_matches)
            inlier_source_points = source_points[inlier_mask].reshape(-1, 2)
            candidate_coverage = _compute_candidate_point_coverage(inlier_source_points, candidate_size)

    score = (
        inliers * 10.0
        + candidate_coverage * 100.0
        + inlier_ratio * 25.0
        + len(good_matches) * 1.0
        - mean_distance * 0.05
    )

    return FeatureMatchMetrics(
        photo_id="",
        good_matches=len(good_matches),
        inliers=inliers,
        inlier_ratio=inlier_ratio,
        candidate_coverage=candidate_coverage,
        mean_distance=mean_distance,
        keypoints=len(candidate_keypoints),
        target_keypoints=len(target_keypoints),
        score=score,
    )


def is_akaze_match_accepted(
    metrics: FeatureMatchMetrics,
    *,
    min_good_matches: int = AKAZE_MIN_GOOD_MATCHES,
    min_inliers: int = AKAZE_MIN_INLIERS,
    min_inlier_ratio: float = AKAZE_MIN_INLIER_RATIO,
    min_candidate_coverage: float = AKAZE_MIN_CANDIDATE_COVERAGE,
) -> bool:
    return (
        metrics.good_matches >= min_good_matches
        and metrics.inliers >= min_inliers
        and metrics.inlier_ratio >= min_inlier_ratio
        and metrics.candidate_coverage >= min_candidate_coverage
    )


def evaluate_multihash_match(
    candidate_hash: Any,
    target_hash: Any,
    *,
    bit_error_rate: float = MATCH_BIT_ERROR_RATE,
    min_candidate_coverage: float = MIN_CANDIDATE_REGION_COVERAGE,
    single_region_max_avg_error: float = SINGLE_REGION_MAX_AVG_ERROR,
) -> HashMatchMetrics | None:
    candidate_segments = getattr(candidate_hash, "segment_hashes", [])
    target_segments = getattr(target_hash, "segment_hashes", [])
    if not candidate_segments or not target_segments:
        return None

    candidate_regions = len(candidate_segments)
    available_regions = min(len(candidate_segments), len(target_segments))
    required_regions = min(MIN_DIRECT_MATCH_REGIONS, available_regions)
    matched_regions, total_distance = candidate_hash.hash_diff(target_hash, bit_error_rate=bit_error_rate)
    if matched_regions < required_regions:
        return None

    segment_bits = len(candidate_segments[0]) or 1
    avg_bit_error = total_distance / (matched_regions * segment_bits)
    candidate_coverage = matched_regions / max(candidate_regions, 1)
    unmatched_candidate_regions = candidate_regions - matched_regions
    strong_partial_match = (
        candidate_regions > 1
        and matched_regions >= STRONG_PARTIAL_MIN_MATCHED_REGIONS
        and unmatched_candidate_regions <= STRONG_PARTIAL_MAX_UNMATCHED_REGIONS
        and avg_bit_error <= STRONG_PARTIAL_MAX_AVG_ERROR
    )

    if candidate_coverage < min_candidate_coverage and not strong_partial_match:
        return None
    if candidate_regions == 1 and avg_bit_error > single_region_max_avg_error:
        return None

    return HashMatchMetrics(
        photo_id="",
        matched_regions=matched_regions,
        candidate_regions=candidate_regions,
        available_regions=available_regions,
        candidate_coverage=candidate_coverage,
        avg_bit_error=avg_bit_error,
        score=float(candidate_hash.__sub__(target_hash, bit_error_rate=bit_error_rate)),
    )


def score_piwigo_candidate_similarity(candidate_hash: Any, target_hash: Any) -> HashMatchMetrics | None:
    candidate_segments = getattr(candidate_hash, "segment_hashes", [])
    target_segments = getattr(target_hash, "segment_hashes", [])
    if not candidate_segments or not target_segments:
        return None

    candidate_regions = len(candidate_segments)
    available_regions = min(len(candidate_segments), len(target_segments))
    matched_regions, total_distance = candidate_hash.hash_diff(target_hash, bit_error_rate=1.0)
    if matched_regions > 0:
        segment_bits = len(candidate_segments[0]) or 1
        avg_bit_error = total_distance / (matched_regions * segment_bits)
        candidate_coverage = matched_regions / max(candidate_regions, 1)
    else:
        avg_bit_error = float("inf")
        candidate_coverage = 0.0

    return HashMatchMetrics(
        photo_id="",
        matched_regions=matched_regions,
        candidate_regions=candidate_regions,
        available_regions=available_regions,
        candidate_coverage=candidate_coverage,
        avg_bit_error=avg_bit_error,
        score=float(candidate_hash.__sub__(target_hash, bit_error_rate=1.0)),
    )


def rank_piwigo_candidates(
    candidate_hash: Any,
    piwigo_records: list[PiwigoHashRecord],
    *,
    match_evaluator: Callable[[Any, Any], HashMatchMetrics | None] = evaluate_multihash_match,
) -> list[HashMatchMetrics]:
    candidates: list[HashMatchMetrics] = []
    for record in piwigo_records:
        metrics = match_evaluator(candidate_hash, record.parsed_hash)
        if metrics is None:
            continue
        candidates.append(
            HashMatchMetrics(
                photo_id=record.photo_id,
                matched_regions=metrics.matched_regions,
                candidate_regions=metrics.candidate_regions,
                available_regions=metrics.available_regions,
                candidate_coverage=metrics.candidate_coverage,
                avg_bit_error=metrics.avg_bit_error,
                score=metrics.score,
            )
        )

    candidates.sort(
        key=lambda item: (
            -item.candidate_coverage,
            -item.matched_regions,
            item.avg_bit_error,
            item.score,
            item.photo_id,
        )
    )
    return candidates


def rank_best_piwigo_candidate(
    candidate_hash: Any,
    piwigo_records: list[PiwigoHashRecord],
) -> HashMatchMetrics | None:
    candidates = rank_piwigo_candidates(
        candidate_hash,
        piwigo_records,
        match_evaluator=score_piwigo_candidate_similarity,
    )
    if not candidates:
        return None
    return candidates[0]


def rank_akaze_candidates(
    candidate_image_bytes: bytes,
    piwigo_records: list[PiwigoImageRecord],
    *,
    image_fetcher: Callable[[PiwigoImageRecord], bytes],
    ratio_test: float = AKAZE_RATIO_TEST,
    ransac_reprojection_threshold: float = AKAZE_RANSAC_REPROJECTION_THRESHOLD,
) -> list[FeatureMatchMetrics]:
    candidates: list[FeatureMatchMetrics] = []
    for record in piwigo_records:
        if not record.image_url:
            continue
        try:
            metrics = evaluate_akaze_match(
                candidate_image_bytes,
                image_fetcher(record),
                ratio_test=ratio_test,
                ransac_reprojection_threshold=ransac_reprojection_threshold,
            )
        except Exception:
            continue
        if metrics is None:
            continue
        candidates.append(
            FeatureMatchMetrics(
                photo_id=record.photo_id,
                good_matches=metrics.good_matches,
                inliers=metrics.inliers,
                inlier_ratio=metrics.inlier_ratio,
                candidate_coverage=metrics.candidate_coverage,
                mean_distance=metrics.mean_distance,
                keypoints=metrics.keypoints,
                target_keypoints=metrics.target_keypoints,
                score=metrics.score,
            )
        )

    candidates.sort(
        key=lambda item: (
            -item.inliers,
            -item.candidate_coverage,
            -item.inlier_ratio,
            -item.good_matches,
            item.mean_distance,
            -item.score,
            item.photo_id,
        )
    )
    return candidates


def resolve_best_akaze_match(
    candidate_image_bytes: bytes,
    piwigo_records: list[PiwigoImageRecord],
    *,
    image_fetcher: Callable[[PiwigoImageRecord], bytes],
    ratio_test: float = AKAZE_RATIO_TEST,
    ransac_reprojection_threshold: float = AKAZE_RANSAC_REPROJECTION_THRESHOLD,
    min_good_matches: int = AKAZE_MIN_GOOD_MATCHES,
    min_inliers: int = AKAZE_MIN_INLIERS,
    min_inlier_ratio: float = AKAZE_MIN_INLIER_RATIO,
    min_candidate_coverage: float = AKAZE_MIN_CANDIDATE_COVERAGE,
    ambiguous_inlier_margin: int = AKAZE_AMBIGUOUS_INLIER_MARGIN,
    ambiguous_score_margin: float = AKAZE_AMBIGUOUS_SCORE_MARGIN,
) -> tuple[PiwigoMatchDecision, str | None]:
    ranked_candidates = rank_akaze_candidates(
        candidate_image_bytes,
        piwigo_records,
        image_fetcher=image_fetcher,
        ratio_test=ratio_test,
        ransac_reprojection_threshold=ransac_reprojection_threshold,
    )
    if not ranked_candidates:
        return (
            PiwigoMatchDecision(
                accepted_photo_id="unknown",
                status="unknown",
                best_photo_id=None,
                best_metrics=None,
            ),
            None,
        )

    preview_best = ranked_candidates[0]
    preview_url = next((record.image_url for record in piwigo_records if record.photo_id == preview_best.photo_id), None)
    accepted_candidates = [
        candidate
        for candidate in ranked_candidates
        if is_akaze_match_accepted(
            candidate,
            min_good_matches=min_good_matches,
            min_inliers=min_inliers,
            min_inlier_ratio=min_inlier_ratio,
            min_candidate_coverage=min_candidate_coverage,
        )
    ]

    if not accepted_candidates:
        return (
            PiwigoMatchDecision(
                accepted_photo_id="unknown",
                status="unknown",
                best_photo_id=preview_best.photo_id,
                best_metrics=preview_best,
            ),
            preview_url,
        )

    best = accepted_candidates[0]
    if len(accepted_candidates) == 1:
        return (
            PiwigoMatchDecision(
                accepted_photo_id=best.photo_id,
                status="matched",
                best_photo_id=preview_best.photo_id,
                best_metrics=preview_best,
            ),
            preview_url,
        )

    second = accepted_candidates[1]
    if (
        abs(best.inliers - second.inliers) <= ambiguous_inlier_margin
        and abs(best.score - second.score) <= ambiguous_score_margin
    ):
        return (
            PiwigoMatchDecision(
                accepted_photo_id="unknown",
                status="ambiguous",
                best_photo_id=preview_best.photo_id,
                best_metrics=preview_best,
            ),
            preview_url,
        )

    return (
        PiwigoMatchDecision(
            accepted_photo_id=best.photo_id,
            status="matched",
            best_photo_id=preview_best.photo_id,
            best_metrics=preview_best,
        ),
        preview_url,
    )


def resolve_best_piwigo_match(
    candidate_hash: Any,
    piwigo_records: list[PiwigoHashRecord],
    *,
    match_evaluator: Callable[[Any, Any], HashMatchMetrics | None] = evaluate_multihash_match,
) -> PiwigoMatchDecision:
    candidates = rank_piwigo_candidates(candidate_hash, piwigo_records, match_evaluator=match_evaluator)
    preview_best = rank_best_piwigo_candidate(candidate_hash, piwigo_records)
    if not candidates:
        return PiwigoMatchDecision(
            accepted_photo_id="unknown",
            status="unknown",
            best_photo_id=None if preview_best is None else preview_best.photo_id,
            best_metrics=preview_best,
        )

    best = candidates[0]
    if len(candidates) == 1:
        return PiwigoMatchDecision(
            accepted_photo_id=best.photo_id,
            status="matched",
            best_photo_id=best.photo_id,
            best_metrics=best,
        )

    second = candidates[1]
    if (
        abs(best.candidate_coverage - second.candidate_coverage) <= AMBIGUOUS_COVERAGE_MARGIN
        and best.matched_regions == second.matched_regions
    ):
        if best.candidate_regions == 1:
            return PiwigoMatchDecision(
                accepted_photo_id="unknown",
                status="ambiguous",
                best_photo_id=best.photo_id,
                best_metrics=best,
            )
        if (
            abs(best.avg_bit_error - second.avg_bit_error) <= MULTI_REGION_AMBIGUOUS_AVG_ERROR_MARGIN
            and abs(best.score - second.score) <= MULTI_REGION_AMBIGUOUS_SCORE_MARGIN
        ):
            return PiwigoMatchDecision(
                accepted_photo_id="unknown",
                status="ambiguous",
                best_photo_id=best.photo_id,
                best_metrics=best,
            )

    return PiwigoMatchDecision(
        accepted_photo_id=best.photo_id,
        status="matched",
        best_photo_id=best.photo_id,
        best_metrics=best,
    )


def select_best_piwigo_match(
    candidate_hash: Any,
    piwigo_records: list[PiwigoHashRecord],
    *,
    match_evaluator: Callable[[Any, Any], HashMatchMetrics | None] = evaluate_multihash_match,
) -> tuple[str, str]:
    decision = resolve_best_piwigo_match(candidate_hash, piwigo_records, match_evaluator=match_evaluator)
    return decision.accepted_photo_id, decision.status


def caption_for_hash(
    hash_value: str,
    piwigo_records: list[PiwigoHashRecord],
    *,
    hash_parser: Callable[[str], Any] | None = None,
    match_evaluator: Callable[[Any, Any], HashMatchMetrics | None] = evaluate_multihash_match,
) -> tuple[str, str]:
    parser = hash_parser or parse_crop_resistant_hash
    candidate_hash = parser(hash_value.lower())
    return select_best_piwigo_match(candidate_hash, piwigo_records, match_evaluator=match_evaluator)


def update_photo_captions_from_piwigo(
    lesson_root: str | Path,
    piwigo_csv_path: str | Path,
    *,
    lesson_glob: str = "Module_*/*.json",
    skip_unknowns: bool = True,
    test_run: bool = False,
    sample_size: int = 3,
    image_limit: int | None = None,
    match_strategy: str = MATCH_STRATEGY_HYBRID_AKAZE,
    match_bit_error_rate: float = MATCH_BIT_ERROR_RATE,
    min_candidate_coverage: float = MIN_CANDIDATE_REGION_COVERAGE,
    piwigo_base_url: str | None = None,
    piwigo_category_id: int = PIWIGO_CATEGORY_ID,
    piwigo_username: str | None = None,
    piwigo_password: str | None = None,
    piwigo_hash_shortlist_size: int = PIWIGO_HASH_SHORTLIST_SIZE,
    akaze_ratio_test: float = AKAZE_RATIO_TEST,
    akaze_ransac_reprojection_threshold: float = AKAZE_RANSAC_REPROJECTION_THRESHOLD,
    akaze_min_good_matches: int = AKAZE_MIN_GOOD_MATCHES,
    akaze_min_inliers: int = AKAZE_MIN_INLIERS,
    akaze_min_inlier_ratio: float = AKAZE_MIN_INLIER_RATIO,
    akaze_min_candidate_coverage: float = AKAZE_MIN_CANDIDATE_COVERAGE,
    fetcher: Callable[[str], bytes] | None = None,
    hash_computer: Callable[[bytes], str] | None = None,
    hash_parser: Callable[[str], Any] | None = None,
    match_evaluator: Callable[[Any, Any], HashMatchMetrics | None] = evaluate_multihash_match,
    piwigo_image_url_builder: Callable[[str], str | None] | None = None,
    match_reporter: Callable[[dict[str, Any]], None] | None = None,
    log: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    root = Path(lesson_root)
    piwigo_records = load_piwigo_hash_records(piwigo_csv_path, hash_parser=hash_parser)
    fetch = fetcher or fetch_image_bytes
    compute_hash = hash_computer or compute_crop_resistant_hash
    effective_match_evaluator = (
        (lambda candidate_hash, target_hash: evaluate_multihash_match(
            candidate_hash,
            target_hash,
            bit_error_rate=match_bit_error_rate,
            min_candidate_coverage=min_candidate_coverage,
        ))
        if match_evaluator is evaluate_multihash_match
        else match_evaluator
    )
    piwigo_session = None
    piwigo_images_by_id: dict[str, PiwigoImageRecord] = {}
    piwigo_image_bytes_cache: dict[str, bytes] = {}
    if match_strategy == MATCH_STRATEGY_HYBRID_AKAZE and piwigo_base_url:
        piwigo_session = create_piwigo_session(
            piwigo_base_url,
            username=piwigo_username,
            password=piwigo_password,
        )
        piwigo_images = fetch_piwigo_category_images(
            piwigo_base_url,
            category_id=piwigo_category_id,
            session=piwigo_session,
        )
        piwigo_images_by_id = {record.photo_id: record for record in piwigo_images if record.image_url or record.page_url}
        if log:
            log(
                f"🖼️ Loaded {len(piwigo_images_by_id)} Piwigo image records "
                f"from category {piwigo_category_id} for AKAZE matching"
            )

    def fetch_piwigo_candidate_bytes(record: PiwigoImageRecord) -> bytes:
        source_url = record.image_url or record.page_url
        if not source_url:
            raise ValueError(f"Piwigo image {record.photo_id} has no usable URL")
        if source_url not in piwigo_image_bytes_cache:
            piwigo_image_bytes_cache[source_url] = fetch_remote_image_bytes(source_url, session=piwigo_session)
        return piwigo_image_bytes_cache[source_url]

    changes: list[PhotoCaptionChange] = []
    scanned_lessons = 0
    scanned_images = 0
    changed_lessons = 0

    lesson_paths = sorted(root.glob(lesson_glob))
    if test_run:
        lesson_paths = lesson_paths[:sample_size]

    stopped_after_image_limit = False
    for lesson_path in lesson_paths:
        if image_limit is not None and scanned_images >= image_limit:
            stopped_after_image_limit = True
            break
        if lesson_path.name == "module_structure.json":
            continue
        lesson_json = load_json(lesson_path)
        candidates = iter_lesson_image_candidates(lesson_json, skip_unknowns=skip_unknowns)
        scanned_lessons += 1
        lesson_relpath = str(lesson_path.relative_to(root))
        if log:
            log(f"📘 Lesson {lesson_relpath}: {len(candidates)} eligible images")
        if not candidates:
            continue

        lesson_changed = False
        for image_path, image_node in candidates:
            if image_limit is not None and scanned_images >= image_limit:
                stopped_after_image_limit = True
                break
            scanned_images += 1
            src = str(image_node.get("src", ""))
            old_caption = "" if image_node.get("caption") is None else str(image_node.get("caption"))
            if log:
                limit_suffix = f"/{image_limit}" if image_limit is not None else ""
                log(f"  🔎 Image {scanned_images}{limit_suffix}: {lesson_relpath} | {image_path}")
                log(f"     src={src}")

            try:
                source_image_bytes = fetch(src)
                hash_value = compute_hash(source_image_bytes)
                candidate_hash = (hash_parser or parse_crop_resistant_hash)(hash_value.lower())
                best_piwigo_src = None

                if match_strategy == MATCH_STRATEGY_HYBRID_AKAZE and piwigo_images_by_id:
                    shortlist = rank_piwigo_candidates(
                        candidate_hash,
                        piwigo_records,
                        match_evaluator=score_piwigo_candidate_similarity,
                    )[:piwigo_hash_shortlist_size]
                    shortlist_records = [
                        piwigo_images_by_id[metrics.photo_id]
                        for metrics in shortlist
                        if metrics.photo_id in piwigo_images_by_id
                    ]
                    if log:
                        log(
                            f"     shortlist={len(shortlist_records)} candidates "
                            f"from top {len(shortlist)} hash-ranked Piwigo images"
                        )
                    decision, best_piwigo_src = resolve_best_akaze_match(
                        source_image_bytes,
                        shortlist_records,
                        image_fetcher=fetch_piwigo_candidate_bytes,
                        ratio_test=akaze_ratio_test,
                        ransac_reprojection_threshold=akaze_ransac_reprojection_threshold,
                        min_good_matches=akaze_min_good_matches,
                        min_inliers=akaze_min_inliers,
                        min_inlier_ratio=akaze_min_inlier_ratio,
                        min_candidate_coverage=akaze_min_candidate_coverage,
                    )
                else:
                    decision = resolve_best_piwigo_match(
                        candidate_hash,
                        piwigo_records,
                        match_evaluator=effective_match_evaluator,
                    )

                new_caption = decision.accepted_photo_id
                match_status = decision.status
            except Exception as exc:
                hash_value = None
                new_caption = "unknown"
                match_status = "error"
                decision = None
                best_piwigo_src = None
                if log:
                    log(f"     result=error | reason={type(exc).__name__}: {exc}")
            else:
                best_metrics = decision.best_metrics if decision else None
                best_photo_id = decision.best_photo_id if decision else None
                if best_piwigo_src is None and best_photo_id and piwigo_image_url_builder is not None:
                    best_piwigo_src = piwigo_image_url_builder(best_photo_id)
                if match_reporter is not None:
                    match_reporter(
                        {
                            "lesson_path": lesson_relpath,
                            "image_path": image_path,
                            "src": src,
                            "old_caption": old_caption,
                            "new_caption": new_caption,
                            "match_status": match_status,
                            "computed_hash": hash_value,
                            "best_photo_id": best_photo_id,
                            "best_piwigo_src": best_piwigo_src,
                            "best_metrics": None if best_metrics is None else best_metrics.__dict__,
                        }
                    )
                if log:
                    hash_label = hash_value if hash_value is not None else "None"
                    log(
                        f"     result={match_status} | old_caption={old_caption!r} | "
                        f"new_caption={new_caption!r} | hash={hash_label}"
                    )
                    if best_metrics is not None and isinstance(best_metrics, FeatureMatchMetrics):
                        log(
                            "     top_piwigo="
                            f"{best_photo_id} | inliers={best_metrics.inliers} | "
                            f"good_matches={best_metrics.good_matches} | "
                            f"coverage={best_metrics.candidate_coverage:.2f} | "
                            f"inlier_ratio={best_metrics.inlier_ratio:.2f} | "
                            f"mean_distance={best_metrics.mean_distance:.2f} | "
                            f"score={best_metrics.score:.2f}"
                        )
                    elif best_metrics is not None:
                        log(
                            "     top_piwigo="
                            f"{best_photo_id} | coverage={best_metrics.candidate_coverage:.2f} | "
                            f"matched_regions={best_metrics.matched_regions}/{best_metrics.candidate_regions} | "
                            f"avg_bit_error={best_metrics.avg_bit_error:.3f} | score={best_metrics.score:.3f}"
                        )

            if old_caption != new_caption:
                image_node["caption"] = new_caption
                lesson_changed = True

            changes.append(
                PhotoCaptionChange(
                    lesson_path=str(lesson_path.relative_to(root)),
                    image_path=image_path,
                    src=src,
                    old_caption=old_caption,
                    new_caption=new_caption,
                    match_status=match_status,
                    computed_hash=hash_value,
                )
            )

        if lesson_changed:
            changed_lessons += 1
            save_json(lesson_json, lesson_path)

    summary = {
        "status": "ok",
        "test_run": test_run,
        "sample_size": sample_size if test_run else None,
        "image_limit": image_limit,
        "match_strategy": match_strategy,
        "match_bit_error_rate": match_bit_error_rate,
        "min_candidate_coverage": min_candidate_coverage,
        "piwigo_hash_shortlist_size": piwigo_hash_shortlist_size if match_strategy == MATCH_STRATEGY_HYBRID_AKAZE else None,
        "akaze_min_good_matches": akaze_min_good_matches if match_strategy == MATCH_STRATEGY_HYBRID_AKAZE else None,
        "akaze_min_inliers": akaze_min_inliers if match_strategy == MATCH_STRATEGY_HYBRID_AKAZE else None,
        "akaze_min_inlier_ratio": akaze_min_inlier_ratio if match_strategy == MATCH_STRATEGY_HYBRID_AKAZE else None,
        "akaze_min_candidate_coverage": akaze_min_candidate_coverage if match_strategy == MATCH_STRATEGY_HYBRID_AKAZE else None,
        "stopped_after_image_limit": stopped_after_image_limit,
        "skip_unknowns": skip_unknowns,
        "scanned_lessons": scanned_lessons,
        "scanned_images": scanned_images,
        "changed_lessons": changed_lessons,
        "matched": sum(1 for change in changes if change.match_status == "matched"),
        "unknown": sum(1 for change in changes if change.match_status == "unknown"),
        "ambiguous": sum(1 for change in changes if change.match_status == "ambiguous"),
        "errors": sum(1 for change in changes if change.match_status == "error"),
        "changes": [change.__dict__ for change in changes],
    }
    return summary
