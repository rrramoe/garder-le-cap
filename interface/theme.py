"""Identité visuelle du service : couleurs, tailles et feuille de style, en un seul endroit.

Une seule famille de caractères (Manrope), quatre tailles, un rayon, un bord. Un seul accent (un bleu franc),
réservé à l'action principale, aux états actifs et à la marque ; un violet discret en seconde voix ; une couleur
et une forme par verdict.
"""

from __future__ import annotations

# Une identité froide et nette. Les bleus, le violet et le vert d'eau sont ceux des feuilles de style publiques
# du site de HEC Montréal (www.hec.ca, relevées le 15 novembre 2026) ; les valeurs « dérivées » en sont des
# nuances plus sombres ou plus pâles, faites pour le texte et les fonds. Aucun logo, aucun nom repris.
BLANC = "#FFFFFF"
ENCRE = "#0F2742"         # dérivée : le bleu profond du texte et des surfaces sombres (bleu #1A61A9 assombri)
MARINE = ENCRE            # un seul élément de structure : le bandeau de simulation
GRIS = "#56657C"          # dérivée de l'ardoise #344054 du site : le texte secondaire, et seulement lui
BORD = "#D3DEE9"          # site : bleu-gris des bords (primary-300)
FILET = "#E4EBF3"         # dérivée : filets entre deux lignes
VOILE = "#F0F5FA"         # site : bleu très pâle des surfaces calmes (primary-200)
PISTE = "#E4EBF3"         # dérivée : piste des jauges
FOND = "#F9FCFF"          # site : le fond de page, un blanc froid (primary-100)
SURFACE = BLANC           # les cartes
ACCENT = "#1A61A9"        # site : le bleu franc (primary-500), pour l'action principale, l'actif et la marque
ACCENT_VIF = "#0069BF"    # site : le même bleu, au survol
BLEU_CLAIR = "#88B0D9"    # site : bleu clair des données (primary-400)
BLEU_PALE = "#E9F3FB"     # site : fond bleu pâle
VIOLET = "#7F56D9"        # site : le violet, seconde voix (repères, angle déterminant, lien entre les agents)
VIOLET_TEXTE = "#6941C6"  # dérivée : le violet assombri, pour un texte lisible sur fond pâle
VIOLET_PALE = "#F2EEFC"   # dérivée : fond violet pâle
POSITIF = "#00AD94"       # site : le vert d'eau (secondary-500), ce qui respecte la politique de placement
POSITIF_PALE = "#E8FBF8"  # site : fond vert d'eau pâle (secondary-100)
# Les couleurs de signal, celles que tout investisseur connaît : bon, prudence, arrêt. Accordées au système froid.
TENSION = "#E09600"       # site : l'ambre, ce qui dépasse une limite (prudence)
TENSION_PALE = "#FDF6D8"  # site : fond ambre pâle
ARRET = "#D12C4A"         # dérivée : un rouge net, un peu froid (cramoisi), ce qui touche une règle stricte
ARRET_PALE = "#FFEFF1"    # site : fond rose pâle
HAUSSE = "#00826F"        # dérivée : le vert d'eau assombri, pour un chiffre en hausse (contraste 4,8 sur blanc)
BAISSE = "#B4233D"        # dérivée : le cramoisi assombri, pour un chiffre en baisse (contraste 6,6 sur blanc)
HAUSSE_SUR_SOMBRE = "#5FE0CB"   # les mêmes, éclaircies pour le panneau sombre
BAISSE_SUR_SOMBRE = "#FF9FB0"

# Un verdict ne se lit jamais par la couleur seule : son mot est écrit à l'encre (contraste de plus de 10 sur
# son fond pâle), sa forme change (un point plein, un anneau, un carré) et sa place reste la même.
# Le violet reste la seconde voix de la marque (angle déterminant, liens, agents) : jamais un statut.
COULEURS_VERDICT = {"compatible": POSITIF, "en_tension": TENSION, "incompatible": ARRET}
FONDS_VERDICT = {"compatible": POSITIF_PALE, "en_tension": TENSION_PALE, "incompatible": ARRET_PALE}
FORMES_VERDICT = {"compatible": "point", "en_tension": "anneau", "incompatible": "carre"}
COULEURS_CLASSES = {"actions": ENCRE, "revenu_fixe": ACCENT, "liquidites": BLEU_CLAIR, "alternatifs": BORD}
COULEUR_AUTRE = PISTE

# La lueur : ce que le service ajoute au courtage se reconnaît à un contour vivant, une lumière lente qui en
# fait le tour, du bleu d'accent vers le violet, et à un halo doux. Une seule recette, réglée ici.
LUEUR_A = ACCENT          # la lumière part du bleu d'accent
LUEUR_B = VIOLET          # et va vers le violet
LUEUR_VITESSE = "8s"      # au repos : un passage de lumière (le dernier quart du temps), puis le repos
LUEUR_VIVE = "2.2s"       # pendant qu'une analyse tourne, ou au survol : un passage, en continu
LUEUR_FORCE = "0.20"      # l'opacité du halo, au repos
LUEUR_FORTE = "0.38"      # et pendant qu'une analyse tourne

POLICE = "Manrope"

CSS = f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap');

:root {{
  --encre: {ENCRE}; --gris: {GRIS}; --bord: {BORD}; --fond: {FOND}; --surface: {SURFACE};
  --voile: {VOILE}; --accent: {ACCENT}; --filet: {FILET}; --piste: {PISTE}; --marine: {MARINE};
  --violet: {VIOLET_TEXTE}; --ombre: 15, 39, 66;
  --t1: 13px; --t2: 15px; --t3: 18px; --t4: 26px;
  --t5: 36px;  /* la phrase d'ouverture de l'introduction, et elle seule */
  --rayon: 12px;
}}

/* ---------- base ---------- */
html, body, .stApp, .stApp * {{ font-family: '{POLICE}', -apple-system, 'Segoe UI', sans-serif; }}
.stApp span[data-testid="stIconMaterial"], .stApp [class*="material-symbols"] {{
  font-family: 'Material Symbols Rounded' !important; }}
.stApp {{ background: radial-gradient(1000px 380px at 92% -140px, rgba(127,86,217,0.08), transparent 70%),
          radial-gradient(900px 340px at 6% -160px, rgba(26,97,169,0.07), transparent 70%), var(--fond); }}
