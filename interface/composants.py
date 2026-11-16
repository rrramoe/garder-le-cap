"""Composants visuels : du HTML et du SVG, sans état. Chaque fonction rend une chaîne à afficher telle quelle."""

from __future__ import annotations

import html
import math

from interface.theme import (ACCENT, BLANC, BORD, COULEUR_AUTRE, COULEURS_VERDICT, ENCRE, FONDS_VERDICT,
                             FORMES_VERDICT, GRIS, PISTE, POSITIF, TENSION, VOILE)


def e(texte) -> str:
    """Texte rendu sans interprétation (ni balise, ni formule)."""
    return " ".join(html.escape(str(texte if texte is not None else ""), quote=False).split())


def marque(taille: int = 26) -> str:
    """La marque : la lettre σ, tracée (aucune police requise), au bleu d'accent."""
    return (f'<svg width="{taille}" height="{taille}" viewBox="0 0 32 32" fill="none" aria-hidden="true">'
            f'<circle cx="14" cy="18.5" r="8.6" stroke="{ACCENT}" stroke-width="3.6"/>'
            f'<path d="M14 9.9H28" stroke="{ACCENT}" stroke-width="3.6" stroke-linecap="round"/></svg>')


def icone_onglet():
    """La marque en image, pour l'onglet du navigateur : σ en blanc sur un carré arrondi au bleu d'accent."""
    from PIL import Image, ImageDraw
    n = 128
    image = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    dessin = ImageDraw.Draw(image)
    dessin.rounded_rectangle([0, 0, n - 1, n - 1], radius=34, fill=ACCENT)
    dessin.ellipse([24, 44, 84, 104], outline=BLANC, width=13)
    dessin.rounded_rectangle([54, 44, 106, 57], radius=6, fill=BLANC)
    return image


def entete_marque() -> str:
    from interface.textes import DESCRIPTEUR, NOM
    return (f'<div class="glc-marque">{marque()}<span class="nom">{e(NOM)}</span>'
            f'<span class="sous">{e(DESCRIPTEUR)}</span></div>')


def bandeau(texte: str) -> str:
    return f'<div class="glc-bandeau">{e(texte)}</div>'


def titre_page(titre: str, sous: str = "") -> str:
    return f'<div class="glc-titre"><h1>{e(titre)}</h1>' + (f"<p>{e(sous)}</p>" if sous else "") + "</div>"


def h2(titre: str, sur: str = "") -> str:
    return f'<p class="glc-h2">{e(titre)}</p>' + (f'<p class="glc-sur">{e(sur)}</p>' if sur else "")


def forme(code: str | None, couleur: str, classe: str = "") -> str:
    """Le signe d'un verdict : un point plein, un anneau ou un carré, pour ne jamais dépendre de la couleur seule."""
    signe = FORMES_VERDICT.get(code, "point")
    return f'<i class="{(classe + " " + signe).strip()}" style="background:{couleur};--teinte-forme:{couleur}"></i>'


def pastille(libelle: str, code: str | None) -> str:
    couleur, fond = COULEURS_VERDICT.get(code, GRIS), FONDS_VERDICT.get(code, VOILE)
    return (f'<span class="glc-pastille" style="color:{ENCRE};background:{fond}">'
            f'{forme(code, couleur)}{e(libelle)}</span>')


def marqueur(texte: str) -> str:
    return f'<span class="glc-marqueur">{e(texte)}</span>'


# ---------------------------------------------------------------- cadran d'un angle

