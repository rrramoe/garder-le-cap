"""Les images qui jouent de l'introduction : de petites histoires dessinées, en SVG animé par des images clés CSS.

Aucun fichier vidéo, aucun script, aucun lecteur. Chaque film tourne seul, en boucle sans fin : tout se joue
sur une même durée, la dernière image est tenue, puis l'ensemble s'efface et recommence. L'état de base de
chaque élément est sa place dans l'image finale : un visiteur qui préfère moins de mouvement voit cette image,
immobile (la feuille de style coupe alors toute animation).
"""

from __future__ import annotations

import html

from interface.theme import (ACCENT, ARRET, ARRET_PALE, BLANC, BLEU_CLAIR, BORD, ENCRE, FILET, GRIS, PISTE, POSITIF,
                             POSITIF_PALE, TENSION, TENSION_PALE, VIOLET_PALE, VIOLET_TEXTE, VOILE)

DUREE = 10.0  # secondes ; la boucle complète

SIGNES = {"compatible": (POSITIF, POSITIF_PALE), "en_tension": (TENSION, TENSION_PALE), "incompatible": (ARRET, ARRET_PALE)}


def e(texte) -> str:
    return html.escape(str(texte if texte is not None else ""), quote=False)


class Film:
    """Fabrique les images clés d'un film et les classes qui les jouent."""

    def __init__(self, nom: str, duree: float = DUREE):
        self.nom, self.duree, self.regles, self.n = nom, duree, [], 0

    def _p(self, t: float) -> str:
        return f"{max(0.0, min(100.0, t / self.duree * 100)):.2f}%"

    def cle(self, etapes: list[tuple[float, str]], extra: str = "") -> str:
        """Une animation en images clés : [(instant en secondes, propriétés CSS)]. Rend le nom de sa classe."""
        self.n += 1
        nom = f"{self.nom}{self.n}"
        corps = " ".join(f"{self._p(t)} {{ {props} }}" for t, props in etapes)
        self.regles.append(f"@keyframes {nom} {{ {corps} }}")
        self.regles.append(f".{nom} {{ animation: {nom} {self.duree}s ease-out infinite both; "
                           f"transform-box: fill-box; transform-origin: center; {extra} }}")
        return nom

    def apparait(self, t: float, dx: float = 0, dy: float = 6, echelle: float = 1.0, duree: float = 0.35) -> str:
        """Caché jusqu'à t, puis en place jusqu'à la fin de la boucle."""
        cache = f"opacity: 0; transform: translate({dx}px, {dy}px) scale({echelle});"
        la = "opacity: 1; transform: none;"
        return self.cle([(0, cache), (t, cache), (t + duree, la), (self.duree, la)])

    def passe(self, t0: float, t1: float, fondu: float = 0.25) -> str:
        """Visible seulement entre t0 et t1 (un halo, un repère)."""
        return self.cle([(0, "opacity: 0;"), (t0, "opacity: 0;"), (t0 + fondu, "opacity: 1;"), (t1, "opacity: 1;"),
                         (t1 + fondu, "opacity: 0;"), (self.duree, "opacity: 0;")])

    def trace(self, t0: float, t1: float, longueur: float) -> str:
        """Un trait qui se dessine entre t0 et t1."""
        return self.cle([(0, f"stroke-dashoffset: {longueur};"), (t0, f"stroke-dashoffset: {longueur};"),
                         (t1, "stroke-dashoffset: 0;"), (self.duree, "stroke-dashoffset: 0;")],
                        extra=f"stroke-dasharray: {longueur};")

    def grandit(self, t0: float, t1: float) -> str:
        """Une barre qui s'allonge depuis sa gauche."""
        return self.cle([(0, "transform: scaleX(0);"), (t0, "transform: scaleX(0);"), (t1, "transform: none;"),
                         (self.duree, "transform: none;")], extra="transform-origin: left center;")

    def glisse(self, t0: float, t1: float, dx: float, dy: float = 0) -> str:
        """Un élément qui vient à sa place depuis un décalage."""
        loin = f"transform: translate({dx}px, {dy}px);"
        return self.cle([(0, loin), (t0, loin), (t1, "transform: none;"), (self.duree, "transform: none;")])

    def appuie(self, t: float) -> str:
        """Un bouton que l'on presse : il s'avance, s'enfonce, revient. Sans rebond."""
        return self.cle([(0, "transform: none;"), (t - 0.5, "transform: none;"), (t - 0.15, "transform: scale(1.05);"),
                         (t, "transform: scale(0.97);"), (t + 0.25, "transform: none;"), (self.duree, "transform: none;")])

    def bat(self, t0: float) -> str:
        """Une attente : l'élément apparaît à t0 puis bat doucement, sans jamais répondre."""
        etapes = [(0, "opacity: 0;"), (t0, "opacity: 0;"), (t0 + 0.3, "opacity: 1; transform: none;")]
        t = t0 + 0.3
        while t + 1.2 < self.duree - 0.2:
            etapes += [(t + 0.6, "opacity: .45; transform: scale(0.96);"), (t + 1.2, "opacity: 1; transform: none;")]
            t += 1.2
        etapes.append((self.duree, "opacity: 1; transform: none;"))
        return self.cle(etapes)

    def scene(self, contenu: str, largeur: int = 520, hauteur: int = 400, titre: str = "") -> tuple[str, str]:
        """Le film : sa feuille d'images clés, et son dessin. L'ensemble s'efface avant de recommencer."""
        d = self.duree
        self.regles.append(f"@keyframes {self.nom}0 {{ 0% {{ opacity: 0; }} {self._p(0.3)} {{ opacity: 1; }} "
                           f"{self._p(d - 0.45)} {{ opacity: 1; }} 100% {{ opacity: 0; }} }}")
        self.regles.append(f".{self.nom}0 {{ animation: {self.nom}0 {d}s linear infinite both; }}")
        style = "<style>" + " ".join(self.regles) + "</style>"
        dessin = (f'<svg class="film" viewBox="0 0 {largeur} {hauteur}" role="img" aria-label="{e(titre)}">'
                  f'<g class="{self.nom}0">{contenu}</g></svg>')
        return style, dessin