header[data-testid="stHeader"], div[data-testid="stToolbar"], div[data-testid="stDecoration"] {{ display: none; }}
section[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"] {{ display: none; }}
.stMainBlockContainer {{ max-width: 1168px; padding: 0 24px 72px 24px; }}
:where(.stApp) p, :where(.stApp) li, :where(.stApp) label {{ font-size: var(--t2); }}
:where(.stApp) p {{ line-height: 1.55; }}
div[data-testid="stElementContainer"]:has(style) {{ display: none; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {{ color: var(--encre); letter-spacing: -0.01em; padding: 0; }}
div[data-testid="stCaptionContainer"] p, .stApp small {{ font-size: var(--t1); color: var(--gris); }}

.stApp div[data-testid="stMarkdownContainer"] {{ margin-bottom: 0; }}
.stApp div[data-testid="stMarkdownContainer"] > p:last-child {{ margin-bottom: 0; }}
.stApp div[data-testid="stMarkdownContainer"] ul {{ margin: 0 0 4px 0; padding-left: 20px; }}
.stApp div[data-testid="stMarkdownContainer"] li {{ margin: 0 0 3px 0; padding: 0; }}

/* ---------- en-tête : bandeau de simulation et barre ---------- */
.st-key-entete {{ position: sticky; top: 0; z-index: 990; gap: 0; background: var(--surface);
  box-shadow: 0 0 0 100vmax var(--surface), 0 1px 0 100vmax var(--bord);
  clip-path: inset(0 -100vmax -1px -100vmax); margin-bottom: 20px; }}
.stApp .glc-bandeau {{ background: var(--marine); color: #FFFFFF; font-size: var(--t1); letter-spacing: 0.01em;
  padding: 6px 0; box-shadow: 0 0 0 100vmax var(--marine); clip-path: inset(0 -100vmax); }}
.stApp .glc-bandeau b {{ color: #fff; font-weight: 600; }}
.st-key-barre {{ padding: 10px 0; }}
.stApp .glc-marque {{ display: flex; align-items: center; gap: 10px; color: var(--encre); white-space: nowrap; }}
.stApp .glc-marque .nom {{ font-size: var(--t3); font-weight: 700; letter-spacing: -0.02em; }}
.stApp .glc-marque .sous {{ font-size: var(--t1); color: var(--gris); border-left: 1px solid var(--bord);
  padding-left: 10px; margin-left: 2px; }}

/* navigation : un groupe de boutons radio rendu comme des pastilles */
.st-key-page {{ margin: 0 auto; }}
.st-key-page div[role="radiogroup"] {{ gap: 4px; background: var(--voile); border-radius: 999px; padding: 4px;
  width: fit-content; margin: 0 auto; flex-wrap: nowrap; }}
.st-key-page label[data-testid="stRadioOption"] {{ margin: 0; padding: 6px 16px; border-radius: 999px; cursor: pointer;
  transition: background .15s ease; }}
.st-key-page label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) {{ display: none; }}
.st-key-page label[data-testid="stRadioOption"] p {{ font-size: var(--t2); font-weight: 600; color: var(--gris);
  white-space: nowrap; }}
.st-key-page label[data-testid="stRadioOption"]:hover p {{ color: var(--encre); }}
.st-key-page label[data-testid="stRadioOption"][data-selected="true"] {{ background: var(--surface);
  box-shadow: 0 1px 2px rgba(var(--ombre), 0.12); }}
.st-key-page label[data-testid="stRadioOption"][data-selected="true"] p {{ color: var(--encre); }}

/* compte */
div[class*="st-key-compte"] {{ align-items: flex-end; }}
div[class*="st-key-compte"] div[data-testid="stPopover"] {{ width: auto; margin-left: auto; }}
div[class*="st-key-compte"] div[data-testid="stPopover"] > div > button {{ border-radius: 999px; padding: 4px 14px 4px 10px;
  min-height: 38px; border: 1px solid var(--bord); background: var(--surface); }}
div[class*="st-key-compte"] div[data-testid="stPopover"] > div > button p {{ font-weight: 600; font-size: var(--t2); }}

/* le menu du compte : une liste de clients, le client choisi sur fond gris chaud */
div[data-testid="stPopoverBody"] {{ border-radius: var(--rayon); border: 1px solid var(--bord); padding: 14px;
  box-shadow: 0 8px 24px rgba(var(--ombre), 0.10); min-width: 300px; }}
div[data-testid="stPopoverBody"] div[role="radiogroup"] {{ gap: 2px; width: 100%; }}
div[data-testid="stPopoverBody"] div[role="radiogroup"] > div {{ width: 100%; }}
div[data-testid="stPopoverBody"] label[data-testid="stRadioOption"] {{ width: 100%; padding: 8px 10px;
  border-radius: 8px; cursor: pointer; margin: 0; }}
div[data-testid="stPopoverBody"] label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) {{
  display: none; }}
div[data-testid="stPopoverBody"] label[data-testid="stRadioOption"]:hover,
div[data-testid="stPopoverBody"] label[data-testid="stRadioOption"][data-selected="true"] {{ background: var(--voile); }}
div[data-testid="stPopoverBody"] label[data-testid="stRadioOption"] p {{ font-size: var(--t1); color: var(--gris); }}
div[data-testid="stPopoverBody"] label[data-testid="stRadioOption"] p strong {{ font-size: var(--t2);
  color: var(--encre); font-weight: 600; }}
div[data-testid="stPopoverBody"] label[data-testid="stWidgetLabel"] p {{ font-size: var(--t1); font-weight: 600;
  color: var(--gris); }}

/* ---------- titres de page ---------- */
.stApp .glc-titre {{ margin: 6px 0 2px 0; }}
.stApp .glc-titre h1 {{ font-size: var(--t4); font-weight: 700; margin: 0; line-height: 1.25; }}
.stApp .glc-titre p {{ color: var(--gris); margin: 2px 0 0 0; font-size: var(--t2); }}
.stApp .glc-h2 {{ font-size: var(--t3); font-weight: 700; color: var(--encre); margin: 0 0 2px 0; letter-spacing: -0.01em; }}
.stApp .glc-sur {{ font-size: var(--t1); color: var(--gris); margin: 0; }}
.stApp .glc-etiquette {{ font-size: var(--t1); font-weight: 600; color: var(--gris); margin: 0 0 4px 0; }}

/* ---------- cartes ---------- */
div[class*="st-key-carte"] {{ background: var(--surface); border: 1px solid var(--bord); border-radius: var(--rayon);
  padding: 22px 24px; }}
.stApp .glc-carte {{ background: var(--surface); border: 1px solid var(--bord); border-radius: var(--rayon);
  padding: 22px 24px; }}
.stApp .glc-chiffre {{ font-size: var(--t4); font-weight: 700; color: var(--encre); letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums; line-height: 1.2; }}
.stApp .glc-faits {{ display: flex; gap: 28px; flex-wrap: wrap; margin-top: 14px; }}
.stApp .glc-faits div span {{ display: block; font-size: var(--t1); color: var(--gris); }}
.stApp .glc-faits div b {{ font-size: var(--t2); font-weight: 600; color: var(--encre); font-variant-numeric: tabular-nums; }}

/* ---------- introduction et choix du compte ---------- */
div[class*="st-key-introduction"] {{ max-width: 1168px; margin: 4px auto 0 auto; gap: 8px; }}
.stApp .glc-pas-intro {{ display: flex; align-items: center; gap: 6px; }}
.stApp .glc-pas-intro span {{ font-size: var(--t1); font-weight: 600; color: var(--gris); margin-right: 8px;
  font-variant-numeric: tabular-nums; }}
.stApp .glc-pas-intro i {{ width: 22px; height: 4px; border-radius: 4px; background: var(--piste); }}
.stApp .glc-pas-intro i.ici {{ background: var(--encre); }}
.stApp .glc-intro {{ height: 318px; display: flex; flex-direction: column; justify-content: flex-end; }}
.stApp .glc-intro h1 {{ font-size: var(--t5); font-weight: 700; line-height: 1.16; margin: 0 0 12px 0;
  letter-spacing: -0.03em; color: var(--encre); }}
.stApp .glc-intro h1 span.avant, .stApp .glc-intro h1 span.apres {{ display: block; }}
.stApp .glc-intro h1 [data-testid="stHeaderActionElements"] {{ display: none; }}
.stApp .glc-intro h1 span.avant {{ color: var(--gris); }}
.stApp .glc-intro p {{ font-size: var(--t3); line-height: 1.5; color: var(--encre); margin: 0 0 8px 0; }}
.stApp .glc-intro p.fort {{ font-weight: 700; }}
.stApp .glc-intro p.note {{ font-size: var(--t1); color: var(--gris); margin: 6px 0 0 0; padding-left: 12px;
  border-left: 2px solid var(--bord); }}
.stApp .glc-vue {{ background: var(--voile); border-radius: 20px; padding: 28px;
  height: clamp(420px, calc(100vh - 230px), 660px); overflow: hidden;
  display: flex; flex-direction: column; justify-content: center; position: relative; }}
.stApp .glc-vue.film {{ padding: 14px; }}
.stApp .glc-vue svg.film {{ width: 100%; height: 100%; display: block; overflow: visible; }}
.stApp .glc-vue svg.film text {{ font-family: inherit; }}
.stApp .glc-vue > .glc-carte, .stApp .glc-vue > .glc-paire > div {{ box-shadow: 0 10px 30px rgba(var(--ombre), 0.07); }}
.stApp .glc-vue .glc-angles {{ grid-template-columns: repeat(5, 1fr); gap: 2px; }}
.stApp .glc-vue .glc-angle {{ padding: 8px 0; }}
.stApp .glc-vue .glc-angle svg {{ width: 62px; height: 62px; }}
.stApp .glc-vue .glc-angle .tag {{ white-space: normal; line-height: 1.25; }}
.stApp .glc-vue .glc-carte {{ padding: 20px 20px; }}
.stApp .glc-vue svg.ecart {{ width: 100%; height: auto; }}
.stApp .glc-vue svg.ecart text {{ font-family: inherit; font-size: 13px; fill: var(--gris); }}
.stApp .glc-vue svg.ecart text.fort {{ fill: var(--encre); font-weight: 600; }}
.stApp .glc-paire {{ display: grid; grid-template-columns: 1fr 22px 1fr; gap: 8px; align-items: center; }}
.stApp .glc-paire > div {{ background: var(--surface); border: 1px solid var(--bord); border-radius: var(--rayon);
  padding: 18px 18px 8px 18px; }}
.stApp .glc-paire > svg {{ justify-self: center; }}
.stApp .glc-paire .tete {{ font-size: var(--t1); font-weight: 600; color: var(--gris); margin: 0 0 8px 0; }}
.stApp .glc-paire dl {{ margin: 0; }}
.stApp .glc-paire dt {{ font-size: var(--t1); color: var(--gris); }}
.stApp .glc-paire dd {{ margin: 0 0 12px 0; font-size: var(--t2); font-weight: 600; color: var(--encre);
  line-height: 1.35; }}
.stApp .glc-issue {{ display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; padding: 12px 0;
  border-bottom: 1px solid var(--filet); align-items: center; }}
.stApp .glc-issue:last-child {{ border-bottom: 0; padding-bottom: 0; }}
.stApp .glc-issue:first-child {{ padding-top: 0; }}
.stApp .glc-issue .qui {{ font-size: var(--t1); color: var(--gris); grid-column: 1 / -1; }}
.stApp .glc-issue .ou {{ font-size: var(--t2); font-weight: 600; color: var(--encre); }}
.stApp .glc-resume p {{ margin: 0; font-size: var(--t2); }}
.stApp .glc-resume .ligne {{ border-top: 1px solid var(--filet); padding: 10px 0 0 0; margin-top: 10px; }}
.stApp .glc-resume .ligne span {{ display: block; font-size: var(--t1); color: var(--gris); }}
.stApp .glc-resume .ligne {{ display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }}
.stApp .glc-resume .piste {{ display: flex; justify-content: space-between; align-items: center; gap: 10px;
  padding: 5px 0 0 0; font-weight: 600; }}
.stApp .glc-billet .champ {{ padding: 10px 0; border-bottom: 1px solid var(--filet); }}
.stApp .glc-billet .champ span {{ display: block; font-size: var(--t1); color: var(--gris); }}
.stApp .glc-billet .champ b {{ font-size: var(--t2); font-weight: 600; color: var(--encre); }}
.stApp .glc-billet .bouton {{ margin-top: 16px; background: var(--accent); color: #fff; border-radius: 999px;
  text-align: center; font-size: var(--t2); font-weight: 600; padding: 10px 0; opacity: .55; }}
.stApp .glc-vue:has(.glc-billet) {{ padding: 28px 84px; }}
div[class*="st-key-introduction"] .stButton > button[kind="tertiary"] {{ float: right; }}
div[class*="st-key-carte_compte"] .glc-faits {{ margin: 10px 0 4px 0; }}
div[class*="st-key-carte_compte"] .allure {{ margin: 10px 0 0 0; }}
div[class*="st-key-carte_compte"] .allure svg {{ width: 100%; height: 54px; display: block; }}
div[class*="st-key-carte_compte"] .allure p {{ margin: 2px 0 0 0; font-size: var(--t1); }}
.stApp .glc-chemin {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 4px; }}
.stApp .glc-chemin > div {{ display: flex; gap: 12px; align-items: flex-start; background: var(--voile);
  border-radius: var(--rayon); padding: 14px 16px; }}
.stApp .glc-chemin b {{ flex: none; display: inline-flex; align-items: center; justify-content: center; width: 24px;
  height: 24px; border-radius: 50%; background: {LUEUR_B}; color: {BLANC}; font-size: var(--t1); }}
.stApp .glc-chemin p {{ margin: 0; font-size: var(--t1); color: var(--gris); line-height: 1.45; }}
.stApp .glc-chemin strong {{ display: block; font-size: var(--t2); color: var(--encre); }}
@media (max-width: 640px) {{ .stApp .glc-chemin {{ grid-template-columns: 1fr; }} }}

/* ---------- étapes numérotées ---------- */
.stApp .glc-pas {{ display: grid; grid-template-columns: 28px 1fr; gap: 4px 12px; padding: 10px 0;
  border-bottom: 1px solid var(--filet); }}
.stApp .glc-pas:last-child {{ border-bottom: 0; }}
.stApp .glc-pas .no {{ font-size: var(--t1); font-weight: 600; color: var(--gris); padding-top: 2px; }}
.stApp .glc-pas b {{ font-weight: 700; }}
.stApp .glc-pas p {{ margin: 0; font-size: var(--t2); }}

/* ---------- données vivantes : courbes, variations, panneau sombre ---------- */
.stApp .glc-var {{ font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.stApp .glc-var.hausse {{ color: {HAUSSE}; }}
.stApp .glc-var.baisse {{ color: {BAISSE}; }}
.stApp .glc-var small {{ font-weight: 400; color: var(--gris); font-size: var(--t1); margin-left: 4px; }}
.stApp svg.glc-courbe {{ display: inline-block; vertical-align: middle; overflow: visible; }}
.stApp .glc-sombre {{ background: var(--marine); color: {BLANC}; border-radius: var(--rayon); padding: 22px 24px 0 24px;
  overflow: hidden; position: relative; height: 100%; }}
.stApp .glc-sombre .glc-etiquette {{ color: {BLEU_CLAIR}; }}
.stApp .glc-sombre .glc-chiffre {{ color: {BLANC}; font-size: var(--t5); }}
.stApp .glc-sombre .glc-var.hausse {{ color: {HAUSSE_SUR_SOMBRE}; }}
.stApp .glc-sombre .glc-var.baisse {{ color: {BAISSE_SUR_SOMBRE}; }}
.stApp .glc-sombre .glc-var small {{ color: {BLEU_CLAIR}; }}
.stApp .glc-sombre .glc-faits div span {{ color: {BLEU_CLAIR}; }}
.stApp .glc-sombre .glc-faits div b {{ color: {BLANC}; }}
.stApp .glc-sombre svg.glc-courbe {{ display: block; width: calc(100% + 48px); margin: 14px -24px 0 -24px; }}
.stApp .glc-sombre .note {{ position: absolute; right: 24px; top: 24px; font-size: var(--t1); color: {BLEU_CLAIR}; }}
.stApp .glc-cours {{ display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 2px 2px 0 2px; }}
.stApp .glc-cours b {{ font-size: var(--t3); font-weight: 700; font-variant-numeric: tabular-nums; }}
.stApp .glc-duo {{ display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 16px; }}
@media (max-width: 900px) {{ .stApp .glc-duo {{ grid-template-columns: minmax(0, 1fr); }} }}
.stApp .glc-duo > * {{ min-width: 0; }}
.stApp .glc-duo > .glc-carte {{ display: flex; flex-direction: column; justify-content: center; }}

/* ---------- un seul rythme : le même écart entre les cartes partout, un plus petit dedans ---------- */
.stMainBlockContainer {{ padding-bottom: 40px; }}
.stMainBlockContainer > div[data-testid="stVerticalBlock"] {{ gap: 14px; }}
.stMainBlockContainer div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {{ gap: 14px; }}
div[class*="st-key-carte"] {{ gap: 10px; padding: 18px 20px; }}
.st-key-entete {{ margin-bottom: 10px; }}
.stApp .glc-titre {{ margin: 2px 0 0 0; }}
.stApp .glc-carte, .stApp .glc-verdict {{ padding: 18px 20px; }}
.stApp .glc-liste-def div {{ padding: 7px 0; }}
.stApp .glc-pas {{ padding: 8px 0; }}
div[class*="st-key-zone_sigma"] > div[data-testid="stVerticalBlock"], div[class*="st-key-zone_sigma"] {{ gap: 12px; }}

/* ---------- la lueur : le contour vivant de ce que le service ajoute ----------
   Bon marché pour le navigateur : le contour et le halo sont fixes (un dégradé, une ombre) ; seule une
   petite lumière bouge, par translation, sur sa propre couche : aucun fond, aucune ombre n'est repeint. */
/* Au repos, la lumière passe puis se repose : le navigateur ne dessine aucune image pendant le repos. */
@keyframes glc-file {{ 0%, 76% {{ transform: translateX(-180px); }} 100% {{ transform: translateX(100%); }} }}
@keyframes glc-file-retour {{ 0%, 76% {{ transform: translateX(100%); }} 100% {{ transform: translateX(-180px); }} }}
@keyframes glc-file-vive {{ from {{ transform: translateX(-180px); }} to {{ transform: translateX(100%); }} }}
@keyframes glc-file-retour-vive {{ from {{ transform: translateX(100%); }} to {{ transform: translateX(-180px); }} }}
@keyframes glc-reflet {{ 0%, 76% {{ transform: translateX(-130%); }} 100% {{ transform: translateX(130%); }} }}
@keyframes glc-reflet-vif {{ from {{ transform: translateX(-130%); }} to {{ transform: translateX(130%); }} }}
@keyframes glc-coule {{ 0%, 76% {{ transform: translateY(-16px); opacity: 0; }} 80% {{ opacity: 1; }}
  96% {{ opacity: 1; }} 100% {{ transform: translateY(var(--course, 64px)); opacity: 0; }} }}
@keyframes glc-pouls-doc {{ 0% {{ opacity: .9; }} 100% {{ opacity: 0; }} }}
.stApp .glc-lueur, div[class*="st-key-zone_sigma"], .stApp .glc-doc {{ position: relative; overflow: hidden;
  border: 1.5px solid transparent !important; --glc-fond: var(--surface);
  background: linear-gradient(var(--glc-fond), var(--glc-fond)) padding-box,
              linear-gradient(120deg, {LUEUR_A}, {BORD} 30%, {BORD} 70%, {LUEUR_B}) border-box;
  box-shadow: 0 14px 44px -18px rgba(26, 97, 169, {LUEUR_FORCE}), 0 0 26px -6px rgba(127, 86, 217, {LUEUR_FORCE}); }}
.stApp .glc-lueur::before, div[class*="st-key-zone_sigma"]::before, .stApp .glc-doc::before,
.stApp .glc-lueur::after, div[class*="st-key-zone_sigma"]::after, .stApp .glc-doc::after {{ content: "";
  position: absolute; left: 0; right: 0; height: 2px; pointer-events: none; will-change: transform;
  background: linear-gradient(90deg, transparent, {LUEUR_A} 35%, {LUEUR_B} 65%, transparent) no-repeat;
  background-size: 180px 100%; }}
.stApp .glc-lueur::before, div[class*="st-key-zone_sigma"]::before, .stApp .glc-doc::before {{ top: 0;
  animation: glc-file {LUEUR_VITESSE} linear infinite; }}
.stApp .glc-lueur::after, div[class*="st-key-zone_sigma"]::after, .stApp .glc-doc::after {{ bottom: 0;
  animation: glc-file-retour {LUEUR_VITESSE} linear infinite; }}
div[class*="st-key-zone_sigma"] {{ --glc-fond: {BLEU_PALE}; border-radius: 18px; padding: 16px 16px 18px 16px; }}
/* pendant qu'une analyse tourne : la lumière passe plus vite, le halo se renforce (une ombre fixe, posée une fois) */
div[class*="st-key-zone_sigma"]:has(.glc-direct)::before, div[class*="st-key-zone_sigma"]:hover::before {{
  animation: glc-file-vive {LUEUR_VIVE} linear infinite; }}
div[class*="st-key-zone_sigma"]:has(.glc-direct)::after, div[class*="st-key-zone_sigma"]:hover::after {{
  animation: glc-file-retour-vive {LUEUR_VIVE} linear infinite; }}
div[class*="st-key-zone_sigma"]:has(.glc-direct)::before, div[class*="st-key-zone_sigma"]:has(.glc-direct)::after {{
  height: 3px; }}
div[class*="st-key-zone_sigma"]:has(.glc-direct) {{
  box-shadow: 0 14px 48px -14px rgba(26, 97, 169, {LUEUR_FORTE}), 0 0 34px -4px rgba(127, 86, 217, {LUEUR_FORTE}); }}
.stApp .glc-sigma {{ display: flex; align-items: center; gap: 8px; margin: 0 0 2px 2px; font-size: var(--t1);
  font-weight: 700; color: var(--encre); letter-spacing: .01em; }}
.stApp .glc-sigma span {{ font-weight: 500; color: var(--gris); }}
/* le bouton de l'analyse : un reflet le traverse de temps en temps ; il passe en continu au survol */
.st-key-inspecter button[kind="primary"] {{ position: relative; overflow: hidden; border-color: transparent;
  background: linear-gradient(105deg, {LUEUR_A} 55%, {LUEUR_B} 140%);
  box-shadow: 0 8px 22px -6px rgba(26, 97, 169, .45), 0 0 18px -4px rgba(127, 86, 217, .35); }}
.st-key-inspecter button[kind="primary"]::after {{ content: ""; position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(105deg, transparent 35%, rgba(255, 255, 255, .38) 50%, transparent 65%);
  will-change: transform; animation: glc-reflet {LUEUR_VITESSE} ease-in-out infinite; }}
.st-key-inspecter button[kind="primary"]:hover::after {{ animation: glc-reflet-vif 1.6s ease-in-out infinite; }}
.st-key-inspecter button[kind="primary"]:hover {{ border-color: transparent; }}
/* le chemin du profil : la fiche, le passage où la lumière court, la politique de placement */
@keyframes glc-court {{ 0%, 76% {{ transform: translateX(-26px); opacity: 0; }} 80% {{ opacity: 1; }} 96% {{ opacity: 1; }}
  100% {{ transform: translateX(var(--course, 64px)); opacity: 0; }} }}
@keyframes glc-eclair {{ 0% {{ opacity: 1; transform: scaleY(3.2); }} 100% {{ opacity: 1; transform: none; }} }}
.stApp .glc-etape {{ display: flex; align-items: center; gap: 8px; margin: 0 0 6px 0; font-size: var(--t1);
  font-weight: 700; color: var(--violet); letter-spacing: .01em; }}
.stApp .glc-etape b {{ display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px;
  border-radius: 50%; background: {LUEUR_B}; color: {BLANC}; font-size: var(--t1); font-weight: 700; }}
.stApp .glc-passage {{ display: flex; flex-direction: column; justify-content: space-around; height: 520px;
  position: sticky; top: 130px; margin: 60px -14px 0 -14px; }}
.stApp .glc-passage .fil {{ position: relative; display: block; height: 2px; border-radius: 2px; overflow: hidden;
  background: linear-gradient(90deg, {BORD}, {LUEUR_A} 60%, {LUEUR_B}); }}
.stApp .glc-passage .fil i {{ position: absolute; top: 0; left: 0; width: 26px; height: 2px; border-radius: 2px;
  background: linear-gradient(90deg, transparent, {BLANC}, {LUEUR_B}); --course: 96px;
  will-change: transform; animation: glc-court {LUEUR_VITESSE} linear infinite; }}
div[class*="st-key-passage_"] .glc-passage .fil {{ animation: glc-eclair .9s ease-out 1; }}
div[class*="st-key-passage_"] .glc-lien {{ display: none; }}
@media (max-width: 640px) {{
  .stApp .glc-passage {{ display: none; }}
  div[class*="st-key-passage_"] .glc-lien {{ display: flex; }}
}}
/* la fiche et la politique, serrées pour tenir côte à côte */
div[class*="st-key-carte_fiche"] {{ padding: 18px 20px; gap: 0.35rem; }}
div[class*="st-key-carte_fiche"] .glc-rubrique {{ margin: 6px 0 0 0; font-size: var(--t1); }}
div[class*="st-key-carte_fiche"] .glc-rubrique span {{ display: inline; margin-left: 8px; }}
div[class*="st-key-carte_fiche"] .stSelectbox div[role="group"] {{ min-height: 38px; }}
div[class*="st-key-carte_fiche"] .stSelectbox button:not([aria-label="Open"]) {{ display: none; }}
div[class*="st-key-carte_fiche"] div[class*="_theme_"] div[data-testid="stRadio"] {{ grid-template-columns: minmax(0, 1fr) auto;
  padding: 2px 0; gap: 8px; }}
div[class*="st-key-carte_fiche"] div[class*="_theme_"] label[data-testid="stWidgetLabel"] p {{ font-size: var(--t1); }}
div[class*="st-key-carte_fiche"] div[class*="_theme_"] label[data-testid="stRadioOption"] {{ padding: 3px 7px; }}
div[class*="st-key-carte_fiche"] div[class*="_theme_"] label[data-testid="stRadioOption"] p {{ font-size: 12px; }}
div[class*="st-key-politique_"] .glc-doc {{ padding: 18px 22px 10px 22px; }}
div[class*="st-key-politique_"] .glc-doc .tete {{ padding-bottom: 10px; }}
div[class*="st-key-politique_"] .glc-doc .tete h2 {{ font-size: var(--t3); }}
div[class*="st-key-politique_"] .glc-doc .tete p {{ font-size: var(--t1); }}
div[class*="st-key-politique_"] .glc-article {{ grid-template-columns: 22px 132px minmax(0, 1fr); gap: 2px 10px; padding: 7px 0; }}
div[class*="st-key-politique_"] .glc-article .nom {{ font-size: var(--t1); }}
div[class*="st-key-politique_"] .glc-article .corps p, div[class*="st-key-politique_"] .glc-article .corps li {{
  font-size: var(--t1); line-height: 1.45; margin-bottom: 1px; }}
div[class*="st-key-politique_"] .glc-article .source {{ margin: 2px 0 0 0; }}
div[class*="st-key-politique_"] .glc-rubrique-doc {{ padding: 10px 0 4px 0; }}
div[class*="st-key-politique_"] .glc-article table.glc-table td {{ padding: 3px 10px 3px 0; font-size: var(--t1); }}
div[class*="st-key-carte_fiche"] .glc-rubrique {{ text-transform: uppercase; letter-spacing: .06em; font-size: 12px;
  color: var(--encre); }}
div[class*="st-key-carte_fiche"] .glc-rubrique span {{ display: none; }}
div[class*="st-key-carte_fiche"] div[class*="_theme_"] label[data-testid="stRadioOption"] {{ padding: 2px 6px; }}
div[class*="st-key-politique_"] .glc-article:has(table) {{ grid-template-columns: 22px minmax(0, 1fr); }}
div[class*="st-key-politique_"] .glc-article:has(table) .corps {{ grid-column: 2; }}
div[class*="st-key-politique_"] .glc-article table.glc-table {{ max-width: none; }}
.stApp .glc-doc .tete p.glc-etape {{ color: var(--violet); font-size: var(--t1); margin: 0 0 6px 0; }}
div[class*="st-key-politique_"] .glc-article .source {{ font-size: 12px; }}
/* le lien vertical, quand les deux cartes s'empilent : un canal où la lumière descend, sans fin */
.stApp .glc-lien {{ display: flex; flex-direction: column; align-items: center; gap: 6px; margin: -6px 0 -6px 0; }}
.stApp .glc-lien .canal {{ position: relative; width: 3px; height: 64px; border-radius: 3px; overflow: hidden;
  background: linear-gradient({BORD}, {LUEUR_A}); }}
.stApp .glc-lien .canal i {{ position: absolute; left: 0; top: 0; width: 3px; height: 16px; border-radius: 3px;
  background: linear-gradient(transparent, {BLANC}, {LUEUR_B}); will-change: transform;
  animation: glc-coule {LUEUR_VITESSE} linear infinite; }}
.stApp .glc-lien .canal i:nth-child(2) {{ animation-delay: .12s; }}
.stApp .glc-lien .canal i:nth-child(3) {{ animation-delay: .24s; }}
.stApp .glc-lien .mot {{ font-size: var(--t1); font-weight: 600; color: var(--violet); background: {VIOLET_PALE};
  border-radius: 999px; padding: 2px 12px; }}
div[class*="st-key-politique_"] {{ position: relative; }}
div[class*="st-key-politique_"]::after {{ content: ""; position: absolute; inset: -6px; border-radius: 18px;
  pointer-events: none; opacity: 0; will-change: opacity;
  background: radial-gradient(closest-side, rgba(127, 86, 217, .0) 70%, rgba(127, 86, 217, .30));
  animation: glc-pouls-doc .9s ease-out 1; }}
div[class*="st-key-politique_"] .glc-doc {{ animation: glc-arrive .22s ease-out both; }}
.stApp .glc-vue svg.film .carte {{ filter: drop-shadow(0 8px 18px rgba(var(--ombre), .10)); }}

/* ---------- mouvement, avec retenue ---------- */
@keyframes glc-arrive {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes glc-arc {{ from {{ stroke-dasharray: 0.1 999; }} }}
@keyframes glc-trace {{ from {{ stroke-dashoffset: var(--long, 600); }} to {{ stroke-dashoffset: 0; }} }}
.stApp .glc-verdict, .stApp .glc-carte, .stApp .glc-sombre, .stApp .glc-vue > *,
.stApp .glc-etapes li {{ animation: glc-arrive .22s ease-out both; }}
.stApp .glc-angle circle.arc {{ animation: glc-arc .7s cubic-bezier(.2, .7, .2, 1) both; }}
.stApp svg.ecart path.trait {{ stroke-dasharray: var(--long, 240); animation: glc-trace .8s ease-out both; }}
.stApp svg.ecart path.trait.tard {{ animation-delay: .7s; }}

.stApp table.glc-table tbody tr {{ transition: background .15s ease; }}
.stApp table.glc-table tbody tr:hover {{ background: var(--voile); }}
.stApp .stButton > button {{ transition: background .15s ease, border-color .15s ease, box-shadow .2s ease,
  transform .15s ease; }}
.stApp .stButton > button[kind="primary"] {{ box-shadow: 0 6px 16px rgba(26, 97, 169, .28); }}
.stApp .stButton > button[kind="primary"]:hover {{ box-shadow: 0 8px 22px rgba(26, 97, 169, .36);
  transform: translateY(-1px); }}
div[class*="st-key-carte"] {{ transition: border-color .2s ease, box-shadow .2s ease; }}
div[class*="st-key-carte_compte"]:hover {{ border-color: var(--accent); box-shadow: 0 8px 24px rgba(var(--ombre), .08); }}
@media (prefers-reduced-motion: reduce) {{
  .stApp *, .stApp *::before, .stApp *::after {{ animation: none !important; transition: none !important; }}
}}

/* ---------- pastilles ---------- */
.stApp .glc-pastille {{ display: inline-flex; align-items: center; gap: 6px; font-size: var(--t1); font-weight: 600;
  padding: 3px 10px; border-radius: 999px; white-space: nowrap; }}
.stApp .glc-pastille i {{ width: 8px; height: 8px; border-radius: 50%; background: currentColor; display: inline-block;
  box-sizing: border-box; flex: none; }}
.stApp i.anneau {{ background: transparent !important; border: 2.5px solid var(--teinte-forme, currentColor); }}
.stApp i.carre {{ border-radius: 2px !important; }}
.stApp .glc-marqueur {{ display: inline-block; font-size: var(--t1); font-weight: 600; color: var(--gris);
  border: 1px solid var(--bord); border-radius: 999px; padding: 0 7px; line-height: 1.5; vertical-align: 1px;
  margin-left: 6px; white-space: nowrap; }}

div[class*="st-key-deja_faite"] {{ margin-bottom: -8px; }}
div[class*="st-key-deja_faite"] .stButton {{ display: flex; justify-content: flex-end; }}

/* ---------- verdict ---------- */
.stApp .glc-verdict {{ border-radius: var(--rayon); border: 1px solid var(--bord); background: var(--surface);
  padding: 22px 24px; position: relative; overflow: hidden; }}
.stApp .glc-verdict::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: var(--teinte); }}
.stApp .glc-verdict .ordre {{ font-size: var(--t1); color: var(--gris); margin: 0 0 6px 0; }}
.stApp .glc-verdict .mot {{ font-size: var(--t4); font-weight: 700; color: var(--encre); letter-spacing: -0.02em;
  line-height: 1.2; margin: 0; }}
.stApp .glc-verdict .mot .pt {{ display: inline-block; width: 12px; height: 12px; border-radius: 50%;
  margin-right: 10px; vertical-align: 2px; }}
.stApp .glc-verdict .raison {{ font-size: var(--t2); color: var(--encre); margin: 8px 0 0 0; max-width: 62ch; }}
.stApp .glc-verdict .suite {{ font-size: var(--t1); color: var(--gris); margin: 8px 0 0 0; max-width: 70ch; }}

/* ---------- angles (cadrans) ---------- */
.stApp .glc-angles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(108px, 1fr)); gap: 4px; }}
.stApp .glc-angle {{ text-align: center; padding: 14px 2px 12px 2px; border-radius: 10px; border: 1px solid transparent; }}
.stApp .glc-angle.decide {{ background: var(--voile); }}
.stApp .glc-angle svg {{ display: block; margin: 0 auto; }}
.stApp .glc-angle .nom {{ font-size: var(--t1); font-weight: 600; color: var(--encre); margin-top: 6px; }}
.stApp .glc-angle .avant {{ font-size: var(--t1); color: var(--gris); }}
.stApp .glc-angle .avant:empty {{ display: none; }}
.stApp .glc-angle .tag {{ display: block; font-size: var(--t1); font-weight: 600; color: var(--violet);
  white-space: nowrap; margin-top: 2px; }}
