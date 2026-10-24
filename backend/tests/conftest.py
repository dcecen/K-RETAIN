import os
import sys
from pathlib import Path

# Rend le paquet « sout » importable sans installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Les tests d'API supposent l'accès libre : une variable laissée par lancer_production.ps1
# dans le même terminal rendrait presque toutes les routes 401.
os.environ.pop("RETAINWALL_AUTH", None)
