# Technical Documentation: SEA Chart Generation Pipeline

## Overview

The SEA Chart Generation Pipeline is an automated system for creating Apache ECharts visualizations from Excel-based datasets and metadata. The pipeline processes chart specifications, applies templates, and generates JSON configuration files that can be rendered as interactive charts.

## Architecture

The pipeline consists of three main components:

1. **Data Extraction Layer** - Reads and processes Excel files
2. **Chart Generation Engine** - Applies templates and transforms data
3. **Output Layer** - Generates JSON configuration files

### Technology Stack
- **Python 3.13+**
- **pandas** - Data manipulation and Excel I/O
- **openpyxl** - Excel file handling
- **json** - JSON serialization
- **pathlib** - File path management

---

## Pipeline Workflow

```
Excel Metadata → [Extract Metadata] → Metadata DataFrame
Excel Datasets → [Extract Datasets] → Dataset Dictionary
                         ↓
              [Merge Data & Metadata]
                         ↓
                 Combined Charts Dict
                         ↓
        [Load Chart Config & Templates]
                         ↓
              [Process Each Chart Type]
                         ↓
         Generate Light & Dark Mode JSONs
```

---

## File Structure

### Input Files

#### 1. Chart Tracker Excel (`Charts Tracker.xlsx`)
**Location**: `../02_Inputs/charts/Metadata/Charts Tracker.xlsx`

**Structure**:
- Multiple sheets (one per module): "Module 1", "Module 2", etc.
- Header row at index 1 (row 2 in Excel)

**Required Columns**:
```python
{
    "Figure ID": str,           # Unique identifier (e.g., "M1_C1_2")
    "Title": str,               # Chart title
    "Subtitle": str,            # Optional subtitle
    "Footnote": str,            # Optional footnote
    "Category": str,            # "Chart to recreate" or other
    "Chart Type": str,          # Chart type identifier
    "Apache Possible": str,     # "Yes" or "No"
    "Automation Possible": str, # "Yes" or "No"
    "Dataset Status": str,      # "Ready" or "Pending"
    "module": str               # Auto-added during processing
}
```

#### 2. Dataset Excel Files
**Location**: `../02_Inputs/charts/Data/Charts/Module X - *.xlsx`

**Structure**:
- Each sheet represents one chart's dataset
- Sheet name must match the Figure ID
- Data starts at cell A1 with headers in first row
- No empty rows/columns at start

**Example Dataset Format**:
```csv
Country,Value,Year
USA,100,2020
China,150,2020
India,80,2020
```

#### 3. Chart Config Excel (`Charts Config.xlsx`)
**Location**: `../02_Inputs/charts/Metadata/Charts Config.xlsx`

**Structure**:
- Multiple sheets (one per module)
- Columns: `Chart Code`, `Property`, `Column Name`

**Example Entries**:
```
Chart Code | Property      | Column Name
M1_C1_2   | Category      | Country
M1_C1_2   | Value         | Value
M1_C1_7   | X Axis        | Year
M1_C1_7   | Y Axis Series | CO2, CH4, N2O
```

#### 4. Template Files
**Location**: `../02_Inputs/charts/Templates/`

**Files**:
- `_charts_global_template_light.json` - Base light mode styling
- `_charts_global_template_dark.json` - Base dark mode styling
- `{chart_type}_template.json` - Chart type-specific templates

**Template Types**:
```
bar_chart_vertical_template.json
bar_chart_horizontal_template.json
bar_chart_categories_horizontal_template.json
bar_chart_categories_vertical_template.json
bar_chart_stacked_vertical_template.json
bar_chart_stacked_horizontal_template.json
bar_chart_stacked_normalized_vertical_template.json
pie_chart_template.json
doughnut_chart_template.json
scatter_chart_template.json
scatter_chart_categories_template.json
line_chart_template.json
line_chart_multi_template.json
line_chart_stacked_template.json
```

### Output Files

**Location**: 
- Light Mode: `../03_Outputs/charts/Auto Charts/LightMode/`
- Dark Mode: `../03_Outputs/charts/Auto Charts/DarkMode/`

**Format**: `{Figure_ID}.json`

**Structure**: Apache ECharts JSON configuration

---

## Core Functions

### 1. Data Extraction

#### `extract_dataset(in_dir)`

**Purpose**: Extracts all chart datasets from module Excel files.