.stApp .glc-legende {{ font-size: var(--t1); color: var(--gris); margin: 10px 0 0 0; }}

/* ---------- tableaux ---------- */
.stApp .glc-defile {{ overflow-x: auto; max-width: 100%; }}
.stApp table.glc-table {{ width: 100%; border-collapse: collapse; font-size: var(--t2); margin: 0; border: 0; }}
.stApp table.glc-table th, .stApp table.glc-table td {{ border: 0; }}
.stApp table.glc-table tr {{ border: 0; background: transparent; }}
.stApp table.glc-table th {{ text-align: left; font-size: var(--t1); font-weight: 600; color: var(--gris);
  padding: 0 12px 8px 0; border-bottom: 1px solid var(--bord); white-space: nowrap; }}
.stApp table.glc-table td {{ padding: 7px 12px 7px 0; line-height: 1.3; border-bottom: 1px solid var(--filet); color: var(--encre);
  vertical-align: middle; }}
.stApp table.glc-table tr:last-child td {{ border-bottom: 0; }}
.stApp table.glc-table .n {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; padding-right: 0;
  padding-left: 12px; }}
.stApp table.glc-table th.n {{ padding-right: 0; }}
.stApp .glc-table .s {{ color: var(--gris); font-size: var(--t1); }}
.stApp .glc-table b {{ font-weight: 600; }}
.stApp table.glc-table .nb {{ white-space: nowrap; }}
.stApp table.glc-table th:first-child {{ min-width: 180px; }}
.stApp table.glc-table .s {{ color: var(--gris); font-size: var(--t1); line-height: 1.45; display: inline-block; }}
.stApp .glc-barre {{ display: inline-block; width: 72px; height: 6px; border-radius: 6px; background: var(--voile);
  vertical-align: middle; margin-right: 10px; overflow: hidden; }}
