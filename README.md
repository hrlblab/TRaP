# TRaP_App
A standardized RAMAN Process Application via Python

This is a new version for the standardized RAMAN Process Application with GUI via python. 

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Built With](#built-with)
- [Getting Started](#getting-started)
- [Tutorial](#tutorial)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
  

## Overview
The TRaP APP is designed for a standard RAMAN Process Application with GUI via python, delivering a user-friendly software for both beginners and professionals.

## Features
Working on.

## Project Structure
```bash
TRaP_App/
├── data/                 # Example data for test purpose
├── UI_utils/             # UI initialization tools
├── utils/                # Build-in mathematical functions 
│   └── io/               # Standardized IO functioins 
├── TRaP_GUI.py           # Main function entrance
├── .gitignore            # Git ignore rules
└── README.md             # Project overview and documentation
```

### UI_utils package
The `UI_utils` package is designed to encapsulate common UI functions used across the application:
- **UI_Config_Manager.py:**  
  Contains an UI builder and config manager class that allow users to save and load the parameters for RAMAN process.
- **UI_P_Mean_Process.py:**  
  Contains an UI builder for P Mean process for a single fingerprint data. This UI allows users to save and load the config file for P Mean process including parameters, methods, etc. for not only processing a single fingerprint data but also optimizing the parameters for futher batch processing.
- **UI_P_Mean_Batch_Process.py:**  
  Contains an UI builder for P Mean process for multiple fingerprint data. This UI allows users to load the config file or use default setting to apply P Mean process to multiple fingerprint data.
- **UI_System_Select.py**  
  Contains an UI builder that allow users to select different systems and process steps.


## Getting Started
Follow these instructions to set up the project locally.

## Tutorial

Follow the four stages below to move from an empty workspace to calibrated, processed spectra.  
(Screenshots in *Document.docx* correspond to each numbered step.)

---

### 1. Configure Your Session

| Action | Where | Result |
|--------|-------|--------|
| **Open `Config Manager`** | Home → **Config Manager** | Configuration dialog appears |
| Select **Name** and **System** | Dropdown menus | Identifies the config to use |
| *(Optional)* Enable **X-axis Calibration** | Toggle **Use X-axis Calibration → Yes** | Adds X-axis adjustment support |
| **Save** a new config – or – **Load** an existing one | Buttons at bottom | Unlocks all other features |

---

### 2. Create a Calibration File

1. Go to **Calibration**.  
2. **Upload NeAr spectrum** and enter the expected **peak count**.  
3. On the plot, **click each peak**.  
4. Choose whether the **system wavelength is known**:  
   * **Known** → type the value.  
   * **Unknown** →  
     1. Select “No”.  
     2. **Upload acetaminophen spectrum**.  
     3. Enter its **peak count** and click peaks for alignment.  
5. Click **Process and Save** to output a `*.Cal` file.

---

### 3. Explore the *P-Mean* Workflow Interactively

| Step | What to Do | UI Element |
|------|------------|------------|
| **Set parameters** | Fill **Start**, **Stop**, and **Poly order** | Input fields |
| **Load data** | Press **Load Data Files** and choose:<br>• waveform<br>• white-light correction<br>• calibration file | File picker |
| **Visualise** | Click **Next** to progress stage-by-stage | Plot canvas updates |
| **Tune anytime** | Change parameters → click **Next** again | Immediate feedback |
| **Track progress** | **Current Step** / **Next Step** labels | Know exactly where you are |

---

### 4. Batch-Process Multiple Spectra

1. Open **Spectrum Batch Process**.  
2. **Select Data Files** → upload one or more waveforms.  
3. **Select WL Correction File** → upload the white-light correction.  
4. **Select Calibration File** → upload the `*.Cal` from Step&nbsp;2.  
5. Press **Start Batch Process**. All spectra are processed automatically and results are saved alongside the originals.

---

### Tips

* Ensure all spectra in a batch share the **same acquisition settings** as the calibration reference for best accuracy.  
* You may revisit **Config Manager** at any time—changes take effect immediately after saving.

### Prerequisites
- Python 3.11

### Installation
1. **Clone the repository:**

   ```bash
   git clone https://github.com/ZhaishenGForSaken/TRaP_App.git
   cd TRaP_App
   ```
2. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```
### Usage
Running this project by using the following command:
  ``` bash
  python TRaP_GUII.py
  ```


## Contributing

Contributions are welcome! To contribute to TRaP App, please follow these steps:

1. **Fork the Repository:**  
   Click the "Fork" button on the top right of the GitHub page to create your own copy of the project.

2. **Create a New Branch:**  
   Use a descriptive branch name for your feature or bug fix. For example:  
   ```bash
   git checkout -b feature/YourFeatureName
   ```
3. **Make Your Changes:**
   Ensure your code adheres to the project’s style guidelines and includes appropriate tests.
4. **Commit Your Changes:**
    Write clear and concise commit messages. For example:
    ```bash
    git commit -m "Add feature to improve XYZ functionality"
    ```
5. **Push to Your Branch:**
   ```bash
   git push origin feature/YourFeatureName
   ```
6. **Open a Pull Request:**
  Once your changes are ready, open a pull request on the main repository with a detailed description of your modifications.

If you encounter any issues or have questions, please open an issue to discuss your ideas before starting your work.


## Contact

For any inquiries, feedback, or additional information regarding the TRaP App project, please reach out using one of the following methods:

- **Email:** [yanfan.zhu@vanderbilt.edu](mailto:yanfan.zhu@vanderbilt.edu)
- **GitHub:** [ZhaishenGForSaken](https://github.com/ZhaishenGForSaken)

Alternatively, you can open an issue on GitHub for public discussion.
  
