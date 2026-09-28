"""services/auth.py — v0.23.0

Authentification simple, OPTIONNELLE, par mot de passe unique.

Contexte (cf. audit) : l'application n'a aucune authentification. Acceptable en
usage local mono-poste, mais bloquant dès qu'elle est exposée sur un serveur.
Ce module ajoute une protection minimale, **désactivée par défaut** pour ne rien
changer à l'usage local actuel.

Activation : définir la variable d'environnement `SEQ_MDP` avec le mot de passe
souhaité avant de lancer le serveur. Tant qu'elle n'est pas définie, aucune
authentification n'est demandée (comportement historique).

    # exemple (déploiement) :
    #   SEQ_MDP="mon-mot-de-passe" python app.py

Le mot de passe n'est jamais stocké en clair dans un fichier du projet : il vit
dans l'environnement. La session Flask (cookie signé) mémorise la connexion.

Ce mécanisme est volontairement minimal (un seul mot de passe partagé, pas de
comptes). Il répond au risque « accès libre à toutes les données » sur un
serveur. Un système de comptes/SSO académique pourra le remplacer plus tard.
"""

from __future__ import annotations
import hmac
import os

from flask import (request, session, redirect, url_for, render_template_string,
                   current_app)

# Chemins toujours accessibles sans authentification.
_CHEMINS_LIBRES = ("/login", "/static/", "/favicon.ico")


def mot_de_passe_configure() -> str | None:
    """Mot de passe attendu (depuis l'environnement), ou None si l'auth est
    désactivée."""
    mdp = os.environ.get("SEQ_MDP", "")
    return mdp if mdp else None


_PAGE_LOGIN = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>seqenseigne — connexion</title>
<style>
  body{font-family:system-ui,sans-serif;background:#f4f6f8;display:flex;
       min-height:100vh;align-items:center;justify-content:center;margin:0}
  form{background:#fff;padding:28px 32px;border-radius:10px;
       box-shadow:0 4px 20px rgba(0,0,0,.1);width:300px}
  h1{font-size:18px;margin:0 0 16px}
  label{display:block;font-size:13px;margin-bottom:6px}
  input[type=password]{width:100%;padding:8px;font-size:14px;
       border:1px solid #ccc;border-radius:6px;box-sizing:border-box}
  button{margin-top:14px;width:100%;padding:9px;font-size:14px;
       background:#2b6cb0;color:#fff;border:none;border-radius:6px;cursor:pointer}
  .err{color:#c33;font-size:12px;margin-top:8px;min-height:16px}
</style></head><body>
<form method="post" aria-label="Connexion">
  <h1>seqenseigne</h1>
  <label for="mdp">Mot de passe</label>
  <input type="password" id="mdp" name="mdp" autofocus
         aria-describedby="err-login">
  <button type="submit">Se connecter</button>
  <div class="err" id="err-login" role="status" aria-live="polite">{{ erreur }}</div>
</form></body></html>"""


def init_auth(app) -> None:
    """Branche l'authentification sur l'app si SEQ_MDP est défini. Sinon,
    ne fait rien (usage local sans authentification)."""
    mdp = mot_de_passe_configure()
    if not mdp:
        return  # authentification désactivée

    # Clé de session : depuis l'environnement si fournie, sinon dérivée du mdp
    # (suffisant pour un usage mono-utilisateur ; définir SEQ_SECRET pour une
    # clé stable dédiée).
    app.secret_key = os.environ.get("SEQ_SECRET") or ("seq-" + mdp)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        erreur = ""
        if request.method == "POST":
            saisi = request.form.get("mdp", "")
            attendu = mot_de_passe_configure() or ""
            # Comparaison à temps constant (évite l'attaque temporelle).
            if hmac.compare_digest(saisi, attendu):
                session["authentifie"] = True
                return redirect(url_for("index"))
            erreur = "Mot de passe incorrect."
        return render_template_string(_PAGE_LOGIN, erreur=erreur)

    @app.route("/logout")
    def logout():
        session.pop("authentifie", None)
        return redirect(url_for("login"))

    @app.before_request
    def _exiger_authentification():
        p = request.path
        if any(p == c or p.startswith(c) for c in _CHEMINS_LIBRES):
            return None
        if session.get("authentifie"):
            return None
        # Non authentifié : rediriger (pages) ou 401 (API).
        if p.startswith("/api/"):
            from flask import jsonify
            return jsonify({"error": "Authentification requise."}), 401
        return redirect(url_for("login"))
