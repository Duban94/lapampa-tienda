#!/bin/bash
cd "$(dirname "$0")"
python3 -m pip install --quiet flask openpyxl pyxlsb
python3 app.py