def cadran(note: float | None, passage: float, taille: int = 84) -> str:
    """Cadran de 0 à 100 : l'arc suit la note, un trait marque la note de passage."""
    r, c = 34.0, 44.0
    tour = 2 * math.pi * r
    arc = 0.75 * tour
    piste = (f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{PISTE}" '
             f'stroke-width="7" stroke-linecap="round" stroke-dasharray="{arc:.1f} {tour:.1f}" '
             + ('' if note is not None else 'stroke-dashoffset="0" opacity=".7" ')
             + f'transform="rotate(135 {c} {c})"/>')
    if note is None:
        return (f'<svg width="{taille}" height="{taille}" viewBox="0 0 88 88" role="img" aria-label="sans objet">{piste}'
                f'<text x="{c}" y="{c + 5}" text-anchor="middle" font-size="15" font-weight="600" fill="{GRIS}">—</text></svg>')
    n = max(0.0, min(100.0, float(note)))
    couleur = POSITIF if note >= passage else TENSION
    valeur = (f'<circle class="arc" cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{couleur}" stroke-width="7" stroke-linecap="round" '
              f'stroke-dasharray="{max(arc * n / 100, 0.1):.1f} {tour:.1f}" transform="rotate(135 {c} {c})"/>')
    a = math.radians(135 + 270 * max(0.0, min(100.0, passage)) / 100)
    x1, y1 = c + (r - 7) * math.cos(a), c + (r - 7) * math.sin(a)
    x2, y2 = c + (r + 7) * math.cos(a), c + (r + 7) * math.sin(a)
    trait = (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{BLANC}" stroke-width="5"/>'
             f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{ENCRE}" stroke-width="2" '
             'stroke-linecap="round"/>')
    return (f'<svg width="{taille}" height="{taille}" viewBox="0 0 88 88" role="img" aria-label="note {round(n)} sur 100">'
            f'{piste}{valeur}{trait}'
            f'<text x="{c}" y="{c + 7}" text-anchor="middle" font-size="21" font-weight="700" fill="{ENCRE}" '
            f'style="font-variant-numeric:tabular-nums">{round(n)}</text></svg>')


def angles(lignes: list[dict], passage: float, legende: str = "") -> str:
    """Les angles côte à côte. Chaque ligne : {nom, note, avant, decide, aide}."""
    blocs = []
    for l in lignes:
        avant = ""
        if l.get("note") is None:
            avant = "sans objet"
        elif l.get("avant") is not None and round(l["avant"]) != round(l["note"]):
            avant = f"avant : {round(l['avant'])}"
        tag = '<span class="tag">Angle déterminant</span>' if l.get("decide") else ""
        blocs.append(f'<div class="glc-angle{" decide" if l.get("decide") else ""}" title="{e(l.get("aide", ""))}">'
                     f'{cadran(l.get("note"), passage)}<div class="nom">{e(l["nom"])}</div>'
                     f'<div class="avant">{e(avant)}</div>{tag}</div>')
    bas = f'<p class="glc-legende">{e(legende)}</p>' if legende else ""
    return f'<div class="glc-angles">{"".join(blocs)}</div>{bas}'


# ---------------------------------------------------------------- verdict

def carte_verdict(ordre: str, libelle: str, code: str, raison: str, suite: str = "") -> str:
    couleur = COULEURS_VERDICT.get(code, ENCRE)
    return (f'<div class="glc-verdict" style="--teinte:{couleur}"><p class="ordre">{e(ordre)}</p>'
            f'<p class="mot">{forme(code, couleur, "pt")}{e(libelle)}</p><p class="raison">{e(raison)}</p>'
            + (f'<p class="suite">{e(suite)}</p>' if suite else "") + "</div>")


# ---------------------------------------------------------------- tableaux

def tableau(colonnes: list[tuple[str, str]], lignes: list[list[str]]) -> str:
    """colonnes : (titre, classe) avec la classe « n » pour un nombre. Les cellules sont déjà du HTML sûr."""
    tete = "".join(f'<th class="{c}">{e(t)}</th>' for t, c in colonnes)
    corps = "".join("<tr>" + "".join(f'<td class="{colonnes[i][1]}">{cell}</td>' for i, cell in enumerate(l)) + "</tr>"
                    for l in lignes)
    return (f'<div class="glc-defile"><table class="glc-table"><thead><tr>{tete}</tr></thead>'
            f'<tbody>{corps}</tbody></table></div>')


def barre(pct: float, maximum: float = 100.0) -> str:
    largeur = 0 if maximum <= 0 else max(0.0, min(100.0, pct / maximum * 100))
    return f'<span class="glc-barre"><i style="width:{largeur:.1f}%"></i></span>'


# ---------------------------------------------------------------- répartition

def anneau(parts: list[tuple[str, float, str]], taille: int = 148) -> str:
    """Anneau de répartition. parts : (nom, pourcentage, couleur)."""
    r, c = 52.0, 70.0
    tour = 2 * math.pi * r
    total = sum(max(p, 0.0) for _, p, _ in parts) or 1.0
    arcs, depart = [], 0.0
    for nom, p, couleur in parts:
        longueur = max(p, 0.0) / total * tour
        if longueur <= 0:
            continue
        arcs.append(f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{couleur}" stroke-width="17" '
                    f'stroke-dasharray="{max(longueur - 1.5, 0.5):.2f} {tour:.2f}" stroke-dashoffset="{-depart:.2f}" '
                    f'transform="rotate(-90 {c} {c})"><title>{e(nom)}</title></circle>')
        depart += longueur
    return f'<svg width="{taille}" height="{taille}" viewBox="0 0 140 140" role="img" aria-label="Répartition">{"".join(arcs)}</svg>'


