# SnapGene History Exporter

## Overview

The SnapGene History Exporter is a Python tool designed to extract and export the history of DNA sequences from SnapGene files. This tool allows users to analyze and manage the history of their DNA sequences efficiently.

## Features

- Extracts history data from SnapGene files.
- Exports history data in a readable format.
- Supports batch processing of multiple SnapGene files.

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/MinTTT/snapgene_history_exporter.git
    ```
2. Navigate to the project directory:
    ```sh
    cd snapgene-history-exporter
    ```
3. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

To use the SnapGene History Exporter, run the `snapgene_history_exporter.py` script with the desired SnapGene file as an argument:

```sh
python ./snapgene_history_exporter.py -i [path/to/your/snapgene/files]
```

If it works, you will get a assembly summarize table `all_assemblies_summary.xlsx`, whose first sheet summarizes the fragments need to PCR, the second sheet summarizes the fragments used for construction, and the last one contains the primers used in you constructions.

## Acknowledgments

This project uses code from the IsaacLuo/SnapGeneFileReader repository. We would like to thank Isaac Luo and the Cai Lab for their contributions to the open-source community.

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Contact
For any questions or suggestions, please open an issue on GitHub or contact the project maintainer at pan_chu@outlook.com.