**Input**:
- `in_dir` (str): Path to directory containing module Excel files

**Processing Logic**:
```python
1. Scan directory for files matching "Module *"
2. For each Excel file:
   a. Extract module name from filename
   b. Read all sheets
   c. For each sheet:
      - Read data into DataFrame
      - Drop fully empty rows and columns
      - Reset index
      - Convert to CSV string
      - Store with sheet name (Figure ID) as key
```

**Output**:
```python
{
    "M1_C1_2": "Country,Value\nUSA,100\nChina,150",
    "M1_C1_7": "Year,CO2,CH4\n2020,100,20\n2021,105,22",
    ...
}
```

**Error Handling**:
- Prints warning for blank sheet names
- Catches and logs sheet reading exceptions
- Continues processing remaining sheets on error

---

#### `extract_metadata(in_path)`

**Purpose**: Extracts chart metadata from all module sheets in the tracker Excel file.

**Input**:
- `in_path` (str): Path to Charts Tracker Excel file

**Processing Logic**:
```python
1. Open Excel file and list all sheet names
2. Filter sheets starting with "module" (case-insensitive)
3. For each module sheet:
   a. Read with header at row 1 (index 1)
   b. Force all columns to string dtype
   c. Add 'module' column with sheet name
   d. Append to list
4. Concatenate all DataFrames
```

**Output**: Single DataFrame with all charts' metadata

**Error Handling**:
- Catches and logs errors for individual sheets
- Continues processing remaining sheets

---

### 2. Data Merging and Filtering

#### `merge_data_metadata(metadata_df, chart_datasets)`

**Purpose**: Combines metadata and datasets, applies filters, and generates statistics.

**Filtering Logic**:

Charts are **excluded** if they fail ANY of these conditions:
```python
filters = {
    "Category": row["Category"] == "Chart to recreate",
    "Apache Possible": row["Apache Possible"] == "Yes",
    "Automation Possible": row["Automation Possible"] == "Yes",
    "Dataset Status": row["Dataset Status"] == "Ready"
}
```

**Processing Algorithm**:
```python
for each row in metadata_df:
    reasons = []
    
    # Check each filter condition
    if not meets_condition:
        reasons.append(reason_text)
        increment_filter_counter
        add_to_filtered_ids_list
    
    if reasons:
        add_to_excluded_list
        continue
    
    # Passed all filters
    lookup_dataset(figure_id)
    create_chart_entry
    add_to_charts_dict
```

**Output Structure**:
```python
{
    "M1_C1_2": {
        "metadata": {
            "Figure ID": "M1_C1_2",
            "Title": "Chart Title",
            "Chart Type": "bar chart vertical",
            ...
        },
        "dataset": "Country,Value\nUSA,100\n..."
    },
    ...
}
```

**Statistics Generated**:
1. **Filtering Summary**:
   - Total charts in metadata
   - Charts added (passed filters)
   - Charts excluded (failed filters)
   - Quota percentage (added/total)

2. **Filter Breakdown**:
   - Count per filter condition
   - List of Figure IDs excluded by each condition

3. **Category Percentages** (from ALL charts):
   - Ready to Use: `Category == "Chart to recreate"`
   - Recreate & Apache = No
   - Recreate & Apache = Yes & Automation = No
   - Recreate & Apache = Yes & Automation = Yes

**Console Output Example**:
```
🚫 Filtered-out charts:
 - M1_C1_3: Category ≠ 'Chart to recreate'; Apache Possible ≠ 'Yes'
 - M1_C1_5: Dataset Status ≠ 'Ready'

📊 Chart Filtering Summary:
 - Total charts in metadata: 155
 - Charts added: 74
 - Charts excluded: 81
 - Quota: 47.74%

🚫 Breakdown of filters:
   • Category: 29
     IDs: M1_C1_3, M1_C1_5, ...
   • Apache Possible: 42
   • Automation Possible: 65
   • Dataset Status: 71

✅ Charts successfully added:
 - M1_C1_2
 - M1_C1_7
 ...
```

---

### 3. Configuration Loading

#### `load_charts_config(filepath)`

**Purpose**: Loads chart-specific configuration from Charts Config Excel.

**Processing Logic**:
```python
1. Read all sheet names from Excel file
2. Filter sheets starting with "Module"
3. For each module sheet:
   a. Read DataFrame with all columns as strings
   b. For each row:
      - Extract chart_code (Figure ID)
      - Clean property value (parse lists, strip quotes)
      - Store in nested dictionary
```

