/* ────────────────────────────────────────────────────────────────────────────
   atelier_atomique.js — SUPPRIMÉ en v0.14.4

   Ce fichier contenait la classe AtelierAtomique qui héritait
   d'AtelierEditeur et ajoutait la machinerie de rendu PDF :
     - basculerOnglet (surcharge pour brancher verifierCacheEtAfficher)
     - verifierCacheEtAfficher
     - _remettrePlaceholderRendu
     - compilerRendu (avec sauvegarde silencieuse en amont)
     - _afficherErreurCompilation
     - toggleTexBrut / _afficherTexBrut
     - scrollVersLigneTex
     - voirLatex

   Comme cette machinerie est désormais identique pour les 5 ateliers
   (Exercice, Notion, Méthode, Fiche, Carte) après le chantier
   d'unification v0.14.1 → v0.14.3, on l'a remontée dans AtelierEditeur
   en v0.14.4. Les 5 ateliers étendent maintenant directement AtelierEditeur.

   La balise <script> qui référençait ce fichier dans index.html a été
   retirée. Le fichier est conservé en stub vide ici pour écraser
   proprement la version précédente sur les installations existantes.

   Tu peux supprimer ce fichier manuellement après déploiement.
   ──────────────────────────────────────────────────────────────────────────── */
