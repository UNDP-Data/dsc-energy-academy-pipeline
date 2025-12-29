import requests
import pandas as pd

BASE_URL = "https://geohub.data.undp.org/api/datasets"

def get_datasets_for_sdg(sdg_goal, limit=100):
    params = {
        "sdg_goal": str(sdg_goal),
        "limit": limit,
        "sortby": "updatedat,desc"
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    return resp.json().get("features", [])

def extract_dataset_info(ds):
    props = ds.get("properties", {})
    name = props.get("name", "Unnamed dataset")
    ds_id = props.get("id", "")
    url = props.get("url", "")
    description = props.get("description", "")
    license_ = props.get("license", "")
    created_at = props.get("createdat", "")
    updated_at = props.get("updatedat", "")
    access_level = props.get("access_level", "")

    tags = props.get("tags", [])
    goal = next((t["value"] for t in tags if t["key"] == "sdg_goal"), None)
    target = next((t["value"] for t in tags if t["key"] == "sdg_target"), None)
    theme = next((t["value"] for t in tags if t["key"] == "theme"), None)
    resolution = next((t["value"] for t in tags if t["key"] == "resolution"), None)

    return {
        "ID": ds_id,
        "Name": name,
        "SDG Goal": goal,
        "SDG Target": target,
        "Description": description,
        "URL": url,
        "License": license_,
        "Created At": created_at,
        "Updated At": updated_at,
        "Access Level": access_level,
        "Theme": theme,
        "Resolution": resolution
    }

def main():
    all_datasets = []

    for sdg in range(1, 18):
        print(f"Fetching datasets for SDG {sdg}...")
        datasets = get_datasets_for_sdg(sdg, limit=100)
        for ds in datasets:
            info = extract_dataset_info(ds)
            all_datasets.append(info)

    df = pd.DataFrame(all_datasets)
    df.to_excel("UNDP_GeoHub_Datasets.xlsx", index=False)
    print(f"Saved {len(all_datasets)} datasets to UNDP_GeoHub_Datasets.xlsx")

if __name__ == "__main__":
    main()