# ---------------------------------------------------------------- pièces de dessin

def carte(x: float, y: float, l: float, h: float, classe: str = "", rayon: float = 14) -> str:
    return (f'<rect class="{classe}" x="{x}" y="{y}" width="{l}" height="{h}" rx="{rayon}" fill="{BLANC}" '
            f'stroke="{BORD}" stroke-width="1.2"/>')


def texte(x: float, y: float, contenu: str, taille: float = 12, couleur: str = ENCRE, gras: bool = False,
          ancre: str = "start", classe: str = "") -> str:
    return (f'<text class="{classe}" x="{x}" y="{y}" font-size="{taille}" fill="{couleur}" text-anchor="{ancre}" '
            f'font-weight="{700 if gras else 500}">{e(contenu)}</text>')


def signe(x: float, y: float, code: str, taille: float = 4.5) -> str:
    """Le signe d'un verdict : un point plein, un anneau ou un carré."""
    couleur = SIGNES.get(code, (GRIS, VOILE))[0]
    if code == "en_tension":
        return f'<circle cx="{x}" cy="{y}" r="{taille - 1}" fill="none" stroke="{couleur}" stroke-width="2.4"/>'
    if code == "incompatible":
        return f'<rect x="{x - taille}" y="{y - taille}" width="{taille * 2}" height="{taille * 2}" rx="1.5" fill="{couleur}"/>'
    return f'<circle cx="{x}" cy="{y}" r="{taille}" fill="{couleur}"/>'


def pastille(x: float, y: float, libelle: str, code: str, classe: str = "", ancre: str = "start",
             taille: float = 12) -> str:
    """Une pastille de verdict : son signe, son mot. x est son bord gauche, son centre ou son bord droit."""
    largeur = len(libelle) * taille * 0.6 + 34
    gauche = x if ancre == "start" else (x - largeur / 2 if ancre == "middle" else x - largeur)
    fond = SIGNES.get(code, (GRIS, VOILE))[1]
    h = taille + 12
    return (f'<g class="{classe}"><rect x="{gauche}" y="{y - h / 2}" width="{largeur}" height="{h}" rx="{h / 2}" '
            f'fill="{fond}"/>{signe(gauche + 13, y, code)}'
            f'{texte(gauche + 24, y + taille * 0.36, libelle, taille, ENCRE, True)}</g>')