.stApp .glc-barre i {{ display: block; height: 100%; border-radius: 6px; background: var(--encre); }}

/* répartition : anneau et zones permises */
.stApp .glc-repart {{ display: flex; gap: 28px; align-items: center; flex-wrap: wrap; }}
.stApp .glc-repart .lignes {{ flex: 1; min-width: 260px; }}
.stApp .glc-zone {{ display: grid; grid-template-columns: 12px minmax(110px, 1.1fr) 56px minmax(120px, 2fr); gap: 10px;
  align-items: center; padding: 7px 0; font-size: var(--t2); }}
.stApp .glc-zone .pt {{ width: 10px; height: 10px; border-radius: 3px; }}
.stApp .glc-zone .v {{ text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }}
.stApp .glc-zone .piste {{ position: relative; height: 6px; border-radius: 6px; background: var(--voile);
  margin: 0 8px; }}
.stApp .glc-zone .permis {{ position: absolute; top: 0; bottom: 0; border-radius: 6px; background: {POSITIF}; opacity: .55; }}
.stApp .glc-zone .cible {{ position: absolute; top: -3px; width: 2px; height: 12px; background: {GRIS}; opacity: .6; }}
.stApp .glc-zone .ici {{ position: absolute; top: -4px; width: 14px; height: 14px; margin-left: -7px; border-radius: 50%;
  background: var(--encre); border: 2.5px solid var(--surface); box-shadow: 0 0 0 1px rgba(var(--ombre), .25); }}