**Value Cleaning Algorithm**:
```python
def clean_value(val):
    if ',' in val:
        return [v.strip() for v in val.split(',')]  # List
    
    try:
        return ast.literal_eval(val)  # Parse Python literals
    except:
        pass
    
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]  # Remove quotes
    
    return val
```

**Output Structure**:
```python
{
    "M1_C1_2": {
        "Category": "Country",
        "Value": "Value"
    },
    "M1_C1_7": {
        "X Axis": "Year",
        "Y Axis Series": ["CO2", "CH4", "N2O"]
    }
}
```

---

#### `load_template(template_path)`

**Purpose**: Loads JSON template file.

**Error Handling**:
- Returns `None` if file not found
- Prints error message

---

#### `merge_templates(global_template, specific_template)`

**Purpose**: Deep merges global and chart-specific templates.

**Algorithm**:
```python
def deep_merge(dict1, dict2):
    for key, value in dict2.items():
        if key in dict1 and both are dicts:
            deep_merge(dict1[key], value)  # Recursive merge
        else:
            dict1[key] = value  # Override or add
```

**Use Case**: Specific template overrides global styling while preserving unspecified properties.

---

### 4. Utility Functions

#### `wrap_label(label: str, max_chars: int = 20)`

**Purpose**: Wraps long labels into multiple lines for better display.

**Algorithm**:
```python
if len(label) <= max_chars:
    return label  # No wrapping needed

words = label.split()

if len(words) == 1:
    # No spaces: break at max_chars intervals
    return "\n".join([label[i:i+max_chars] for i in range(0, len(label), max_chars)])

# Word-by-word wrapping
lines = []
current_line = ""

for word in words:
    if len(current_line + " " + word) <= max_chars:
        current_line += " " + word if current_line else word
    else:
        lines.append(current_line)
        current_line = word

if current_line:
    lines.append(current_line)

return "\n".join(lines)
```

**Example**:
```python
wrap_label("Very Long Category Name That Exceeds Maximum", 20)
# Returns: "Very Long Category\nName That Exceeds\nMaximum"
```

---

#### `read_dataset(dataset_str, chart_id)`

**Purpose**: Converts CSV string to pandas DataFrame.

**Special Handling**:
- `keep_default_na=False` prevents automatic NaN conversion
- Empty strings replaced with `None`

**Error Handling**:
- Catches and logs parsing errors
- Returns `None` on failure

---

### 5. Chart Generation

#### `generate_chart(chart_id, metadata, dataset_str, template_path, output_dir, prepare_data_fn, global_template_path=None)`

**Purpose**: Orchestrates the complete chart generation process.

**Process Flow**:
```python
1. Print chart ID and title
2. Read dataset string into DataFrame
3. Load specific template
4. If global template provided:
   - Load global template
   - Merge with specific template
5. Execute prepare_data function to populate template
6. Save chart configuration to output directory
```

**Parameters**:
- `chart_id` (str): Figure ID
- `metadata` (dict): Chart metadata
- `dataset_str` (str): CSV-formatted dataset
- `template_path` (str): Path to chart-specific template
- `output_dir` (str): Output directory path
- `prepare_data_fn` (function): Function to populate template with data
- `global_template_path` (str, optional): Path to global template

**Error Handling**:
- Returns early if dataset reading fails
- Returns early if template loading fails
- Catches and logs errors during data preparation

---

#### `common_prepare_data_wrapper(metadata, specific_prepare_fn)`

**Purpose**: Creates a wrapper function that applies common setup and chart-specific logic.

**Common Setup** (currently disabled):
```python
# Title, subtitle, footnote disabled - handled in frontend
# template["title"]["text"] = metadata.get("Title", "")
# template["title"]["subtext"] = metadata.get("Subtitle", "")
# Set footnote in graphic elements
```

**Active Setup**:
```python
# Shuffle color palette for visual variety
shuffled_color = random.sample(template["color"], len(template["color"]))
template["color"] = shuffled_color
```

**Returns**: Wrapped function that:
1. Applies common setup
2. Calls chart-specific preparation function

---

### 6. Chart Type Processors

#### `process_charts(charts_data, charts_config, template_folder_path, output_dir, global_template_path)`

