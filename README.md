# dsc-energy-academy-pipeline

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![License](https://img.shields.io/github/license/undp-data/dsc-energy-academy-pipeline)](https://github.com/undp-data/dsc-energy-academy-pipeline/blob/main/LICENSE)
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-%23FE5196?logo=conventionalcommits&logoColor=white)](https://conventionalcommits.org)

A simple package to to process Figma designs and transform them into a standardised JSON format for the Sustainable Energy Academy.

> [!WARNING]  
> The package is currently under active development. Some features may be missing or not working as intended. Feel free to [open an issue](https://github.com/UNDP-Data/dsc-energy-academy-pipeline/issues).

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Installation

The package can be installed directly from GitHub using `pip`:

```bash
pip install git+https://github.com/undp-data/dsc-energy-academy-pipeline
```

See [VCS Support](https://pip.pypa.io/en/stable/topics/vcs-support/#vcs-support) for more details.
If you have cloned the repository, you can create a virtual environment and install the editable version of the package using the Makefile

```bash
python -m venv .venv
source .venv/bin/activate
make install
```

## Usage

See [`main.ipynb`](https://nbviewer.org/github/undp-data/dsc-energy-academy-pipeline/blob/main/main.ipynb) which provides an brief introduction.

## Contributing

All contributions must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
The codebase is formatted with `black` and `isort`. Use the provided [Makefile](./Makefile) for these
routine operations.

1. Clone or fork the repository
2. Create a new branch (`git checkout -b feature-branch`)
3. Make your changes
4. Ensure your code is properly formatted (`make format`)
5. Commit your changes (`git commit -m 'Add some feature'`)
6. Push to the branch (`git push origin feature-branch`)
7. Open a pull request

## License

This project is licensed under the BSD 3-Clause License. See the [LICENSE](./LICENSE) file.