.stApp .glc-zone .ici.hors {{ background: {TENSION}; box-shadow: 0 0 0 1px {ENCRE}; }}

/* ---------- politique de placement (document) ---------- */
.stApp .glc-doc {{ background: var(--surface); border: 1px solid var(--bord); border-radius: var(--rayon);
  padding: 34px 40px 26px 40px; }}
.stApp .glc-doc .tete {{ border-bottom: 2px solid var(--encre); padding-bottom: 16px; margin-bottom: 0; }}
.stApp .glc-doc .tete h2 {{ font-size: var(--t4); font-weight: 700; margin: 0; letter-spacing: -0.02em; }}
.stApp .glc-doc .tete p {{ margin: 4px 0 0 0; color: var(--gris); font-size: var(--t2); }}
.stApp .glc-article {{ display: grid; grid-template-columns: 34px 210px 1fr; gap: 8px 14px; padding: 13px 0;
  border-bottom: 1px solid var(--filet); }}
.stApp .glc-article:last-of-type {{ border-bottom: 0; }}
.stApp .glc-article .no {{ font-size: var(--t1); font-weight: 600; color: var(--gris); padding-top: 2px;
  font-variant-numeric: tabular-nums; }}
.stApp .glc-article .nom {{ font-size: var(--t2); font-weight: 700; color: var(--encre); }}
.stApp .glc-article .corps p {{ margin: 0 0 4px 0; font-size: var(--t2); color: var(--encre); line-height: 1.5; }}
.stApp .glc-article .corps ul {{ margin: 0; padding-left: 18px; }}
.stApp .glc-article .corps li {{ font-size: var(--t2); margin: 0 0 2px 0; }}
.stApp .glc-article .source {{ font-size: var(--t1); color: var(--gris); margin: 6px 0 0 0; }}
.stApp .glc-article .glc-table {{ max-width: 520px; margin: 2px 0 4px 0; }}
.stApp .glc-article table.glc-table td {{ padding: 7px 12px 7px 0; }}
@media (max-width: 760px) {{
  .glc-doc {{ padding: 22px 18px; }}
  .glc-article {{ grid-template-columns: 26px 1fr; }}
  .glc-article .corps {{ grid-column: 2; }}
}}