def champ(x: float, y: float, l: float, etiquette: str, valeur: str, classe_valeur: str = "",
          classe_halo: str = "", classe: str = "") -> str:
    """Un champ dessiné : son étiquette, son cadre, sa valeur, et le halo qui dit qu'on y est."""
    halo = (f'<rect class="{classe_halo}" x="{x - 3}" y="{y + 5}" width="{l + 6}" height="40" rx="11" fill="none" '
            f'stroke="{ACCENT}" stroke-width="2"/>' if classe_halo else "")
    return (f'<g class="{classe}">{texte(x, y, etiquette, 11, GRIS)}'
            f'<rect x="{x}" y="{y + 8}" width="{l}" height="34" rx="8" fill="{BLANC}" stroke="{BORD}" stroke-width="1.2"/>'
            f'{halo}{texte(x + 12, y + 30, valeur, 13, ENCRE, True, classe=classe_valeur)}</g>')


def bouton(x: float, y: float, l: float, libelle: str, classe: str = "") -> str:
    return (f'<g class="{classe}"><rect x="{x}" y="{y}" width="{l}" height="40" rx="20" fill="{ACCENT}"/>'
            f'{texte(x + l / 2, y + 25, libelle, 13, BLANC, True, "middle")}</g>')


# ---------------------------------------------------------------- 1. l'écart

def ecart() -> tuple[str, str]:
    """Le cours suit la zone de la politique de placement ; un ordre arrive, la ligne s'en écarte, l'écart est mesuré."""
    f = Film("fa")
    c = (f'<rect class="{f.apparait(0.2, dy=0)}" x="16" y="190" width="444" height="64" rx="32" fill="{BLEU_CLAIR}" opacity=".30"/>'
         + texte(40, 180, "Votre politique de placement", 13, GRIS, classe=f.apparait(0.4))
         + f'<g class="{f.apparait(0.7, dy=0, echelle=0.8)}"><circle cx="476" cy="222" r="15" fill="none" stroke="{ENCRE}" stroke-width="2"/>'
           f'<circle cx="476" cy="222" r="5" fill="{ENCRE}"/></g>'
         + texte(476, 266, "Vos objectifs", 13, ENCRE, True, "middle", f.apparait(0.9))
         + f'<path class="{f.trace(0.6, 2.3, 230)}" d="M40 230 C110 210 170 236 250 222" fill="none" stroke="{ENCRE}" stroke-width="3" stroke-linecap="round"/>'
         + f'<circle class="{f.apparait(2.4, dy=0, echelle=0.4)}" cx="250" cy="222" r="8" fill="{ENCRE}" stroke="{BLANC}" stroke-width="3"/>'
         + texte(250, 284, "Un ordre", 13, ENCRE, True, "middle", f.apparait(2.5))
         + f'<path class="{f.apparait(3.1, dy=0, duree=0.8)}" d="M250 222 C320 212 390 226 458 222" fill="none" stroke="{ENCRE}" stroke-width="2" stroke-dasharray="2 7" stroke-linecap="round"/>'
         + texte(352, 244, "il reste dans votre politique", 12, GRIS, False, "middle", f.apparait(3.7))
         + f'<path class="{f.trace(4.4, 5.8, 250)}" d="M250 222 C310 200 360 150 418 102" fill="none" stroke="{TENSION}" stroke-width="3" stroke-linecap="round"/>'
         + f'<circle class="{f.apparait(5.7, dy=0, echelle=0.4)}" cx="418" cy="102" r="6" fill="{TENSION}"/>'
         + texte(304, 124, "il vous en écarte", 12, GRIS, False, "end", f.apparait(5.3))
         + f'<line class="{f.apparait(6.4, dy=0)}" x1="418" y1="114" x2="418" y2="186" stroke="{GRIS}" stroke-width="1.5" stroke-dasharray="3 4"/>'
         + texte(428, 152, "l'écart, mesuré", 12, ENCRE, True, classe=f.apparait(6.7)))
    return f.scene(c, titre="Un ordre peut rester dans votre politique de placement ou s'en écarter : l'écart est mesuré")


# ---------------------------------------------------------------- 2. la fiche devient une politique de placement