**Purpose**: Main processing function that generates all charts.

**Algorithm**:
```python
for chart_id, chart_info in charts_data.items():
    metadata = chart_info["metadata"]
    dataset = chart_info["dataset"]
    chart_type = metadata["Chart Type"].strip().lower()
    style = charts_config.get(chart_id, {})
    
    if chart_type == "bar chart vertical":
        # Process bar chart vertical
    elif chart_type == "bar chart horizontal":
        # Process bar chart horizontal
    # ... etc for each chart type
    else:
        print(f"Skipping {chart_id}: Unsupported chart type")
```

---

## Chart Type Specifications

### Bar Chart Vertical

**Configuration Requirements**:
```python
{
    "Category": str,  # Column name for x-axis
    "Value": str      # Column name for y-axis
}
```

**Template**: `bar_chart_vertical_template.json`

**Preparation Logic**:
```python
def specific_prepare(template, df):
    # Validate columns exist
    if x_col not in df.columns or y_col not in df.columns:
        raise ValueError
    
    # Wrap labels for readability
    raw_labels = df[x_col].tolist()
    wrapped_labels = [wrap_label(str(label)) for label in raw_labels]
    
    # Populate template
    template["xAxis"]["data"] = wrapped_labels
    template["xAxis"]["name"] = wrap_label(x_col)
    template["yAxis"]["name"] = wrap_label(y_col)
    template["series"][0]["data"] = df[y_col].tolist()
    
    # Adjust layout based on category count
    if len(wrapped_labels) > 10:
        template["xAxis"]["axisLabel"]["rotate"] = 45
        template["grid"]["bottom"] = 150
    else:
        max_lines = max(label.count("\n") + 1 for label in wrapped_labels)
        template["grid"]["bottom"] = 80 + 20 * (max_lines - 1)
```

**Layout Adjustments**:
- **≤10 categories**: Bottom padding = 80 + 20 × (max_lines - 1)
- **>10 categories**: Rotate labels 45°, bottom padding = 150

---

### Bar Chart Horizontal

**Configuration Requirements**:
```python
{
    "Category": str,  # Column name for y-axis
    "Value": str      # Column name for x-axis
}
```

**Template**: `bar_chart_horizontal_template.json`

**Preparation Logic**:
```python
def specific_prepare(template, df):
    raw_labels = df[y_col].tolist()
    wrapped_labels = [wrap_label(str(label)) for label in raw_labels]
    
    template["yAxis"]["data"] = wrapped_labels
    template["yAxis"]["name"] = wrap_label(y_col)
    template["xAxis"]["name"] = wrap_label(x_col)
    template["series"][0]["data"] = df[x_col].tolist()
```

**Note**: No rotation needed; horizontal bars accommodate long labels naturally.

---

### Bar Chart Categories Vertical

**Configuration Requirements**:
```python
{
    "Category": str,            # Column name for x-axis
    "Value Series": list[str],  # Column names for multiple series
    "Value Series Unit": str    # Y-axis label
}
```

**Template**: `bar_chart_categories_vertical_template.json`

**Preparation Logic**:
```python
def specific_prepare(template, df):
    # Parse series columns if provided as comma-separated string
    if isinstance(series_cols, str):
        series_cols = [s.strip() for s in series_cols.split(',')]
    
    # Wrap category labels
    wrapped_labels = [wrap_label(str(label)) for label in df[category_col]]
    
    template["xAxis"]["data"] = wrapped_labels
    template["xAxis"]["name"] = wrap_label(category_col)
    template["yAxis"]["name"] = wrap_label(series_cols_unit)
    
    # Create series for each column
    template["series"] = [
        {"name": col, "type": "bar", "data": df[col].tolist()}
        for col in series_cols
    ]
    
    # Apply rotation logic
```

**Legend**: Automatically generated from series names.

---

### Bar Chart Categories Horizontal

**Configuration Requirements**: Same as vertical variant

**Template**: `bar_chart_categories_horizontal_template.json`

**Key Difference**: Y-axis contains categories, X-axis contains values.

---

### Bar Chart Stacked Vertical

**Configuration Requirements**:
```python
{
    "Category": str,
    "Value Series": list[str],
    "Value Series Unit": str
}
```

**Template**: `bar_chart_stacked_vertical_template.json`

