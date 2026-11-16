"""Identité visuelle de Garder le cap : couleurs, tailles et feuille de style, en un seul endroit.

Une seule famille de caractères (Manrope), quatre tailles, un rayon, un bord. Un seul accent (rouge),
réservé à l'action principale et à la marque ; une couleur par verdict, jamais confondue avec l'accent.
"""

from __future__ import annotations

# La palette vient de deux sources et de nulle part ailleurs : le site de courtage de la Banque Nationale
# (captures du 15 novembre) et le Datathon (couleurs des diapositives remises aux participants).
# Version claire : le blanc et le gris chaud mènent ; le noir sert au texte ; le rouge reste rare.
BLANC = "#FFFFFF"        # Banque Nationale : fond des pages
ENCRE = "#222222"        # Datathon : texte des diapositives (Banque Nationale : #333333)
MARINE = "#152532"       # Datathon : bleu marine des diapositives ; un seul élément de structure, le bandeau
GRIS = "#6E6E71"         # Datathon : gris du texte secondaire, et seulement lui
BORD = "#DADADA"         # Banque Nationale : bord fin des cartes et de la barre
FILET = "#E6E2DE"        # Datathon : gris chaud clair, pour les filets entre deux lignes
VOILE = "#F6F4F0"        # Banque Nationale : gris chaud des sections
PISTE = "#EDEDED"        # Banque Nationale : gris des panneaux, piste des jauges
ACCENT = "#CC322B"       # Banque Nationale : le rouge, pour l'action principale et la marque
ACCENT_VIF = "#DE161D"   # Datathon : le rouge des diapositives, au survol de l'action principale
SAUGE = "#A8C1B8"        # Datathon : vert sauge
OR = "#F6C45E"           # Datathon : or
ARDOISE_PALE = "#DCE5EA" # Datathon : bleu ardoise pâle
GRIS_CHAUD = "#D9D5D0"   # Datathon : gris chaud moyen

FOND = BLANC
SURFACE = BLANC

# Une couleur par verdict, jamais le rouge de l'accent. Le mot du verdict reste écrit à l'encre :
# la couleur le marque (point, filet, arc), le fond en est une version pâle.
COULEURS_VERDICT = {"compatible": SAUGE, "en_tension": OR, "incompatible": MARINE}
FONDS_VERDICT = {"compatible": "#E9F0ED", "en_tension": "#FDF3DC", "incompatible": ARDOISE_PALE}
COULEURS_CLASSES = {"actions": MARINE, "revenu_fixe": GRIS, "liquidites": ARDOISE_PALE, "alternatifs": GRIS_CHAUD}
COULEUR_AUTRE = PISTE

POLICE = "Manrope"

CSS = f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap');

:root {{
  --encre: {ENCRE}; --gris: {GRIS}; --bord: {BORD}; --fond: {FOND}; --surface: {SURFACE};
  --voile: {VOILE}; --accent: {ACCENT}; --filet: {FILET}; --piste: {PISTE}; --marine: {MARINE};
  --t1: 13px; --t2: 15px; --t3: 18px; --t4: 26px;
  --rayon: 12px;
}}

/* ---------- base ---------- */
html, body, .stApp, .stApp * {{ font-family: '{POLICE}', -apple-system, 'Segoe UI', sans-serif; }}
.stApp span[data-testid="stIconMaterial"], .stApp [class*="material-symbols"] {{
  font-family: 'Material Symbols Rounded' !important; }}
.stApp {{ background: radial-gradient(1000px 360px at 92% -140px, rgba(222,22,29,0.05), transparent 70%), var(--fond); }}
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
.st-key-page label[data-testid="stRadioOption"] p {{ font-size: var(--t2); font-weight: 600; color: var(--gris); }}
.st-key-page label[data-testid="stRadioOption"]:hover p {{ color: var(--encre); }}
.st-key-page label[data-testid="stRadioOption"][data-selected="true"] {{ background: var(--surface);
  box-shadow: 0 1px 2px rgba(34,34,34,0.12); }}
.st-key-page label[data-testid="stRadioOption"][data-selected="true"] p {{ color: var(--encre); }}

/* compte */
div[class*="st-key-compte"] {{ align-items: flex-end; }}
div[class*="st-key-compte"] div[data-testid="stPopover"] {{ width: auto; margin-left: auto; }}
div[class*="st-key-compte"] div[data-testid="stPopover"] > div > button {{ border-radius: 999px; padding: 4px 14px 4px 10px;
  min-height: 38px; border: 1px solid var(--bord); background: var(--surface); }}