.stApp .glc-rubrique {{ font-size: var(--t2); font-weight: 700; color: var(--encre); margin: 12px 0 0 0; }}
.stApp .glc-rubrique span {{ display: block; font-size: var(--t1); font-weight: 400; color: var(--gris); }}
.stApp .glc-rubrique-doc {{ font-size: var(--t1); font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: var(--encre); padding: 22px 0 6px 0; border-bottom: 1px solid var(--bord); }}
.stApp .glc-rubrique-doc span {{ font-weight: 400; letter-spacing: 0; text-transform: none; color: var(--gris);
  margin-left: 10px; font-size: var(--t1); }}

/* ---------- explication de l'agent ---------- */
.stApp .glc-explication p {{ margin: 0; font-size: var(--t2); line-height: 1.6; max-width: 72ch; }}
.stApp .glc-explication p.t {{ font-weight: 700; margin: 14px 0 2px 0; }}
.stApp .glc-explication p.t:first-child {{ margin-top: 0; }}
.stApp .glc-note-bas {{ font-size: var(--t1); color: var(--gris); margin: 12px 0 0 0; display: flex; gap: 6px;
  align-items: flex-start; }}
.stApp .glc-note-bas svg {{ flex: none; margin-top: 2px; }}

/* ---------- étapes de l'analyse ---------- */
.stApp .glc-etapes {{ list-style: none; margin: 0; padding: 0; }}
.stApp .glc-etapes li {{ display: grid; grid-template-columns: 18px 1fr; gap: 10px; padding: 7px 0; font-size: var(--t2);
  color: var(--encre); }}