def ligne_zone(nom: str, valeur: str, poids: float, zone: dict | None, couleur: str) -> str:
    """Une classe d'actif : sa part, et sa place dans la zone permise par la politique de placement."""
    piste = ""
    if zone:
        mini, maxi, cible = float(zone["min"]), float(zone["max"]), float(zone.get("cible", zone["min"]))
        hors = not (mini - 1e-9 <= poids <= maxi + 1e-9)
        piste = (f'<div class="piste" title="Zone permise : {mini:g} à {maxi:g} %, cible {cible:g} %">'
                 f'<div class="permis" style="left:{mini}%;width:{max(maxi - mini, 0)}%"></div>'
                 f'<div class="cible" style="left:{cible}%"></div>'
                 f'<div class="ici{" hors" if hors else ""}" style="left:{max(0.0, min(100.0, poids))}%"></div></div>')
    return (f'<div class="glc-zone"><span class="pt" style="background:{couleur or COULEUR_AUTRE}"></span>'
            f'<span>{e(nom)}</span><span class="v">{e(valeur)}</span>{piste or "<span></span>"}</div>')


# ---------------------------------------------------------------- politique de placement

def article(numero: int, nom: str, corps: str, source: str = "") -> str:
    bas = f'<p class="source">{source}</p>' if source else ""
    return (f'<div class="glc-article"><div class="no">{numero:02d}</div><div class="nom">{e(nom)}</div>'
            f'<div class="corps">{corps}{bas}</div></div>')


def etape_du_chemin(numero: int, mot: str) -> str:
    """Le repère d'une étape du chemin : son rang, et ce qui s'y passe."""
    return f'<p class="glc-etape"><b>{numero}</b>{e(mot)}</p>'


def passage(fils: int = 5) -> str:
    """Le passage d'une carte à l'autre : des fils où la lumière court de gauche à droite, sans fin."""
    return ('<div class="glc-passage">' + "".join(f'<span class="fil"><i style="animation-delay:-{k * 0.37:.2f}s"></i></span>'
                                                  for k in range(fils)) + "</div>")


def document(titre: str, sous: str, articles: list[str], tete: str = "") -> str:
    return (f'<div class="glc-doc"><div class="tete">{tete}<h2>{e(titre)}</h2><p>{e(sous)}</p></div>'
            + "".join(articles) + "</div>")


# ---------------------------------------------------------------- étapes de l'analyse

def etapes(lignes: list[dict], en_cours: bool = False) -> str:
    """lignes : {libelle, agent, fini, detail}. Pendant l'analyse, l'étape en cours bat doucement."""
    if not lignes:
        lignes = [{"libelle": "Je commence l'analyse.", "fini": False}]
    blocs = []
    for l in lignes:
        classe = "fini" if l.get("fini") else ("cours" if en_cours else "")
        qui = f'<span class="qui">{e(l["agent"])}</span>' if l.get("agent") else ""
        detail = f'<span class="res">{e(l["detail"])}</span>' if l.get("detail") else ""
        blocs.append(f'<li class="{classe}"><span class="pt"></span><span><span class="quoi">{e(l["libelle"])}</span>'
                     f'{qui}{detail}</span></li>')
    return f'<ul class="glc-etapes">{"".join(blocs)}</ul>'


def en_direct(titre: str, lignes: list[dict]) -> str:
    return (f'<div class="glc-carte"><div class="glc-direct"><span class="rond"></span>'
            f'<p class="glc-h2" style="margin:0">{e(titre)}</p></div>{etapes(lignes, en_cours=True)}</div>')


# ---------------------------------------------------------------- divers

def etat_vide(titre: str, texte: str, puces: list[str]) -> str:
    p = "".join(f"<span>{e(x)}</span>" for x in puces)
    return (f'<div class="glc-vide">{marque(34)}<h3>{e(titre)}</h3><p>{e(texte)}</p>'
            f'<div class="puces">{p}</div></div>')


def pas(lignes: list[tuple[str, str]]) -> str:
    """Une suite d'étapes numérotées : un titre, une phrase."""
    return "".join(f'<div class="glc-pas"><span class="no">{i:02d}</span><p><b>{e(t)}.</b> {e(x)}</p></div>'
                   for i, (t, x) in enumerate(lignes, start=1))


