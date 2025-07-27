# 📘 User Guide: SEA Chart Generator

This guide explains how to use the SEA Chart Pipeline to add and generate charts. It covers the key components of the system and provides step-by-step instructions for both manual and automated workflows.


## How to Add a Chart to the pipeline

### Step 1: Add Metadata to the Chart Tracker

- Open the **Chart Tracker Excel file** (`Charts Tracker.xlsx`)
- Go to the sheet of the relevant module
- Add a new row and fill out all columns
- Note that only permissible values may be entered (In-depth explanation of columns can be found here: [Chart Tracker](#chart-tracker))

 Reference: [Chart Tracker](#chart-tracker)


### Step 2: Add the Dataset

- Open the Excel file for datasets of the appropriate module (e.g., `Module 1 - Datasets for Charts.xlsx`)
- Create a new sheet named after the chart
- Format the dataset by removing all excess information (See formatting guidelines here: [Datasets](#datasets))
- Insert the dataset starting at cell **A1**

 Reference: [Datasets](#datasets)

 **Checklist**:
- Headers in Row 1
- No extra top or bottom rows
- No metadata or notes


### Step 3: Link the Dataset
- In the **Chart Tracker**, fill in the `Dataset Link` column with the figure ID and a hyperlink to the dataset sheet you just added.


## How to Create a Chart with the pipeline

As a first step, check whether the chart needs to be recreated or can be used from source. 
If it needs to be recreated follow one of the two options: Automatic via the pipeline, or custom via the LLM prompt.


### Option 1: Automatic Chart Creation

Here, common chart types can be generated fully automatically after correctly adding the dataset, metadata (**Charts Tracker**) and adding necessary logic for the chart generation (**Charts Config**)

#### Steps:

1. In the **Chart Tracker**:
   - Set `Category` to `Chart to Recreate`
   - Check if the chart type is supported [Templates](#templates)
   - If supported, set `Automated processing` to `Yes`
   - Enter the **exact chart type** corresponding to the [Templates](#templates) in the `Chart type` column

2. Fill in **Chart Config** with required parameters for the selected chart type
    - Open the **Chart Config Excel file** (`SEA Charts Config.xlsx`)
    - Check within the [Chart Config](#chart-config), which additional information of the chart has to be added to Chart config for your selected chart type.
    - Add new rows to the chart config with the `Figure ID`, `Property` and `Column Name`.

3. The chart will be automatically processed and rendered with styling defined by the template.

 Reference:
- [Templates](#templates)
- [Chart Config](#charts-config)



### Option 2: Custom Chart with LLM Prompt

For **unsupported chart types**:

1. In the **Chart Tracker**:
   - Set `Category` to `Chart to Recreate`
   - Set `Automated processing` to `No`

2. Open the **Chart Prompt Template** ( *link TBD*), and fill in:
   - Metadata
   - Dataset
   - Further Instructions
   - Reference chart (Apache E-Chart, etc.)

3. Paste the completed prompt into an LLM to generate a chart rendering script.

 Reference: [Chart Prompt Template](#chart-prompt-template)




The diagram illustrates the full end-to-end flow for  generating a chart.
 *[Insert workflow image here]*





## Key Components

### Chart Tracker

The **Chart Tracker** is the central control file that manages chart metadata and status across modules. Each row represents one chart.
Below is a list of columns and their expected input values:
| Column              | Description                              | Expected Input Values                      | Obligatory/Optional |
| ------------------- | ---------------------------------------- | ------------------------------------------ | ------------------- |
| Chapter             | Number of Chapter                        | Numerical (Integer)                        | Obligatory          |
| #                   | Serial number within chapter             | Numerical (Integer)                        | Obligatory          |
| Figure ID           | Serial number to uniquely identify chart | Text (String)                              | Obligatory          |
| Title               | Title of the figure                      | Text (String)                              | Obligatory          |
| Subtitle            | Additional description below the title   | Text (String)                              | Optional            |
| Screenshot          | Original screenshot                      | Image (JPG/PNG)                            | Optional            |
| New Screenshot      | Updated or annotated screenshot          | Image (JPG/PNG)                            | Optional            |
| Lead                | Person responsible for this figure       | Text (String)                              | Obligatory            |
| Source (APA)        | Bibliographic source                     | Text (String)                              | Obligatory            |
| Footnote            | Footnote within the Chart                  | Text (String)                              | Optional            |
| Source Link         | Link to original data or reference       | Text (String) with Hyperlink               | Obligatory            |
| Dataset Link        | Link to dataset location (Excel Sheet)   | Text (String) with Hyperlink               | Obligatory            |
| Chart Status        | Availability status of chart | Factor (Ready \| Pending)                      | Obligatory          |
| Dataset Status      | Availability status of the underlying dataset | Factor (Ready \| Pending) | Obligatory          |
| Category            | Chart classification                     | Factor (Chart to Recreate \| Ready to Use) | Obligatory          |
| Chart Type          | Type of visualization                    | Factor (Bar Chart \| Pie Chart \| ...)     | Obligatory          |
| Apache possible     | Can it be created as an Apache e-Chart?   | Category (Yes \| No \| Unsure)                    | Obligatory            |
| Apache Link         | Link to Apache e-Chart example        | Text (String) with Hyperlink               | Optional            |
| Automation possible | Can the chart be automated via the charts pipeline?              | Category (Yes \| No \| Unsure)                   | Obligatory            |
| Notes               | Any extra information                    | Text (String)                              | Optional    


 **Note**: All obligatory columns must be filled out correctly to ensure smooth processing.

---

### Datasets


**Formatting Guidelines**:
- Start at cell **A1**
- Row 1 must contain **column headers**
- Data rows begin immediately after headers
- Remove all extraneous rows (titles, notes, metadata)

 Improper formatting could cause the pipeline to fail.

---

###  Templates

Templates define the **visual layout** and **styling** for each supported chart type.

- Stored in: `02_Inputs/Templates/`
- Predefined for each chart type
- Applied automatically during chart creation

The pipeline currently supports the following chart types:

* Bar Chart Vertical
* Bar Chart Horizontal
* Bar Chart Categories Horizontal
* Bar Chart Categories Vertical
* Bar Chart Stacked Horizontal
* Bar Chart Stacked Vertical
* Pie Chart
* Scatter Chart
* Scatter Chart Categories
* Line Chart
* Line Chart Multi
* Line Chart Stacked

 Each chart type expects additional configuration information which needs to be added to the [Chart Config](#charts-config).

 **Templates are fixed** and cannot be modified by the user. Styling includes fonts, colors, labels, etc.

---

### Chart Config

This file provides **advanced configuration** for charts that need more than basic metadata, such as:

- Which columns of the dataset to use for X and Y axes
- Grouping or filtering logic
- Optional labels or scaling options

The following table lists the obligatory properties for each Chart Type:

| **Chart Type**                  | **Properties**           | **Description**                                                                 |
|--------------------------------|--------------------------|---------------------------------------------------------------------------------|
| Bar Chart Vertical             | Category                 | Name of the Dataset Column of the Bar Chart categories                         |
|                                | Value                    | Name of the Dataset Column of the Bar Chart values                              |
| Bar Chart Horizontal           | Category                 | Name of the Dataset Column of the Bar Chart categories                         |
|                                | Value                    | Name of the Dataset Column of the Bar Chart values                              |
| Bar Chart Categories Vertical  | Category                 | Name of the Dataset Column of the Bar Chart categories                         |
|                                | Value Series             | Names of Dataset Columns representing different value series for each category |
| Bar Chart Categories Horizontal| Category                 | Name of the Dataset Column of the Bar Chart categories                         |
|                                | Value Series             | Names of Dataset Columns representing different value series for each category |
| **Bar Chart Stacked Vertical** | Category                 | Name of the Dataset Column of the Bar Chart categories                         |
|                                | Series Columns           | Names of Dataset Columns to be stacked per category                            |
| **Bar Chart Stacked Horizontal**| Category                | Name of the Dataset Column of the Bar Chart categories                         |
|                                | Series Columns           | Names of Dataset Columns to be stacked per category                            |
| Pie Chart                      | Category                 | Name of the Dataset Column of the Pie Chart names                              |
|                                | Value                    | Name of the Dataset Column of the Pie Chart values                             |
| Scatter Chart Categories       | Category                 | Name of the Dataset Column of the data point categories                        |
|                                | X Axis                   | Name of the Dataset Column for X values                                        |
|                                | Y Axis                   | Name of the Dataset Column for Y values                                        |
| Scatter Chart                  | X Axis                   | Name of the Dataset Column for X values                                        |
|                                | Y Axis                   | Name of the Dataset Column for Y values                                        |
| Line Chart                     | X Axis                   | Name of the Dataset Column for X values                                        |
|                                | Y Axis                   | Name of the Dataset Column for Y values                                        |
| Line Chart Multi               | X Axis                   | Name of the Dataset Column for X values                                        |
|                                | Y Axis Series            | Names of Dataset Columns representing different series for Y axis              |
| Line Chart Stacked             | X Axis                   | Name of the Dataset Column for X values                                        |
|                                | Y Axis Series            | Names of Dataset Columns to be stacked per X value                             |


---

### Chart Prompt Template

For unsupported chart types, a **Chart Prompt Template** is used to create charts via a Large Language Model (LLM).

- **Stored in:** `02_Inputs/Templates/custom_prompt_template`

This template includes:
- Chart metadata
- Dataset
- Reference chart
- Instructions for rendering

#### How to use

1. Copy the entire contents of the `custom_prompt_template` file.
2. Fill in the necessary parts (chart metadata, dataset, reference chart, instructions) with the details relevant to your specific chart.
3. Use the completed prompt to generate your chart via the LLM.



---

##  Need Help?

For technical issues, submit a GitHub Issue or contact the maintainer.