div[class*="st-key-compte"] div[data-testid="stPopover"] > div > button p {{ font-weight: 600; font-size: var(--t2); }}

/* le menu du compte : une liste de clients, le client choisi sur fond gris chaud */
div[data-testid="stPopoverBody"] {{ border-radius: var(--rayon); border: 1px solid var(--bord); padding: 14px;
  box-shadow: 0 8px 24px rgba(34,34,34,0.10); min-width: 300px; }}
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
div[class*="st-key-introduction"] {{ max-width: 1040px; margin: 16px auto 0 auto; }}
.stApp .glc-pas-intro {{ display: flex; align-items: center; gap: 6px; }}
.stApp .glc-pas-intro span {{ font-size: var(--t1); font-weight: 600; color: var(--gris); margin-right: 8px;
  font-variant-numeric: tabular-nums; }}
.stApp .glc-pas-intro i {{ width: 22px; height: 4px; border-radius: 4px; background: var(--piste); }}
.stApp .glc-pas-intro i.ici {{ background: var(--encre); }}
.stApp .glc-intro h1 {{ font-size: var(--t4); font-weight: 700; line-height: 1.25; margin: 0 0 14px 0;
  letter-spacing: -0.02em; }}
.stApp .glc-intro p {{ font-size: var(--t3); line-height: 1.5; color: var(--encre); margin: 0 0 8px 0; }}
.stApp .glc-intro p:last-child {{ margin-bottom: 20px; color: var(--gris); }}
.stApp .glc-intro {{ min-height: 270px; padding-top: 34px; }}
.stApp .glc-vue {{ background: var(--voile); border-radius: 20px; padding: 28px; height: 440px; overflow: hidden;
  display: flex; flex-direction: column; justify-content: center; position: relative; }}
.stApp .glc-vue:has(.glc-doc) {{ justify-content: flex-start; }}
.stApp .glc-vue:has(.glc-doc)::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 90px;
  background: linear-gradient(to bottom, rgba(246,244,240,0), var(--voile)); }}
.stApp .glc-vue .glc-angles {{ grid-template-columns: repeat(5, 1fr); gap: 2px; }}
.stApp .glc-vue .glc-angle svg {{ width: 66px; height: 66px; }}
.stApp .glc-vue .glc-angle .tag {{ white-space: normal; line-height: 1.25; }}
.stApp .glc-vue .glc-carte {{ padding: 22px 16px; }}
.stApp .glc-vue > * {{ box-shadow: 0 10px 30px rgba(34,34,34,0.07); }}
.stApp .glc-vue .glc-doc {{ padding: 22px 24px 10px 24px; }}
.stApp .glc-vue .glc-doc .tete h2 {{ font-size: var(--t3); }}
.stApp .glc-vue .glc-article {{ grid-template-columns: 26px 1fr; }}
.stApp .glc-vue .glc-article .corps {{ grid-column: 2; }}
div[class*="st-key-introduction"] .stButton > button[kind="tertiary"] {{ float: right; }}
div[class*="st-key-carte_compte"] .glc-faits {{ margin: 14px 0 6px 0; }}

/* ---------- étapes numérotées ---------- */
.stApp .glc-pas {{ display: grid; grid-template-columns: 28px 1fr; gap: 4px 12px; padding: 10px 0;
  border-bottom: 1px solid var(--filet); }}
.stApp .glc-pas:last-child {{ border-bottom: 0; }}
.stApp .glc-pas .no {{ font-size: var(--t1); font-weight: 600; color: var(--gris); padding-top: 2px; }}
.stApp .glc-pas b {{ font-weight: 700; }}
.stApp .glc-pas p {{ margin: 0; font-size: var(--t2); }}

/* ---------- pastilles ---------- */
.stApp .glc-pastille {{ display: inline-flex; align-items: center; gap: 6px; font-size: var(--t1); font-weight: 600;
  padding: 3px 10px; border-radius: 999px; white-space: nowrap; }}
.stApp .glc-pastille i {{ width: 7px; height: 7px; border-radius: 50%; background: currentColor; display: inline-block; }}
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
.stApp .glc-angles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(122px, 1fr)); gap: 6px; }}
.stApp .glc-angle {{ text-align: center; padding: 14px 2px 12px 2px; border-radius: 10px; border: 1px solid transparent; }}
.stApp .glc-angle.decide {{ background: var(--voile); }}
.stApp .glc-angle svg {{ display: block; margin: 0 auto; }}
.stApp .glc-angle .nom {{ font-size: var(--t1); font-weight: 600; color: var(--encre); margin-top: 6px; }}
.stApp .glc-angle .avant {{ font-size: var(--t1); color: var(--gris); }}
.stApp .glc-angle .avant:empty {{ display: none; }}
.stApp .glc-angle .tag {{ display: block; font-size: var(--t1); font-weight: 600; color: var(--encre);
  white-space: nowrap; margin-top: 2px; }}