.stApp .glc-etapes li .pt {{ width: 8px; height: 8px; border-radius: 50%; background: {BORD}; margin: 7px 0 0 4px; }}
.stApp .glc-etapes li.fini .pt {{ background: {POSITIF}; }}
.stApp .glc-etapes li.cours .pt {{ background: {VIOLET}; animation: glc-pouls 1.2s ease-in-out infinite; }}
.stApp .glc-etapes li.cours .quoi {{ font-weight: 600; }}
.stApp .glc-etapes li .qui {{ font-size: var(--t1); color: var(--violet); font-weight: 600; margin-left: 8px; white-space: nowrap; }}
.stApp .glc-etapes li .res {{ display: block; font-size: var(--t1); color: var(--gris); margin-top: 1px; }}
.stApp .glc-etapes h5 {{ font-size: var(--t1); font-weight: 600; color: var(--gris); margin: 10px 0 2px 0; }}
@keyframes glc-pouls {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(127, 86, 217, .35); }}
  50% {{ box-shadow: 0 0 0 6px rgba(127, 86, 217, 0); }} }}
.stApp .glc-direct {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
.stApp .glc-direct .rond {{ width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--piste);
  border-top-color: {VIOLET}; animation: glc-tourne .9s linear infinite; }}
@keyframes glc-tourne {{ to {{ transform: rotate(360deg); }} }}

/* ---------- état vide ---------- */
.stApp .glc-vide {{ text-align: center; padding: 56px 24px; border-radius: var(--rayon); background: var(--voile); }}
.stApp .glc-vide h3 {{ font-size: var(--t3); font-weight: 700; margin: 12px 0 4px 0; }}
.stApp .glc-vide p {{ color: var(--gris); margin: 0 auto; max-width: 46ch; font-size: var(--t2); }}
.stApp .glc-vide .puces {{ display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; margin-top: 16px; }}
.stApp .glc-vide .puces span {{ font-size: var(--t1); font-weight: 600; color: var(--gris); background: var(--surface);
  border: 1px solid var(--bord); border-radius: 999px; padding: 3px 12px; }}

/* ---------- aide ---------- */
.stApp .glc-liste-def {{ margin: 0; }}
.stApp .glc-liste-def div {{ display: grid; grid-template-columns: 150px 1fr; gap: 12px; padding: 9px 0;
  border-bottom: 1px solid var(--filet); font-size: var(--t2); align-items: baseline; }}
.stApp .glc-liste-def div:last-child {{ border-bottom: 0; }}
.stApp .glc-liste-def dt {{ font-weight: 600; }}
.stApp .glc-liste-def dd {{ margin: 0; color: var(--encre); }}
.stApp .glc-reponse {{ border-radius: 10px; padding: 14px 16px; font-size: var(--t2); margin-top: 6px; }}

/* ---------- contrôles Streamlit, au ton de la maison ---------- */
.stApp label[data-testid="stWidgetLabel"] p {{ font-size: var(--t1); font-weight: 600; color: var(--gris); }}
.stApp .stSelectbox div[role="group"], .stApp .stTextInput .react-aria-TextField > div,
.stApp div[data-testid="stNumberInputContainer"] {{ background: var(--surface); border: 1px solid var(--bord);
  border-radius: 10px; min-height: 42px; box-shadow: none; }}
.stApp .stSelectbox div[role="group"]:focus-within, .stApp .stTextInput .react-aria-TextField > div:focus-within,
.stApp div[data-testid="stNumberInputContainer"]:focus-within {{ border-color: var(--encre);
  box-shadow: 0 0 0 1px var(--encre); outline: none; }}
.stApp .stSelectbox input, .stApp .stTextInput input, .stApp .stNumberInput input {{ background: transparent;
  color: var(--encre); font-variant-numeric: tabular-nums; font-size: var(--t2); }}
.stApp .stSelectbox button, .stApp .stNumberInput button {{ background: transparent; color: var(--gris); }}
.stApp div[data-testid="stCaptionContainer"] {{ opacity: 1; color: var(--gris); }}
.stApp div[data-testid="InputInstructions"] {{ display: none; }}