**Preparation Logic**:
```python
template["series"] = [
    {
        "name": col,
        "type": "bar",
        "stack": "total",  # Key difference: all series share stack ID
        "emphasis": {"focus": "series"},
        "data": df[col].tolist()
    }
    for col in series_cols
]
```

**Stacking Behavior**: All series with same `stack` ID are stacked vertically.

---

### Bar Chart Stacked Normalized Vertical

**Configuration Requirements**: Same as stacked variant

**Template**: `bar_chart_stacked_normalized_vertical_template.json`

**Preparation Logic**:
```python
# Convert to numeric
df[series_cols] = df[series_cols].apply(pd.to_numeric, errors='coerce')

# Calculate totals per category
total_series = df[series_cols].sum(axis=1).replace(0, 1)

# Normalize each series
normalized_data = [(df[col] / total_series).tolist() for col in series_cols]

# Use base series template
base_series = template["series"][0]
template["series"] = [
    {
        **base_series,
        "name": col,
        "data": data
    }
    for col, data in zip(series_cols, normalized_data)
]
```

**Output**: Values sum to 1.0 (100%) for each category.

---

### Bar Chart Stacked Horizontal

**Configuration Requirements**: Same as vertical stacked

**Template**: `bar_chart_stacked_horizontal_template.json`

**Key Difference**: Categories on Y-axis, values on X-axis.

---

### Pie Chart

**Configuration Requirements**:
```python
{
    "Category": str,  # Column for slice names
    "Value": str      # Column for slice values
}
```

**Template**: `pie_chart_template.json`

**Preparation Logic**:
```python
template["series"][0]["data"] = [
    {"name": row[name_col], "value": row[value_col]}
    for _, row in df.iterrows()
]

# Remove axis definitions (not needed for pie charts)
template.pop("xAxis", None)
template.pop("yAxis", None)
```

---

### Doughnut Chart

**Configuration Requirements**: Same as pie chart

**Template**: `doughnut_chart_template.json`

**Key Difference**: Template defines inner radius to create ring shape.

---

### Scatter Chart

**Configuration Requirements**:
```python
{
    "X Axis": str,  # Column for x-coordinates
    "Y Axis": str   # Column for y-coordinates
}
```

**Template**: `scatter_chart_template.json`

**Preparation Logic**:
```python
template["series"][0]["data"] = df[[x_col, y_col]].values.tolist()
template["xAxis"]["name"] = wrap_label(x_col)
template["yAxis"]["name"] = wrap_label(y_col)
```

**Data Format**: `[[x1, y1], [x2, y2], ...]`

---

### Scatter Chart Categories

**Configuration Requirements**:
```python
{
    "Category": str,    # Column for grouping points
    "X Axis": str,      # Column for x-coordinates
    "Y Axis": str,      # Column for y-coordinates
    "Tooltip": str      # Optional: Column for tooltip text
}
```

**Template**: `scatter_chart_categories_template.json`

**Preparation Logic**:
```python
use_tooltip = bool(tooltip_col and tooltip_col.strip())

prototype_series = template["series"][0]
grouped = df.groupby(category_col)

template["series"] = []
for name, group_df in grouped:
    series_data = []
    for _, row in group_df.iterrows():
        if use_tooltip:
            point = {
                "value": [row[x_col], row[y_col]],
                "tooltip": str(row[tooltip_col])
            }
        else:
            point = [row[x_col], row[y_col]]
        series_data.append(point)
    
    series_entry = {
        **prototype_series,
        "name": name,
        "data": series_data
    }
    template["series"].append(series_entry)
```

**Features**:
- Multiple series (one per category)
- Optional custom tooltip per point

---

### Line Chart

**Configuration Requirements**:
```python
{
    "X Axis": str,  # Column for x-axis (typically time/sequence)
    "Y Axis": str   # Column for y-values
}
```

**Template**: `line_chart_template.json`

**Preparation Logic**:
```python
template["xAxis"]["data"] = df[x_col].tolist()
template["series"][0]["data"] = df[y_col].tolist()
template["series"][0]["name"] = y_col
template["xAxis"]["name"] = wrap_label(x_col)
template["yAxis"]["name"] = wrap_label(y_col)
```

---

### Line Chart Multi

**Configuration Requirements**:
```python
{
    "X Axis": str,                # Column for x-axis
    "Y Axis Series": list[str],   # Columns for multiple lines
    "Value Series Unit": str      # Y-axis label
}
```