def coche(texte: str, ok: bool = True) -> str:
    couleur = POSITIF if ok else TENSION
    trace = "M4.4 8.2 7 10.8 11.6 5.6" if ok else "M8 4.5v4.2M8 11.2v.3"
    return (f'<p class="glc-note-bas"><svg width="16" height="16" viewBox="0 0 16 16" fill="none">'
            f'<circle cx="8" cy="8" r="8" fill="{couleur}"/>'
            f'<path d="{trace}" stroke="{ENCRE}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg><span>{e(texte)}</span></p>')


def definitions(paires: list[tuple[str, str]]) -> str:
    return '<dl class="glc-liste-def">' + "".join(f"<div><dt>{t}</dt><dd>{e(d)}</dd></div>" for t, d in paires) + "</dl>"


def reponse(texte: str, code: str | None) -> str:
    couleur, fond = COULEURS_VERDICT.get(code, PISTE), FONDS_VERDICT.get(code, VOILE)
    return f'<div class="glc-reponse" style="background:{fond};border-left:4px solid {couleur}">{e(texte)}</div>'


def suite(libelle: str, page: str, cle: str, principal: bool = True) -> None:
    """La fin d'une page : l'étape qui suit, à droite."""
    import streamlit as st
    from interface import etat
    _, droite = st.columns([2.2, 1])
    droite.button(libelle, key=cle, type="primary" if principal else "secondary", width="stretch",
                  on_click=etat.aller, args=(page,), icon=":material/arrow_forward:")


def courbe(valeurs: list[float], largeur: int = 96, hauteur: int = 28, couleur: str = ACCENT,
           remplie: bool = False, epaisseur: float = 1.8) -> str:
    """Une ligne de cours, en SVG : l'allure seule, sans axe. Vide si la série manque."""
    if len(valeurs) < 2:
        return ""
    bas, haut = min(valeurs), max(valeurs)
    ecart = (haut - bas) or 1.0
    marge = epaisseur + 1
    pas = (largeur - 2) / (len(valeurs) - 1)
    points = [(1 + i * pas, marge + (hauteur - 2 * marge) * (1 - (v - bas) / ecart)) for i, v in enumerate(valeurs)]
    trait = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in points)
    fond = ""
    if remplie:
        fond = (f'<path d="{trait} L{points[-1][0]:.1f} {hauteur} L{points[0][0]:.1f} {hauteur} Z" '
                f'fill="{couleur}" opacity=".16"/>')
    return (f'<svg class="glc-courbe" viewBox="0 0 {largeur} {hauteur}" width="{largeur}" height="{hauteur}" '
            f'preserveAspectRatio="none" aria-hidden="true">{fond}<path class="trait" d="{trait}" fill="none" '
            f'stroke="{couleur}" stroke-width="{epaisseur}" stroke-linejoin="round" stroke-linecap="round" '
            f'vector-effect="non-scaling-stroke" style="--long:{largeur * 3}"/></svg>')


def variation(pourcentage: float | None, periode: str = "") -> str:
    """Une variation, lisible sans la couleur : son signe et sa flèche la disent aussi."""
    if pourcentage is None:
        return ""
    hausse = pourcentage >= 0
    texte = f"{pourcentage:+.1f}".replace(".", ",").replace("-", "−") + " %"
    suite = f"<small>sur {e(periode)}</small>" if periode else ""
    return (f'<span class="glc-var {"hausse" if hausse else "baisse"}">{"▲" if hausse else "▼"} {texte}{suite}</span>')


def lien(mot: str) -> str:
    """Le lien entre deux cartes : un canal où la lumière descend, et le mot qui dit ce qui se passe."""
    return f'<div class="glc-lien"><span class="canal"><i></i><i></i><i></i></span><span class="mot">{e(mot)}</span></div>'


def etiquette_du_service(titre: str, sous: str = "") -> str:
    """Le nom du travail propre au service, avec sa marque."""
    return f'<p class="glc-sigma">{marque(18)}{e(titre)}' + (f"<span>· {e(sous)}</span>" if sous else "") + "</p>"


def montrer(contenu: str) -> None:
    """Affiche un composant. Le contenu ne passe par aucune mise en forme : il est rendu tel quel."""
    import streamlit as st
    st.markdown(contenu, unsafe_allow_html=True)
