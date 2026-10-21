"""Comptes d'accès au serveur interne (authentification HTTP Basic).

Les mots de passe sont stockés hachés (PBKDF2-HMAC-SHA256, sel aléatoire) dans
backend/data/utilisateurs.json, jamais en clair. L'authentification est active
quand la variable d'environnement RETAINWALL_AUTH vaut 1 (déploiement) ; en
développement local elle est désactivée.

Ligne de commande :
    python -m sout.utilisateurs ajouter <nom>      # demande le mot de passe
    python -m sout.utilisateurs supprimer <nom>
    python -m sout.utilisateurs lister
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

FICHIER = Path(os.environ.get("RETAINWALL_UTILISATEURS",
                              Path(__file__).resolve().parents[1] / "data" / "utilisateurs.json"))
ITERATIONS = 600_000


def _lire(fichier: Path | None = None) -> dict:
    fichier = fichier or FICHIER
    if not fichier.exists():
        return {}
    return json.loads(fichier.read_text(encoding="utf-8"))


def _ecrire(d: dict, fichier: Path | None = None) -> None:
    fichier = fichier or FICHIER
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps(d, indent=2), encoding="utf-8")


def _hacher(mot_de_passe: str, sel: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, iterations).hex()


def ajouter(nom: str, mot_de_passe: str, fichier: Path | None = None) -> None:
    if len(mot_de_passe) < 10:
        raise ValueError("mot de passe trop court (10 caractères minimum)")
    d = _lire(fichier)
    sel = secrets.token_bytes(16)
    d[nom] = {"sel": sel.hex(), "iterations": ITERATIONS, "empreinte": _hacher(mot_de_passe, sel, ITERATIONS)}
    _ecrire(d, fichier)


def supprimer(nom: str, fichier: Path | None = None) -> None:
    d = _lire(fichier)
    d.pop(nom, None)
    _ecrire(d, fichier)


def verifier(nom: str, mot_de_passe: str, fichier: Path | None = None) -> bool:
    u = _lire(fichier).get(nom)
    if u is None:
        # calcul factice pour un temps de réponse comparable
        _hacher(mot_de_passe, b"0" * 16, ITERATIONS)
        return False
    calc = _hacher(mot_de_passe, bytes.fromhex(u["sel"]), int(u["iterations"]))
    return hmac.compare_digest(calc, u["empreinte"])


def authentification_active() -> bool:
    return os.environ.get("RETAINWALL_AUTH", "0") == "1"


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("ajouter", "supprimer", "lister"):
        print(__doc__)
        sys.exit(1)
    action = sys.argv[1]
    if action == "lister":
        for n in _lire():
            print(n)
    elif len(sys.argv) < 3:
        print("nom d'utilisateur manquant")
        sys.exit(1)
    elif action == "ajouter":
        mdp = getpass.getpass(f"Mot de passe pour {sys.argv[2]} : ")
        if mdp != getpass.getpass("Confirmation : "):
            print("les deux saisies diffèrent")
            sys.exit(1)
        ajouter(sys.argv[2], mdp)
        print(f"utilisateur {sys.argv[2]} enregistré dans {FICHIER}")
    else:
        supprimer(sys.argv[2])
        print(f"utilisateur {sys.argv[2]} supprimé")
