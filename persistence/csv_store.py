"""
persistence/csv_store.py — Lecture des référentiels CSV des cycles 3 et 4.

Référentiels stables (non modifiés par l'application) :
  - param_niveaux.csv   : 6 niveaux (N07..N12), lien niveau → cycle
  - C03_sequences.csv   : 15 séquences du cycle 3 (CM1, CM2, 6ème)
  - C03_themes.csv      : 3 thèmes du cycle 3
  - C04_sequences.csv   : 14 séquences du cycle 4 (5ème, 4ème, 3ème)
  - C04_themes.csv      : 4 thèmes du cycle 4

Toutes les méthodes retournent des dicts indexés par le code, avec
des clés en minuscules.
"""

from __future__ import annotations
import csv
from pathlib import Path


class CsvStore:
    """Lecture des fichiers CSV de référentiel."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir

    # ── Niveaux (table commune aux deux cycles) ───────────────────────────

    def lire_param_niveaux(self) -> dict:
        """
        Retourne {code: {code, code_cycle, annee_dans_cycle, nom_court,
        nom_long}} depuis param_niveaux.csv. Retourne {} si absent.

        C'est la source de vérité du lien niveau → cycle, qui était
        auparavant dupliquée en dur dans `services/resoudre_macros.py`
        (table `PARAM_NIVEAUX`). Elle reste rare à mettre à jour (les
        niveaux collège/élémentaire ne bougent pas), mais on l'unifie
        pour éviter la divergence avec `param_niveaux.dbtex` côté
        paquet LaTeX.
        """
        p = self.data_dir / "param_niveaux.csv"
        if not p.exists():
            return {}
        result = {}
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                result[row["Code"]] = {
                    "code":             row["Code"],
                    "code_cycle":       row["CodeCycle"],
                    "annee_dans_cycle": row["AnneeDansCycle"],
                    "nom_court":        row["NomCourt"],
                    "nom_long":         row["NomLong"],
                }
        return result

    # ── Séquences : C03 et C04 ────────────────────────────────────────────

    def lire_c03_sequences(self) -> dict:
        """
        Retourne {code_seq: {code, numero, nom, theme}} depuis C03_sequences.csv.
        Retourne {} si le fichier est absent.
        """
        return self._lire_sequences("C03_sequences.csv")

    def lire_c04_sequences(self) -> dict:
        """
        Retourne {code_seq: {code, numero, nom, theme}} depuis C04_sequences.csv.
        Retourne {} si le fichier est absent.
        """
        return self._lire_sequences("C04_sequences.csv")

    def _lire_sequences(self, nom_fichier: str) -> dict:
        p = self.data_dir / nom_fichier
        if not p.exists():
            return {}
        result = {}
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                result[row["Code"]] = {
                    "code":   row["Code"],
                    "numero": int(row["Numero"]),
                    "nom":    row["Nom"],
                    "theme":  row["Theme"],
                }
        return result

    # ── Thèmes : C03 et C04 ───────────────────────────────────────────────

    def lire_c03_themes(self) -> dict:
        """
        Retourne {code_theme: {code, nom, code_couleur, description}}
        depuis C03_themes.csv. Retourne {} si le fichier est absent.
        """
        return self._lire_themes("C03_themes.csv")

    def lire_c04_themes(self) -> dict:
        """
        Retourne {code_theme: {code, nom, code_couleur, description}}
        depuis C04_themes.csv. Retourne {} si le fichier est absent.
        """
        return self._lire_themes("C04_themes.csv")

    def _lire_themes(self, nom_fichier: str) -> dict:
        p = self.data_dir / nom_fichier
        if not p.exists():
            return {}
        result = {}
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                result[row["Code"]] = {
                    "code":         row["Code"],
                    "nom":          row["Nom"],
                    "code_couleur": row["CodeCouleur"],
                    "description":  row.get("Description", ""),
                }
        return result

    # ── Connaissances : C03 et C04 ────────────────────────────────────────
    # Clé composite (CodeNiveau, CodeSequence, CodeConnaissance)

    def lire_c03_connaissances(self) -> dict:
        """
        Retourne {(niveau, sequence, code): nom} depuis C03_connaissances.csv.
        Retourne {} si le fichier est absent.
        """
        return self._lire_connaissances("C03_connaissances.csv")

    def lire_c04_connaissances(self) -> dict:
        """
        Retourne {(niveau, sequence, code): nom} depuis C04_connaissances.csv.
        Retourne {} si le fichier est absent.
        """
        return self._lire_connaissances("C04_connaissances.csv")

    def _lire_connaissances(self, nom_fichier: str) -> dict:
        p = self.data_dir / nom_fichier
        if not p.exists():
            return {}
        result = {}
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                cle = (row["CodeNiveau"], row["CodeSequence"], row["CodeConnaissance"])
                result[cle] = row["Nom"]
        return result

    # ── Objectifs : C03 et C04 ────────────────────────────────────────────
    # Clé composite (CodeNiveau, CodeSequence, CodeObjectif)
    # Valeur : dict avec nom, fin_cycle, maitrise_tb, maitrise_s, maitrise_f

    def lire_c03_objectifs(self) -> dict:
        """
        Retourne {(niveau, sequence, code): {nom, fin_cycle, maitrise_tb,
        maitrise_s, maitrise_f}} depuis C03_objectifs.csv.
        Retourne {} si le fichier est absent.
        """
        return self._lire_objectifs("C03_objectifs.csv")

    def lire_c04_objectifs(self) -> dict:
        """
        Retourne {(niveau, sequence, code): {nom, fin_cycle, maitrise_tb,
        maitrise_s, maitrise_f}} depuis C04_objectifs.csv.
        Retourne {} si le fichier est absent.
        """
        return self._lire_objectifs("C04_objectifs.csv")

    def _lire_objectifs(self, nom_fichier: str) -> dict:
        p = self.data_dir / nom_fichier
        if not p.exists():
            return {}
        result = {}
        with open(p, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                cle = (row["CodeNiveau"], row["CodeSequence"], row["CodeObjectif"])
                result[cle] = {
                    "nom":         row["Nom"],
                    "fin_cycle":   row.get("FinCycle", "N"),
                    "maitrise_tb": row.get("MaitriseTB", ""),
                    "maitrise_s":  row.get("MaitriseS", ""),
                    "maitrise_f":  row.get("MaitriseF", ""),
                }
        return result

    # ── Helpers de plus haut niveau ───────────────────────────────────────

    def sequences_avec_themes(self) -> list:
        """
        Retourne la liste des séquences du cycle 4 enrichies avec les
        infos de thème, triée par numéro. Utilisé par
        /api/referentiel/sequences.
        """
        sequences = self.lire_c04_sequences()
        themes = self.lire_c04_themes()
        result = []
        for code, seq in sorted(sequences.items(), key=lambda x: x[1]["numero"]):
            theme = themes.get(seq["theme"], {})
            result.append({
                **seq,
                "theme_nom":     theme.get("nom", ""),
                "theme_couleur": theme.get("code_couleur", ""),
            })
        return result

    def c04_disponible(self) -> bool:
        return (self.data_dir / "C04_sequences.csv").exists()