**Template**: `line_chart_multi_template.json`

**Preparation Logic**:
```python
if isinstance(y_cols, str):
    y_cols = [s.strip() for s in y_cols.split(',')]

template["xAxis"]["data"] = df[x_col].tolist()
template["xAxis"]["name"] = wrap_label(x_col)
template["yAxis"]["name"] = wrap_label(series_cols_unit)

template["series"] = [
    {
        "type": "line",
        "name": col,
        "data": df[col].tolist()
    }
    for col in y_cols
]
```

---

### Line Chart Stacked

**Configuration Requirements**: Same as multi-line

**Template**: `line_chart_stacked_template.json`

**Preparation Logic**:
```python
template["series"] = [
    {
        "name": col,
        "type": "line",
        "stack": "Total",  # All series stacked
        "areaStyle": {},   # Filled area under line
        "data": df[col].tolist()
    }
    for col in series_cols
]
```

**Visual**: Area chart with stacked regions.

---

## Execution Flow (Jupyter Notebook)

### Cell 1: Setup

```python
import json
import charts_functions as cf

# Define all I/O paths
path_in_metadata = "../02_Inputs/charts/Metadata/Charts Tracker.xlsx"
path_in_datasets = "../02_Inputs/charts/Data/Charts"
path_out_charts_data_json = "../02_Inputs/charts/Data/Charts/charts_data.json"
path_charts_template_folder = "../02_Inputs/charts/Templates"
path_charts_global_template_light = "../02_Inputs/charts/Templates/_charts_global_template_light.json"
path_charts_global_template_dark = "../02_Inputs/charts/Templates/_charts_global_template_dark.json"
path_charts_config = "../02_Inputs/charts/Metadata/Charts Config.xlsx"
path_chart_output_light = "../03_Outputs/charts/Auto Charts/LightMode"
path_chart_output_dark = "../03_Outputs/charts/Auto Charts/DarkMode"
```

---

### Cell 2: Extract Chart Data

```python
# Import Metadata/Datasets
metadata = cf.extract_metadata(path_in_metadata)
datasets = cf.extract_dataset(path_in_datasets)

# Merge Metadata/Datasets
charts = cf.merge_data_metadata(metadata, datasets)

# Save Dictionary to Device (optional)
with open(path_out_charts_data_json, "w", encoding="utf-8") as f:
    json.dump(charts, f, indent=2, ensure_ascii=False)
```

**Output**: Console logging of filtering statistics and chart addition status.

---

### Cell 3: Generate Charts

```python
# Load charts data
charts_data = cf.load_json_file(path_out_charts_data_json)

# Load charts config
charts_config = cf.load_charts_config(path_charts_config)

# Generate Light Mode Charts
cf.process_charts(
    charts_data=charts_data,
    charts_config=charts_config,
    template_folder_path=path_charts_template_folder,
    output_dir=path_chart_output_light,
    global_template_path=path_charts_global_template_light
)

# Generate Dark Mode Charts
cf.process_charts(
    charts_data=charts_data,
    charts_config=charts_config,
    template_folder_path=path_charts_template_folder,
    output_dir=path_chart_output_dark,
    global_template_path=path_charts_global_template_dark
)
```

**Output**: Two sets of JSON files (light and dark mode) for each chart.

---

## Output Format

### Apache ECharts JSON Structure

```json
{
  "title": {
    "text": "Chart Title",
    "subtext": "Subtitle",
    "left": "center"
  },
  "color": ["#5470c6", "#91cc75", "#fac858", ...],
  "tooltip": {
    "trigger": "axis",
    "axisPointer": {
      "type": "shadow"
    }
  },
  "legend": {
    "data": ["Series 1", "Series 2"],
    "top": "5%"
  },
  "grid": {
    "left": "3%",
    "right": "4%",
    "bottom": 80,
    "containLabel": true
  },
  "xAxis": {
    "type": "category",
    "data": ["Cat1", "Cat2", "Cat3"],
    "name": "Category",
    "axisLabel": {
      "rotate": 0
    }
  },
  "yAxis": {
    "type": "value",
    "name": "Value"
  },
  "series": [
    {
      "name": "Series 1",
      "type": "bar",
      "data": [100, 150, 80]
    }
  ]
}
```

---

## Error Handling Strategy

### Level 1: File-Level Errors
- Missing Excel files
- Corrupt Excel files
- Missing template files

