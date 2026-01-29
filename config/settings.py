"""
Configuraciones y parámetros del proyecto.
"""
import os
from pathlib import Path

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuraciones generales
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Configuraciones de datos
DATA_DIR = BASE_DIR / "data"

# Configuraciones de logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