.stApp .glc-legende {{ font-size: var(--t1); color: var(--gris); margin: 10px 0 0 0; }}

/* ---------- tableaux ---------- */
.stApp table.glc-table {{ width: 100%; border-collapse: collapse; font-size: var(--t2); margin: 0; border: 0; }}
.stApp table.glc-table th, .stApp table.glc-table td {{ border: 0; }}
.stApp table.glc-table tr {{ border: 0; background: transparent; }}
.stApp table.glc-table th {{ text-align: left; font-size: var(--t1); font-weight: 600; color: var(--gris);
  padding: 0 12px 8px 0; border-bottom: 1px solid var(--bord); white-space: nowrap; }}
.stApp table.glc-table td {{ padding: 9px 12px 9px 0; line-height: 1.35; border-bottom: 1px solid var(--filet); color: var(--encre);
  vertical-align: middle; }}
.stApp table.glc-table tr:last-child td {{ border-bottom: 0; }}
.stApp table.glc-table .n {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; padding-right: 0;
  padding-left: 12px; }}
.stApp table.glc-table th.n {{ padding-right: 0; }}
.stApp .glc-table .s {{ color: var(--gris); font-size: var(--t1); }}
.stApp .glc-table b {{ font-weight: 600; }}
.stApp table.glc-table .nb {{ white-space: nowrap; }}
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
.stApp .glc-zone .permis {{ position: absolute; top: 0; bottom: 0; border-radius: 6px; background: {SAUGE}; opacity: .55; }}
.stApp .glc-zone .cible {{ position: absolute; top: -3px; width: 2px; height: 12px; background: {GRIS}; opacity: .6; }}
.stApp .glc-zone .ici {{ position: absolute; top: -4px; width: 14px; height: 14px; margin-left: -7px; border-radius: 50%;
  background: var(--encre); border: 2.5px solid var(--surface); box-shadow: 0 0 0 1px rgba(34,34,34,.25); }}
.stApp .glc-zone .ici.hors {{ background: {OR}; box-shadow: 0 0 0 1px {ENCRE}; }}

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
.stApp .glc-etapes li .pt {{ width: 8px; height: 8px; border-radius: 50%; background: {GRIS_CHAUD}; margin: 7px 0 0 4px; }}
.stApp .glc-etapes li.fini .pt {{ background: {SAUGE}; }}
.stApp .glc-etapes li.cours .pt {{ background: var(--encre); animation: glc-pouls 1.2s ease-in-out infinite; }}
.stApp .glc-etapes li.cours .quoi {{ font-weight: 600; }}
.stApp .glc-etapes li .qui {{ font-size: var(--t1); color: var(--gris); margin-left: 8px; white-space: nowrap; }}
.stApp .glc-etapes li .res {{ display: block; font-size: var(--t1); color: var(--gris); margin-top: 1px; }}
.stApp .glc-etapes h5 {{ font-size: var(--t1); font-weight: 600; color: var(--gris); margin: 10px 0 2px 0; }}
@keyframes glc-pouls {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(34,34,34,.30); }}
  50% {{ box-shadow: 0 0 0 6px rgba(34,34,34,0); }} }}
.stApp .glc-direct {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
.stApp .glc-direct .rond {{ width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--piste);
  border-top-color: var(--encre); animation: glc-tourne .9s linear infinite; }}
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
  box-shadow: 0 1px 2px rgba(34,34,34,0.12); }}
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
  .stApp .glc-intro {{ min-height: 0; padding-top: 4px; }}
  .stApp .glc-vue {{ height: auto; min-height: 220px; padding: 16px; }}
  .stMainBlockContainer {{ padding: 0 14px 56px 14px; }}
  .glc-marque .sous {{ display: none; }}
  .st-key-page div[role="radiogroup"] {{ margin: 0; overflow-x: auto; max-width: 100%; }}
  div[class*="st-key-compte"] {{ justify-content: flex-start; }}
  div[class*="st-key-carte"], .glc-carte, .glc-verdict {{ padding: 18px 16px; }}
  .glc-liste-def div {{ grid-template-columns: 1fr; gap: 2px; }}
}}
</style>"""