**Behavior**: Print error, return `None`, halt processing for that item.

---

### Level 2: Data-Level Errors
- Missing required columns
- Invalid data types
- Empty datasets

**Behavior**: Print error, skip chart, continue with next chart.

---

### Level 3: Configuration Errors
- Missing chart config entries
- Unsupported chart types

**Behavior**: Print warning, skip chart, continue with next chart.

---


## Debugging and Troubleshooting

### Console Output Analysis

**Chart Generation Output**:
```
---
Generating chart for M1_C1_2...
Title: The Human Development Index (HDI) and energy use per capita, 2019
Saved chart to ../03_Outputs/charts/Auto Charts/LightMode/M1_C1_2.json
```

**Skip Messages**:
```
Skipping M1_C3_27: Unsupported chart type 'morphing between map and bar'
```

**Error Messages**:
```
Failed to read sheet 'Sheet1' in 'Module 1.xlsx': [error details]
Missing styling for bar chart vertical: M1_C1_2
```

---

### Common Issues and Solutions

#### Issue: "Missing columns: X, Y"
**Cause**: Chart config references columns that don't exist in dataset.

**Solution**:
1. Check dataset sheet for correct column names
2. Verify Chart Config entries match exactly (case-sensitive)
3. Check for leading/trailing spaces in column names

---

#### Issue: Charts not generated despite being in tracker
**Cause**: Failed one or more filter conditions.

**Solution**:
1. Check console output for filtering reasons
2. Verify all required fields in Chart Tracker:
   - `Category` = "Chart to recreate"
   - `Apache Possible` = "Yes"
   - `Automation Possible` = "Yes"
   - `Dataset Status` = "Ready"

---

#### Issue: "Unsupported chart type"
**Cause**: Chart type doesn't match any implemented handlers.

**Solution**:
1. Check spelling in Chart Tracker `Chart Type` column
2. Verify chart type is supported (see [Chart Type Specifications](#chart-type-specifications))
3. Use exact naming convention (lowercase with spaces)
4. For unsupported types, use custom LLM prompt approach

---

## Extension Guide

### Adding New Chart Types

**Step 1**: Create Template File
```json
// new_chart_type_template.json
{
  "title": {},
  "tooltip": {},
  "xAxis": {},
  "yAxis": {},
  "series": [
    {
      "type": "newChartType",
      "data": []
    }
  ]
}
```

**Step 2**: Add Handler to `process_charts()`
```python
elif chart_type == "new chart type":
    required_cols = style.get("RequiredConfig")
    
    if required_cols:
        template_path = Path(template_folder_path) / "new_chart_type_template.json"
        
        def specific_prepare(template, df):
            # Validation
            if required_col not in df.columns:
                raise ValueError(f"Missing column: {required_col}")
            
            # Data transformation
            template["series"][0]["data"] = process_data(df)
            
            # Axis configuration
            template["xAxis"]["name"] = wrap_label(x_col)
            template["yAxis"]["name"] = wrap_label(y_col)
        
        prepare_data = common_prepare_data_wrapper(metadata, specific_prepare)
        generate_chart(chart_id, metadata, dataset, template_path, 
                      output_dir, prepare_data, global_template_path)
    else:
        print(f"Missing styling for new chart type: {chart_id}")
```

**Step 3**: Update Documentation
- Add chart type to supported list
- Document required configuration fields
- Provide example

---

### Modifying Global Templates

**Light Mode** (`_charts_global_template_light.json`):
```json
{
  "backgroundColor": "#ffffff",
  "textStyle": {
    "color": "#333333"
  },
  "title": {
    "textStyle": {
      "color": "#333333"
    }
  },
  "legend": {
    "textStyle": {
      "color": "#333333"
    }
  },
  "color": ["#5470c6", "#91cc75", "#fac858", ...]
}
```

**Dark Mode** (`_charts_global_template_dark.json`):
```json
{
  "backgroundColor": "#1a1a1a",
  "textStyle": {
    "color": "#e0e0e0"
  },
  "title": {
    "textStyle": {
      "color": "#e0e0e0"
    }
  },
  "legend": {
    "textStyle": {
      "color": "#e0e0e0"
    }
  },
  "color": ["#6fa8dc", "#93c47d", "#ffd966", ...]
}
```

**Impact**: Changes apply to all generated charts.