.stApp .stButton > button, .stApp .stFormSubmitButton > button {{ border-radius: 999px; min-height: 42px;
  font-weight: 600; border: 1px solid var(--bord); background: var(--surface); color: var(--encre);
  padding: 6px 20px; transition: background .15s ease, border-color .15s ease; }}
.stApp .stButton > button p, .stApp .stFormSubmitButton > button p {{ font-size: var(--t2); font-weight: 600; }}
.stApp .stButton > button:hover, .stApp .stFormSubmitButton > button:hover {{ border-color: var(--encre);
  color: var(--encre); background: var(--surface); }}
.stApp .stButton > button[kind="primary"], .stApp .stFormSubmitButton > button[kind="primaryFormSubmit"] {{
  background: var(--accent); border-color: var(--accent); color: #fff; }}
.stApp .stButton > button[kind="primary"]:hover {{ background: {ACCENT_VIF}; border-color: {ACCENT_VIF}; color: #fff; }}
.stApp button:focus-visible {{ outline: 2px solid var(--encre); outline-offset: 2px; }}
.stApp .stButton > button:focus:not(:active), .stApp div[data-testid="stPopover"] button:focus:not(:active),
.stApp .stFormSubmitButton > button:focus:not(:active) {{ border-color: var(--bord); box-shadow: none;
  color: var(--encre); }}
.stApp .stButton > button[kind="primary"]:focus:not(:active) {{ border-color: var(--accent); color: #fff; }}
.stApp .stButton > button[kind="tertiary"] {{ border: 0; background: transparent; color: var(--gris);
  padding: 0; min-height: 0; text-decoration: underline; text-underline-offset: 3px; }}

/* choix à une réponse (opération, échelle des thèmes) : le même contrôle segmenté que la navigation */
div[class*="st-key-o_"] div[role="radiogroup"], div[class*="st-key-q_"] div[role="radiogroup"] {{ gap: 2px;
  background: var(--voile); border-radius: 999px; padding: 3px; width: fit-content; }}
div[class*="st-key-o_"] label[data-testid="stRadioOption"], div[class*="st-key-q_"] label[data-testid="stRadioOption"] {{
  margin: 0; padding: 4px 12px; border-radius: 999px; cursor: pointer; }}
div[class*="st-key-o_"] label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]),
div[class*="st-key-q_"] label[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) {{ display: none; }}
div[class*="st-key-o_"] label[data-testid="stRadioOption"] p, div[class*="st-key-q_"] label[data-testid="stRadioOption"] p {{
  font-size: var(--t1); font-weight: 600; color: var(--gris); white-space: nowrap; }}
div[class*="st-key-o_"] label[data-testid="stRadioOption"][data-selected="true"],
div[class*="st-key-q_"] label[data-testid="stRadioOption"][data-selected="true"] {{ background: var(--surface);
  box-shadow: 0 1px 2px rgba(var(--ombre), 0.12); }}
div[class*="st-key-o_"] label[data-testid="stRadioOption"][data-selected="true"] p,
div[class*="st-key-q_"] label[data-testid="stRadioOption"][data-selected="true"] p {{ color: var(--encre); }}
div[class*="st-key-o_"][class*="_operation"], div[class*="st-key-o_"][class*="_operation"] div[data-testid="stRadio"] {{
  width: 100% !important; }}
div[class*="st-key-o_"][class*="_operation"] div[role="radiogroup"] {{ border-radius: 14px; display: grid;
  grid-template-columns: 1fr 1fr; width: 100%; }}
div[class*="st-key-o_"][class*="_operation"] label[data-testid="stRadioOption"] {{ border-radius: 11px;
  justify-content: center; padding: 6px 8px; width: 100%; }}
div[class*="st-key-o_"][class*="_operation"] div[role="radiogroup"] > div {{ display: flex; }}

/* thèmes : le libellé à gauche, l'échelle à droite, les échelles alignées */
div[class*="st-key-q_"][class*="_theme_"] {{ width: 100% !important; }}
div[class*="st-key-q_"][class*="_theme_"] div[data-testid="stRadio"] {{ display: grid; width: 100%;
  grid-template-columns: minmax(200px, 340px) 1fr; align-items: center; gap: 12px; padding: 5px 0;
  border-bottom: 1px solid var(--filet); }}
div[class*="st-key-q_"][class*="_theme_"] label[data-testid="stWidgetLabel"] {{ margin: 0; min-height: 0; }}
div[class*="st-key-q_"][class*="_theme_"] label[data-testid="stWidgetLabel"] p {{ font-size: var(--t2);
  font-weight: 500; color: var(--encre); }}
div[class*="st-key-q_"][class*="_theme_"] div[role="radiogroup"] {{ flex-wrap: nowrap; }}
div[class*="st-key-carte_fiche"] {{ gap: 0.5rem; }}
@media (max-width: 900px) {{
  div[class*="st-key-q_"][class*="_theme_"] div[data-testid="stRadio"] {{ grid-template-columns: 1fr; gap: 4px; }}
  div[class*="st-key-q_"][class*="_theme_"] div[role="radiogroup"] {{ flex-wrap: wrap; border-radius: 14px; }}
}}

/* sections repliées */
.stApp div[data-testid="stExpander"] details {{ border: 1px solid var(--bord); border-radius: var(--rayon);
  background: var(--surface); }}
.stApp div[data-testid="stExpander"] summary {{ padding: 12px 18px; }}
.stApp div[data-testid="stExpander"] summary p {{ font-size: var(--t2); font-weight: 600; color: var(--encre); }}
.stApp div[data-testid="stExpander"] summary:hover {{ color: var(--encre); }}
.stApp div[data-testid="stExpander"] div[data-testid="stExpanderDetails"] {{ padding: 4px 18px 16px 18px; }}

/* messages */
.stApp div[data-testid="stAlert"] {{ border-radius: 10px; border: 1px solid var(--bord); }}
.stApp div[data-testid="stAlert"] p {{ font-size: var(--t2); }}
hr {{ border-color: var(--bord); }}

@media (max-width: 640px) {{
  .stApp .glc-barre {{ display: none; }}
  .stApp .glc-sombre .note {{ position: static; display: block; margin: 0 0 6px 0; }}
  .st-key-page label[data-testid="stRadioOption"] {{ padding: 6px 10px; }}
  .stApp .glc-intro {{ height: auto; display: block; }}
  .stApp .glc-intro h1 {{ font-size: var(--t4); }}
  .stApp .glc-vue, .stApp .glc-vue:has(.glc-billet) {{ height: auto; min-height: 220px; padding: 14px; }}
  .stApp .glc-vue.film {{ height: auto; aspect-ratio: 1.3; padding: 8px; }}
  .stApp .glc-paire {{ grid-template-columns: 1fr; }}
  .stApp .glc-paire > svg {{ transform: rotate(90deg); }}
  .stApp table.glc-table .nb {{ white-space: normal; }}
  .stApp table.glc-table th, .stApp table.glc-table td {{ padding-right: 8px; }}
  .stMainBlockContainer {{ padding: 0 14px 56px 14px; }}
  .glc-marque .sous {{ display: none; }}
  .st-key-page div[role="radiogroup"] {{ margin: 0; overflow-x: auto; max-width: 100%; }}
  div[class*="st-key-compte"] {{ justify-content: flex-start; }}
  div[class*="st-key-carte"], .glc-carte, .glc-verdict {{ padding: 18px 16px; }}
  .glc-liste-def div {{ grid-template-columns: 1fr; gap: 2px; }}
}}
</style>"""