def fiche() -> tuple[str, str]:
    """Un questionnaire simple se remplit, puis devient un document plus riche : des articles, chacun une limite."""
    f = Film("fb")
    questions = [("Objectif", 0), ("Horizon", 1), ("Risque", 1)]
    gauche = carte(16, 36, 216, 328) + texte(34, 66, "Votre fiche", 14, ENCRE, True)
    for i, (nom, choix) in enumerate(questions):
        y = 100 + i * 84
        gauche += texte(34, y, nom, 12, GRIS)
        for k in range(3):
            gauche += f'<rect x="{34 + k * 62}" y="{y + 12}" width="54" height="26" rx="13" fill="{VOILE}"/>'
        x = 34 + choix * 62
        t = 0.7 + i * 0.9
        gauche += (f'<g class="{f.apparait(t, dy=0, echelle=0.7, duree=0.25)}"><rect x="{x}" y="{y + 12}" width="54" height="26" rx="13" fill="{ACCENT}"/>'
                   f'<path d="M{x + 20} {y + 25} l5 5 l10 -10" fill="none" stroke="{BLANC}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></g>')
    gauche = f'<g class="{f.cle([(0, "opacity: 1;"), (3.6, "opacity: 1;"), (4.2, "opacity: .5;"), (DUREE, "opacity: .5;")])}">{gauche}</g>'
    fleche = (f'<path class="{f.apparait(3.5, dx=-8, dy=0)}" d="M240 200 H270 M262 192 l9 8 l-9 8" fill="none" stroke="{ENCRE}" '
              f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')
    droite = (carte(284, 20, 220, 360) + texte(300, 50, "Politique de placement", 13, ENCRE, True)
              + f'<line x1="300" y1="62" x2="488" y2="62" stroke="{ENCRE}" stroke-width="1.6"/>')
    articles = [("Profil d'investisseur", None, None, 2), ("Répartition", 40, 70, 96), ("Limites de risque", 0, 86, 58),
                ("Concentration", 0, 60, 30)]
    for j, (nom, debut, largeur, repere) in enumerate(articles):
        y = 94 + j * 72
        t = 4.6 + j * 0.8
        bloc = texte(300, y, f"{j + 1:02d}", 11, GRIS) + texte(324, y, nom, 12, ENCRE, True)
        if debut is None:  # le profil : une échelle à cinq degrés, l'un retenu
            for k in range(5):
                bloc += (f'<rect class="{f.apparait(t + 0.3, dy=0, echelle=0.6) if k == repere else ""}" x="{324 + k * 33}" y="{y + 12}" '
                         f'width="27" height="10" rx="5" fill="{ACCENT if k == repere else PISTE}"/>')
        else:  # une limite : sa piste, sa zone permise, son repère
            bloc += (f'<rect x="324" y="{y + 13}" width="160" height="8" rx="4" fill="{PISTE}"/>'
                     f'<rect class="{f.grandit(t + 0.2, t + 0.7)}" x="{324 + debut}" y="{y + 13}" width="{largeur}" height="8" rx="4" fill="{BLEU_CLAIR}"/>'
                     f'<circle class="{f.glisse(t + 0.3, t + 0.9, -repere)}" cx="{324 + repere}" cy="{y + 17}" r="6.5" fill="{ENCRE}" stroke="{BLANC}" stroke-width="2.4"/>')
        droite += f'<g class="{f.apparait(t)}">{bloc}</g>'
    droite = f'<g class="{f.apparait(3.9, dx=-10, dy=0, echelle=0.94, duree=0.5)}">{droite}</g>'
    return f.scene(gauche + fleche + droite, titre="Une fiche simple devient une politique de placement, faite de limites")


# ---------------------------------------------------------------- 3. l'ordre, mis à l'épreuve

def epreuve(ticker: str, montant: str) -> tuple[str, str]:
    """Un billet d'ordre dessiné se remplit, on presse « Analyser l'ordre », et l'issue se lit sur la zone de la
    politique : le point y reste, en sort, ou, parti de dehors, s'en rapproche."""
    f = Film("fc")
    billet = (carte(16, 44, 214, 300) + texte(34, 74, "Ordre", 14, ENCRE, True)
              + champ(34, 100, 178, "Titre", ticker, f.apparait(0.8, dy=0), f.passe(0.3, 1.5), f.cle(
                  [(0, "transform: none;"), (0.3, "transform: none;"), (0.6, "transform: scale(1.05);"),
                   (1.5, "transform: scale(1.05);"), (1.8, "transform: none;"), (DUREE, "transform: none;")]))
              + champ(34, 166, 178, "Montant", montant, f.apparait(2.1, dy=0), f.passe(1.7, 2.8), f.cle(
                  [(0, "transform: none;"), (1.7, "transform: none;"), (2.0, "transform: scale(1.05);"),
                   (2.8, "transform: scale(1.05);"), (3.1, "transform: none;"), (DUREE, "transform: none;")]))
              + f'<circle class="{f.cle([(0, "opacity: 0; transform: scale(.3);"), (3.5, "opacity: 0; transform: scale(.3);"), (3.6, "opacity: .35; transform: scale(.5);"), (4.3, "opacity: 0; transform: scale(1.5);"), (DUREE, "opacity: 0;")])}" '
                f'cx="123" cy="270" r="60" fill="{ACCENT}"/>'
              + bouton(34, 250, 178, "Analyser l'ordre", f.appuie(3.6)))
    issues = [("il y reste", "Compatible", "compatible", "M280 {m} C320 {a} 360 {b} 404 {m}", ENCRE, 0, 0),
              ("il en sort", "En tension", "en_tension", "M280 {m} C320 {m} 360 {h} 404 {s}", TENSION, 0, -36),
              ("il s'en rapproche", "En tension", "en_tension", "M280 {s} C320 {s} 350 {h} 404 {r}", ENCRE, -36, -12)]
    droite = ""
    for i, (legende, mot, code, chemin, couleur, depart, arrivee) in enumerate(issues):
        y, t = 60 + i * 108, 4.3 + i * 1.3
        m = y + 47
        d = chemin.format(m=m, a=m - 9, b=m + 9, h=m - 22, s=m - 36, r=m - 12)
        droite += (f'<g class="{f.apparait(t)}">' + texte(262, y + 6, legende, 12, GRIS)
                   + pastille(504, y + 2, mot, code, ancre="end", taille=11)
                   + f'<rect x="262" y="{y + 30}" width="242" height="34" rx="17" fill="{BLEU_CLAIR}" opacity=".30"/>'
                   + f'<circle cx="280" cy="{m + depart}" r="4.5" fill="{GRIS}"/></g>'
                   + f'<path class="{f.trace(t + 0.3, t + 1.1, 150)}" d="{d}" fill="none" stroke="{couleur}" stroke-width="2.6" stroke-linecap="round"/>'
                   + f'<circle class="{f.apparait(t + 1.0, dy=0, echelle=0.4, duree=0.25)}" cx="404" cy="{m + arrivee}" r="6" fill="{couleur}" stroke="{BLANC}" stroke-width="2"/>')
    return f.scene(billet + droite, titre="Un ordre est analysé avant d'être passé : il reste dans la politique, en sort, ou s'en rapproche")


# ---------------------------------------------------------------- 4. cinq angles, un verdict, et le pourquoi

def resultat(angles: list[dict], verdict: dict, passage: float) -> tuple[str, str]:
    """Les cadrans se remplissent, le plus bas devient l'angle déterminant, le verdict tombe, l'explication
    s'écrit, deux pistes testées paraissent. angles : {nom, note, decide}."""
    import math
    f = Film("fd")
    n = max(len(angles), 1)
    pas = 460 / n
    r = min(26.0, pas / 2 - 14)
    tour = 2 * math.pi * r
    arc = 0.75 * tour
    c = carte(16, 16, 488, 368)
    for i, a in enumerate(angles):
        x, y, t = 30 + pas * (i + 0.5), 86, 0.4 + i * 0.4
        if a.get("decide"):
            c += (f'<rect class="{f.apparait(2.8, dy=0, echelle=0.9)}" x="{x - pas / 2 + 4}" y="42" width="{pas - 8}" height="124" rx="10" fill="{VIOLET_PALE}"/>'
                  + texte(x, 150, "Angle", 10.5, VIOLET_TEXTE, True, "middle", f.apparait(3.0))
                  + texte(x, 162, "déterminant", 10.5, VIOLET_TEXTE, True, "middle", f.apparait(3.0)))
        c += (f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{PISTE}" stroke-width="6.5" stroke-linecap="round" '
              f'stroke-dasharray="{arc:.1f} {tour:.1f}" transform="rotate(135 {x} {y})"/>')
        note = a.get("note")
        if note is None:
            c += texte(x, y + 5, "—", 14, GRIS, True, "middle")
        else:
            longueur = max(arc * max(0.0, min(100.0, note)) / 100, 0.1)
            couleur = POSITIF if note >= passage else TENSION
            c += (f'<g transform="rotate(135 {x} {y})"><circle class="{f.cle([(0, "stroke-dasharray: 0.1 999;"), (t, "stroke-dasharray: 0.1 999;"), (t + 0.8, f"stroke-dasharray: {longueur:.1f} 999;"), (DUREE, f"stroke-dasharray: {longueur:.1f} 999;")])}" '
                  f'cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{couleur}" stroke-width="6.5" stroke-linecap="round" '
                  f'stroke-dasharray="{longueur:.1f} 999"/></g>'
                  + texte(x, y + 6, str(round(note)), 16, ENCRE, True, "middle", f.apparait(t + 0.3, dy=0)))
        c += texte(x, 134, a["nom"], 10.5, ENCRE, True, "middle")
    c += pastille(260, 204, verdict.get("libelle", ""), verdict.get("code", ""), f.apparait(3.7, dy=8, echelle=0.9), "middle", 15)
    c += texte(40, 252, "Explication", 12, ENCRE, True, classe=f.apparait(4.5))
    for k, largeur in enumerate((440, 404, 300)):
        c += (f'<rect class="{f.grandit(4.7 + k * 0.55, 5.3 + k * 0.55)}" x="40" y="{262 + k * 16}" width="{largeur}" '
              f'height="8" rx="4" fill="{FILET}"/>')
    c += texte(40, 332, "Pistes testées", 12, ENCRE, True, classe=f.apparait(6.8))
    for k in range(2):
        x = 40 + k * 166
        c += (f'<g class="{f.apparait(7.2 + k * 0.5, dx=-6, dy=0)}"><rect x="{x}" y="342" width="154" height="28" rx="14" fill="{VOILE}"/>'
              f'<circle cx="{x + 16}" cy="356" r="4.5" fill="{ACCENT}"/>'
              f'<rect x="{x + 28}" y="352" width="{104 - k * 22}" height="8" rx="4" fill="{BORD}"/></g>')
    return f.scene(c, titre="Cinq angles notés, l'angle déterminant, le verdict, l'explication et les pistes testées")


# ---------------------------------------------------------------- 5. à vous

def billet(nom: str, titre: str, operation: str, montant: str) -> tuple[str, str]:
    """Le billet d'ordre d'un compte, dessiné ; le pointeur va à « Analyser l'ordre » ; le verdict se fait attendre."""
    f = Film("fe")
    c = (carte(130, 22, 260, 356) + texte(150, 54, "Ordre", 14, ENCRE, True) + texte(370, 54, nom, 12, GRIS, False, "end")
         + champ(150, 76, 220, "Titre", titre, classe=f.apparait(0.3))
         + champ(150, 136, 220, "Opération", operation, classe=f.apparait(0.6))
         + champ(150, 196, 220, "Montant", montant, classe=f.apparait(0.9))
         + f'<circle class="{f.cle([(0, "opacity: 0; transform: scale(.3);"), (3.6, "opacity: 0; transform: scale(.3);"), (3.7, "opacity: .35; transform: scale(.5);"), (4.4, "opacity: 0; transform: scale(1.5);"), (DUREE, "opacity: 0;")])}" '
           f'cx="260" cy="282" r="70" fill="{ACCENT}"/>'
         + bouton(150, 262, 220, "Analyser l'ordre", f.appuie(3.7))
         + f'<g class="{f.bat(4.5)}"><rect x="216" y="322" width="88" height="34" rx="17" fill="{VOILE}" stroke="{BORD}" stroke-width="1.2"/>'
           + texte(260, 345, "?", 17, ENCRE, True, "middle") + "</g>"
         + f'<g class="{f.cle([(0, "transform: translate(150px, 70px);"), (1.4, "transform: translate(150px, 70px);"), (3.3, "transform: none;"), (DUREE, "transform: none;")])}">'
           f'<path d="M300 288 l0 22 l6 -5 l5 10 l5 -2.5 l-5 -10 l8 0 Z" fill="{ENCRE}" stroke="{BLANC}" stroke-width="1.6" stroke-linejoin="round"/></g>')
    return f.scene(c, titre=f"L'ordre de {nom} : {operation.lower()}, {montant} de {titre}. Le verdict reste à découvrir")
