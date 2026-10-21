# État d'avancement — RetainWall

## J0 — Mise en place : fait

- Dépôt Git, structure décrite dans CLAUDE.md, cahier des charges copié dans docs/specs.md.
- Backend FastAPI (`/api/sante`), pytest configuré, frontend React + Vite.
- Lancement : `lancer_backend.ps1` puis `lancer_frontend.ps1`, ouvrir http://localhost:5173.
- Tests : `lancer_tests.ps1`.

## J1 — Noyau 2D, une phase : fait (porte partiellement ouverte)

- `sout/sol` : couches et σ'v hydrostatique, Ka/Kp de Coulomb (Rankine si δ = 0),
  K0 de Jaky, cohésion par les états correspondants, kh de Schmitt, corrélation CPT
  paramétrable, surcharges (répartie, bande de Boussinesq, linéique de Flamant),
  branchement des tables de Kérisel-Absi (CSV à fournir).
- `sout/noyau` : poutre d'Euler-Bernoulli en éléments finis, ressorts élasto-plastiques
  avec mémoire, solveur de Newton semi-lisse avec recherche linéaire exacte sur
  l'énergie (convexe), détection de rupture.
- Tests (verts) : console analytique, Hetényi (poutre infinie sur Winkler, < 1 %),
  charge uniforme sur Winkler, équilibre global des forces et des moments, convergence
  du maillage, hauteur critique d'un écran autostable rigide face à l'équilibre limite
  rigide-plastique (écart < 2 %).
- **Porte non franchie** : comparaison au cas K-Réa/RIDO cas01, fichiers absents.
