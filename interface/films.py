"""Les images qui jouent de l'introduction : un film en cinq scènes, dessiné en SVG et animé par des images clés CSS.

Aucun fichier vidéo, aucun script, aucun lecteur. Chaque scène tourne seule, en boucle sans fin, sur une même
scène d'encre bleue : tout se joue sur une même durée, la dernière image est tenue, puis le dessin s'efface et
recommence (le fond, lui, ne bouge pas : la boucle n'a pas de couture). L'état de base de chaque élément est sa
place dans l'image finale : un visiteur qui préfère moins de mouvement voit cette image, immobile (la feuille de
style coupe alors toute animation).

Une seule grammaire pour les cinq scènes : mêmes épaisseurs de trait, mêmes rayons, mêmes tailles de lettres,
mêmes ombres, même courbe de temps. Seuls la position et l'opacité s'animent.
"""

from __future__ import annotations

import html
import math

from interface.theme import (ACCENT, ARRET, ARRET_PALE, BLANC, BLEU_CLAIR, BLEU_PALE, BORD, ENCRE, FILET, GRIS, PISTE,
                             POSITIF, POSITIF_PALE, TENSION, TENSION_PALE, VIOLET, VIOLET_TEXTE, VOILE)

DUREE = 10.0  # secondes ; la boucle complète
LARGEUR, HAUTEUR = 520, 440  # la scène

# Les valeurs propres aux films : la scène d'encre et ce qui s'y lit.
NUIT = "#0A1B30"          # le bord de la scène
NUIT_CLAIRE = "#173B64"   # son centre
CLAIR = "#B4C6DC"         # le texte secondaire, sur l'encre
CIEL = "#8FC2F5"          # le bleu des données, éclairci pour l'encre
LILAS = "#D5C7FB"         # le violet, éclairci pour l'encre
AMBRE = "#FFB937"         # l'ambre, éclairci pour l'encre
MENTHE = "#3FD9C1"        # le vert d'eau, éclairci pour l'encre
OMBRE = "#030A16"

DOUX = "cubic-bezier(.22, .8, .24, 1)"   # une arrivée : vive, puis posée
ALLER = "cubic-bezier(.65, 0, .35, 1)"   # un déplacement : il part et arrive en douceur

SIGNES = {"compatible": (POSITIF, POSITIF_PALE), "en_tension": (TENSION, TENSION_PALE), "incompatible": (ARRET, ARRET_PALE)}


def e(texte) -> str:
    return html.escape(str(texte if texte is not None else ""), quote=False)


class Film:
    """Fabrique les images clés d'un film et les classes qui les jouent."""

    def __init__(self, nom: str, duree: float = DUREE):
        self.nom, self.duree, self.regles, self.n = nom, duree, [], 0

    def _p(self, t: float) -> str:
        return f"{max(0.0, min(100.0, t / self.duree * 100)):.2f}%"

    def cle(self, etapes: list[tuple[float, str]], extra: str = "", courbe: str = DOUX) -> str:
        """Une animation en images clés : [(instant en secondes, propriétés CSS)]. Rend le nom de sa classe."""
        self.n += 1
        nom = f"{self.nom}{self.n}"
        corps = " ".join(f"{self._p(t)} {{ {props} }}" for t, props in etapes)
        self.regles.append(f"@keyframes {nom} {{ {corps} }}")
        self.regles.append(f".{nom} {{ animation: {nom} {self.duree}s {courbe} infinite both; "
                           f"transform-box: fill-box; transform-origin: center; {extra} }}")
        return nom

    def apparait(self, t: float, dx: float = 0, dy: float = 6, echelle: float = 1.0, duree: float = 0.4) -> str:
        """Caché jusqu'à t, puis en place jusqu'à la fin de la boucle."""
        cache = f"opacity: 0; transform: translate({dx}px, {dy}px) scale({echelle});"
        la = "opacity: 1; transform: none;"
        return self.cle([(0, cache), (t, cache), (t + duree, la), (self.duree, la)])

    def passe(self, t0: float, t1: float, fondu: float = 0.25) -> str:
        """Visible seulement entre t0 et t1 (un halo, un repère). Absent de l'image finale."""
        return self.cle([(0, "opacity: 0;"), (t0, "opacity: 0;"), (t0 + fondu, "opacity: 1;"), (t1, "opacity: 1;"),
                         (t1 + fondu, "opacity: 0;"), (self.duree, "opacity: 0;")], extra="opacity: 0;")

    def trace(self, t0: float, t1: float, longueur: float) -> str:
        """Un trait qui se dessine entre t0 et t1."""
        return self.cle([(0, f"stroke-dashoffset: {longueur};"), (t0, f"stroke-dashoffset: {longueur};"),
                         (t1, "stroke-dashoffset: 0;"), (self.duree, "stroke-dashoffset: 0;")],
                        extra=f"stroke-dasharray: {longueur};")

    def grandit(self, t0: float, t1: float, courbe: str = DOUX) -> str:
        """Une barre qui s'allonge depuis sa gauche."""
        return self.cle([(0, "transform: scaleX(0);"), (t0, "transform: scaleX(0);"), (t1, "transform: none;"),
                         (self.duree, "transform: none;")], extra="transform-origin: left center;", courbe=courbe)

    def glisse(self, t0: float, t1: float, dx: float, dy: float = 0) -> str:
        """Un élément qui vient à sa place depuis un décalage."""
        loin = f"transform: translate({dx}px, {dy}px);"
        return self.cle([(0, loin), (t0, loin), (t1, "transform: none;"), (self.duree, "transform: none;")], courbe=ALLER)

    def appuie(self, t: float) -> str:
        """Un bouton que l'on presse : il s'enfonce, puis revient. Sans rebond."""
        return self.cle([(0, "transform: none;"), (t - 0.12, "transform: none;"), (t, "transform: scale(0.95);"),
                         (t + 0.35, "transform: none;"), (self.duree, "transform: none;")])

    def onde(self, cx: float, cy: float, t: float, rayon: float = 60, couleur: str = ACCENT) -> str:
        """L'onde d'un appui : un disque qui s'élargit et s'éteint. Absent de l'image finale."""
        classe = self.cle([(0, "opacity: 0; transform: scale(.3);"), (t, "opacity: 0; transform: scale(.3);"),
                           (t + 0.08, "opacity: .4; transform: scale(.45);"), (t + 0.8, "opacity: 0; transform: scale(1.5);"),
                           (self.duree, "opacity: 0; transform: scale(1.5);")], extra="opacity: 0;")
        return f'<circle class="{classe}" cx="{cx}" cy="{cy}" r="{rayon}" fill="{couleur}"/>'

    def anneau(self, cx: float, cy: float, t: float, rayon: float, couleur: str) -> str:
        """Un anneau qui part d'un point et s'éteint : ce qui vient d'arriver. Absent de l'image finale."""
        classe = self.cle([(0, "opacity: 0; transform: scale(.6);"), (t, "opacity: 0; transform: scale(.6);"),
                           (t + 0.1, "opacity: .9; transform: scale(.7);"), (t + 0.9, "opacity: 0; transform: scale(1.7);"),
                           (self.duree, "opacity: 0; transform: scale(1.7);")], extra="opacity: 0;")
        return f'<circle class="{classe}" cx="{cx}" cy="{cy}" r="{rayon}" fill="none" stroke="{couleur}" stroke-width="2"/>'

    def bat(self, t0: float) -> str:
        """Une attente : l'élément apparaît à t0 puis bat doucement, sans jamais répondre."""
        etapes = [(0, "opacity: 0;"), (t0, "opacity: 0;"), (t0 + 0.3, "opacity: 1; transform: none;")]
        t = t0 + 0.3
        while t + 1.2 < self.duree - 0.2:
            etapes += [(t + 0.6, "opacity: .4; transform: scale(0.9);"), (t + 1.2, "opacity: 1; transform: none;")]
            t += 1.2
        etapes.append((self.duree, "opacity: 1; transform: none;"))
        return self.cle(etapes, courbe="ease-in-out")

    def tape(self, x: float, y: float, l: float, h: float, t0: float, t1: float, pas: int) -> str:
        """Un cache qui se retire lettre à lettre : la valeur d'un champ, tapée."""
        classe = self.cle([(0, "transform: none;"), (t0, "transform: none;"), (t1, "transform: scaleX(0);"),
                           (self.duree, "transform: scaleX(0);")],
                          extra="transform-origin: right center; transform: scaleX(0);", courbe=f"steps({max(pas, 1)}, end)")
        return f'<rect class="{classe}" x="{x}" y="{y}" width="{l}" height="{h}" fill="{BLANC}"/>'

    def course(self, pts: list[tuple[float, float]], t0: float, t1: float, couleur: str, tete: str = "plein",
               epaisseur: float = 3, pas: int = 10) -> str:
        """Une ligne qui avance le long d'une courbe, son point de tête sur sa pointe, du départ à l'arrivée."""
        n = 80
        pos = [_bezier(pts, i / n) for i in range(n + 1)]
        s = [0.0]
        for a, b in zip(pos, pos[1:]):
            s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        longueur, fin = s[-1], pts[3]
        trait = [(0, f"stroke-dashoffset: {longueur:.1f};")]
        point = [(0, f"opacity: 0; transform: translate({pts[0][0] - fin[0]:.1f}px, {pts[0][1] - fin[1]:.1f}px);"),
                 (t0 - 0.02, f"opacity: 0; transform: translate({pts[0][0] - fin[0]:.1f}px, {pts[0][1] - fin[1]:.1f}px);")]
        for i in range(pas + 1):
            u = i / pas
            k = round(u * u * (3 - 2 * u) * n)  # le départ et l'arrivée en douceur
            t = t0 + (t1 - t0) * u
            trait.append((t, f"stroke-dashoffset: {longueur - s[k]:.1f};"))
            point.append((t, f"opacity: 1; transform: translate({pos[k][0] - fin[0]:.1f}px, {pos[k][1] - fin[1]:.1f}px);"))
        trait.append((self.duree, "stroke-dashoffset: 0;"))
        point.append((self.duree, "opacity: 1; transform: none;"))
        ct = self.cle(trait, extra=f"stroke-dasharray: {longueur:.1f};", courbe="linear")
        cp = self.cle(point, courbe="linear")
        d = f"M{pts[0][0]} {pts[0][1]} C{pts[1][0]} {pts[1][1]} {pts[2][0]} {pts[2][1]} {pts[3][0]} {pts[3][1]}"
        if tete == "anneau":
            marque = f'<circle cx="{fin[0]}" cy="{fin[1]}" r="6" fill="{NUIT}" stroke="{couleur}" stroke-width="3"/>'
        else:
            marque = f'<circle cx="{fin[0]}" cy="{fin[1]}" r="6.5" fill="{couleur}"/>'
        return (f'<path class="{ct}" d="{d}" fill="none" stroke="{couleur}" stroke-width="{epaisseur + 9}" stroke-linecap="round" opacity=".16"/>'
                f'<path class="{ct}" d="{d}" fill="none" stroke="{couleur}" stroke-width="{epaisseur}" stroke-linecap="round"/>'
                f'<g class="{cp}"><circle cx="{fin[0]}" cy="{fin[1]}" r="13" fill="{couleur}" opacity=".22"/>{marque}</g>')

    @property
    def fondu(self) -> str:
        """La classe de ce qui s'efface à la fin de la boucle : l'histoire. Le décor, lui, reste en place."""
        return f"{self.nom}0"

    def fin(self, contenu: str) -> str:
        """L'histoire : elle s'efface juste avant que la boucle recommence, sur un décor qui ne bouge pas."""
        return f'<g class="{self.fondu}">{contenu}</g>'

    def scene(self, contenu: str, titre: str = "") -> tuple[str, str]:
        """Le film : sa feuille d'images clés, et son dessin. Aucune image vide : le décor reste, l'histoire seule
        s'efface (voir fin) et reprend aussitôt."""
        d = self.duree
        self.regles.append(f"@keyframes {self.nom}0 {{ 0% {{ opacity: 1; }} {self._p(d - 0.6)} {{ opacity: 1; }} {self._p(d - 0.28)} {{ opacity: 0; }} 100% {{ opacity: 0; }} }}")
        self.regles.append(f".{self.nom}0 {{ animation: {self.nom}0 {d}s linear infinite both; }}")
        self.regles.append("svg.film .fo { filter: drop-shadow(0 12px 20px rgba(2, 8, 20, .42)); }")
        style = "<style>" + " ".join(self.regles) + "</style>"
        fond = (f'<defs><radialGradient id="fl-scene" gradientUnits="userSpaceOnUse" cx="260" cy="190" r="430">'
                f'<stop offset="0" stop-color="{NUIT_CLAIRE}"/><stop offset="1" stop-color="{NUIT}"/></radialGradient>'
                f'<linearGradient id="fl-lueur" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3D97EC"/>'
                f'<stop offset="1" stop-color="{VIOLET}"/></linearGradient>'
                f'<radialGradient id="fl-halo"><stop offset="0" stop-color="{VIOLET}" stop-opacity=".8"/>'
                f'<stop offset=".6" stop-color="#4C8FE6" stop-opacity=".42"/><stop offset="1" stop-color="#3D97EC" stop-opacity="0"/></radialGradient>'
                f'<pattern id="fl-grain" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="{BLANC}" opacity=".055"/></pattern></defs>'
                f'<rect x="-1500" y="-1500" width="3520" height="3440" fill="url(#fl-scene)"/>'
                f'<rect x="-1500" y="-1500" width="3520" height="3440" fill="url(#fl-grain)"/>')
        dessin = (f'<svg class="film" viewBox="0 0 {LARGEUR} {HAUTEUR}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="{e(titre)}">{fond}'
                  f'{contenu}</svg>')
        return style, dessin


def _bezier(p: list[tuple[float, float]], u: float) -> tuple[float, float]:
    a = 1 - u
    return tuple(a ** 3 * p[0][k] + 3 * a * a * u * p[1][k] + 3 * a * u * u * p[2][k] + u ** 3 * p[3][k] for k in (0, 1))


# ---------------------------------------------------------------- pièces de dessin

def carte(x: float, y: float, l: float, h: float, classe: str = "", rayon: float = 16) -> str:
    return f'<rect class="fo {classe}" x="{x}" y="{y}" width="{l}" height="{h}" rx="{rayon}" fill="{BLANC}"/>'


def halo(cx: float, cy: float, rx: float, ry: float, classe: str = "") -> str:
    """La lueur de ce que Sigma ajoute : du bleu vers le violet, derrière une carte."""
    return f'<ellipse class="{classe}" cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="url(#fl-halo)"/>'


def texte(x: float, y: float, contenu: str, taille: float = 12, couleur: str = ENCRE, gras: bool = False,
          ancre: str = "start", classe: str = "") -> str:
    return (f'<text class="{classe}" x="{x}" y="{y}" font-size="{taille}" fill="{couleur}" text-anchor="{ancre}" '
            f'font-weight="{700 if gras else 500}">{e(contenu)}</text>')


def signe(x: float, y: float, code: str, taille: float = 4.5, couleur: str | None = None) -> str:
    """Le signe d'un verdict : un point plein, un anneau ou un carré."""
    couleur = couleur or SIGNES.get(code, (GRIS, VOILE))[0]
    if code == "en_tension":
        return f'<circle cx="{x}" cy="{y}" r="{taille - 1}" fill="none" stroke="{couleur}" stroke-width="2.4"/>'
    if code == "incompatible":
        return f'<rect x="{x - taille}" y="{y - taille}" width="{taille * 2}" height="{taille * 2}" rx="1.5" fill="{couleur}"/>'
    return f'<circle cx="{x}" cy="{y}" r="{taille}" fill="{couleur}"/>'


def pastille(x: float, y: float, libelle: str, code: str, classe: str = "", ancre: str = "start",
             taille: float = 12) -> str:
    """Une pastille de verdict : son signe, son mot. x est son bord gauche, son centre ou son bord droit."""
    largeur = len(libelle) * taille * 0.6 + 38
    gauche = x if ancre == "start" else (x - largeur / 2 if ancre == "middle" else x - largeur)
    fond = SIGNES.get(code, (GRIS, VOILE))[1]
    h = taille + 14
    return (f'<g class="{classe}"><rect class="fo" x="{gauche}" y="{y - h / 2}" width="{largeur}" height="{h}" rx="{h / 2}" '
            f'fill="{fond}"/>{signe(gauche + 15, y, code, taille * 0.38)}'
            f'{texte(gauche + 27, y + taille * 0.36, libelle, taille, ENCRE, True)}</g>')


def champ(x: float, y: float, l: float, etiquette: str, valeur: str, classe_halo: str = "", classe: str = "",
          cache: str = "", classe_valeur: str = "") -> str:
    """Un champ dessiné : son étiquette, son cadre, sa valeur, et le halo qui dit qu'on y est."""
    lueur = (f'<rect class="{classe_halo}" x="{x - 2.5}" y="{y + 5.5}" width="{l + 5}" height="41" rx="11" fill="none" '
             f'stroke="url(#fl-lueur)" stroke-width="2.4"/>' if classe_halo else "")
    return (f'<g class="{classe}">{texte(x, y, etiquette, 11.5, GRIS)}'
            f'<rect x="{x}" y="{y + 8}" width="{l}" height="36" rx="9" fill="{BLANC}" stroke="{BORD}" stroke-width="1.2"/>'
            f'{texte(x + 13, y + 31, valeur, 14, ENCRE, True, classe=classe_valeur)}{cache}{lueur}</g>')


def bouton(x: float, y: float, l: float, libelle: str, classe: str = "", classe_lueur: str = "") -> str:
    """Le bouton de l'action ; sa lueur, du bleu vers le violet, dit que l'analyse est partie."""
    lueur = (f'<rect class="{classe_lueur}" x="{x - 4}" y="{y - 4}" width="{l + 8}" height="50" rx="25" fill="none" '
             f'stroke="url(#fl-lueur)" stroke-width="2.4"/>' if classe_lueur else "")
    return (f'<g class="{classe}">{lueur}<rect x="{x}" y="{y}" width="{l}" height="42" rx="21" fill="{ACCENT}"/>'
            f'{texte(x + l / 2, y + 26, libelle, 13.5, BLANC, True, "middle")}</g>')


def pointeur(x: float, y: float, classe: str = "") -> str:
    """Le pointeur, sa pointe en (x, y)."""
    return (f'<g class="{classe}"><path class="fo" d="M{x} {y} l0 23 l6.5 -5.5 l5 10.5 l5 -2.5 l-5 -10.5 l8.5 0 Z" fill="{ENCRE}" '
            f'stroke="{BLANC}" stroke-width="1.8" stroke-linejoin="round"/></g>')


def jeton(x: float, y: float, genre: str, classe: str = "") -> str:
    """Un agent : un nœud violet, marqué. Le principal : un point dans son anneau. L'explorateur : trois points reliés."""
    if genre == "principal":
        marque = (f'<circle cx="{x}" cy="{y}" r="5.6" fill="none" stroke="{BLANC}" stroke-width="1.8"/>'
                  f'<circle cx="{x}" cy="{y}" r="2.1" fill="{BLANC}"/>')
    else:
        sommets = [(x - 5, y + 3.8), (x, y - 5), (x + 5, y + 3.8)]
        marque = (f'<path d="M{sommets[0][0]} {sommets[0][1]} L{sommets[1][0]} {sommets[1][1]} L{sommets[2][0]} {sommets[2][1]}" fill="none" '
                  f'stroke="{BLANC}" stroke-width="1.4" stroke-linejoin="round"/>'
                  + "".join(f'<circle cx="{a}" cy="{b}" r="2.2" fill="{BLANC}"/>' for a, b in sommets))
    return f'<g class="{classe}"><circle class="fo" cx="{x}" cy="{y}" r="13" fill="{VIOLET}"/>{marque}</g>'


def zone(x: float, y: float, l: float, h: float, classe: str = "") -> str:
    """La zone de la politique de placement : une bande claire, sur l'encre."""
    return (f'<rect class="{classe}" x="{x}" y="{y}" width="{l}" height="{h}" rx="{h / 2}" fill="{BLEU_CLAIR}" fill-opacity=".20" '
            f'stroke="{BLEU_CLAIR}" stroke-opacity=".45" stroke-width="1.2"/>')


# ---------------------------------------------------------------- 1. l'écart

def ecart() -> tuple[str, str]:
    """Le cours suit la zone de la politique de placement ; un ordre arrive, la ligne s'en écarte, l'écart est mesuré."""
    f = Film("fa", 6.8)
    decor = (zone(20, 236, 448, 80) + texte(48, 222, "Votre politique de placement", 13.5, CLAIR)
             + f'<circle cx="486" cy="276" r="17" fill="none" stroke="{BLANC}" stroke-width="2.4"/>'
               f'<circle cx="486" cy="276" r="6" fill="{BLANC}"/>'
             + texte(506, 348, "Vos objectifs", 14, BLANC, True, "end"))
    c = (f'<path class="{f.apparait(1.95, dy=0, duree=0.6)}" d="M250 276 C320 266 390 284 464 276" fill="none" stroke="{CLAIR}" stroke-width="2.2" stroke-dasharray="1 8" stroke-linecap="round"/>'
         + texte(358, 302, "il reste dans votre politique", 12.5, CLAIR, False, "middle", f.apparait(2.3))
         + f.course([(46, 288), (112, 258), (172, 298), (250, 276)], 0.2, 1.6, BLANC)
         + f.anneau(250, 276, 1.55, 15, BLANC)
         + texte(250, 348, "Un ordre", 14, BLANC, True, "middle", f.apparait(1.6))
         + f'<line class="{f.apparait(1.6, dy=0)}" x1="250" y1="293" x2="250" y2="330" stroke="{CLAIR}" stroke-width="1.2" stroke-dasharray="2 4"/>'
         + f.course([(250, 276), (304, 254), (352, 170), (400, 92)], 2.7, 4.0, AMBRE)
         + texte(300, 168, "il vous en écarte", 12.5, CLAIR, False, "end", f.apparait(3.5))
         + f'<g class="{f.apparait(3.95, dy=0)}"><path d="M400 112 V228 M392 112 H408 M392 228 H408" fill="none" stroke="{BLANC}" stroke-width="1.8" stroke-linecap="round"/></g>'
         + texte(415, 175, "l'écart,", 13, BLANC, True, classe=f.apparait(4.25, dx=-6, dy=0))
         + texte(415, 192, "mesuré", 13, BLANC, True, classe=f.apparait(4.35, dx=-6, dy=0)))
    # L'écart mesuré devient une note : le même cadran que dans les scènes 3 et 4, sans chiffre, à son niveau.
    rj = 13.0
    tourj = 2 * math.pi * rj
    arcj = 0.75 * tourj
    vide, pleine = "stroke-dasharray: 0.1 999;", f"stroke-dasharray: {arcj * 0.32:.1f} 999;"
    c += (f'<g class="{f.apparait(4.5, dy=0, echelle=0.8)}">'
          f'<circle cx="430" cy="141" r="{rj}" fill="none" stroke="{BLANC}" stroke-opacity=".16" stroke-width="5" stroke-linecap="round" '
          f'stroke-dasharray="{arcj:.1f} {tourj:.1f}" transform="rotate(135 430 141)"/>'
          f'<g transform="rotate(135 430 141)"><circle class="{f.cle([(0, vide), (4.65, vide), (5.3, pleine), (f.duree, pleine)])}" '
          f'cx="430" cy="141" r="{rj}" fill="none" stroke="{AMBRE}" stroke-width="5" stroke-linecap="round" stroke-dasharray="{arcj * 0.32:.1f} 999"/></g>'
          + texte(451, 145.5, "note", 12.5, CLAIR, True) + "</g>")
    return f.scene(decor + f.fin(c),
                   titre="Un ordre peut rester dans votre politique de placement ou s'en écarter : l'écart est mesuré")


# ---------------------------------------------------------------- 2. la fiche devient une politique de placement

def fiche() -> tuple[str, str]:
    """Un questionnaire simple se remplit, coche après coche ; il se range, et il en sort un document plus riche :
    la politique de placement, des articles, chacun une limite. À la fin, la fiche revient au centre, vide."""
    f = Film("fb", 7.6)
    d = f.duree
    questions = [("Objectif", 0), ("Horizon", 1), ("Risque", 1)]
    instants = [0.3, 0.9, 1.5]
    avance = f.cle([(0, "transform: scaleX(0);"), (instants[0], "transform: scaleX(0);"), (instants[0] + 0.4, "transform: scaleX(.333);"),
                    (instants[1], "transform: scaleX(.333);"), (instants[1] + 0.4, "transform: scaleX(.667);"),
                    (instants[2], "transform: scaleX(.667);"), (instants[2] + 0.4, "transform: none;"), (d, "transform: none;")],
                   extra="transform-origin: left center;")
    q = (carte(20, 96, 180, 248) + texte(38, 127, "Votre fiche", 14, ENCRE, True)
         + f'<rect x="38" y="139" width="144" height="4" rx="2" fill="{PISTE}"/>')
    coches = f'<rect class="{avance}" x="38" y="139" width="144" height="4" rx="2" fill="{ACCENT}"/>'
    for i, (nom, choix) in enumerate(questions):
        y, t = 172 + i * 58, instants[i]
        q += (f'<rect class="{f.passe(max(t - 0.3, 0.02), t + 0.35, 0.2)}" x="29" y="{y - 15}" width="162" height="54" rx="10" fill="{BLEU_PALE}"/>'
              + texte(38, y, nom, 11.5, GRIS))
        for k in range(3):
            q += f'<rect x="{38 + k * 50}" y="{y + 8}" width="44" height="24" rx="12" fill="{VOILE}" stroke="{FILET}" stroke-width="1"/>'
        x = 38 + choix * 50
        coches += (f'<rect class="{f.apparait(t, dy=0, echelle=0.6, duree=0.3)}" x="{x}" y="{y + 8}" width="44" height="24" rx="12" fill="{ACCENT}"/>'
                   f'<path class="{f.trace(t + 0.18, t + 0.5, 21)}" d="M{x + 15} {y + 20} l5 5 l9 -10" fill="none" stroke="{BLANC}" '
                   f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
    au_centre, rangee = "transform: translate(150px, 0px) scale(1.24); opacity: 1;", "transform: none; opacity: .78;"
    q = f'<g class="{f.cle([(0, au_centre), (2.0, au_centre), (2.8, rangee), (d - 0.36, rangee), (d, au_centre)], extra="opacity: .78;", courbe=ALLER)}">{q}{f.fin(coches)}</g>'
    lien = (f'<path class="{f.apparait(2.75, dx=-8, dy=0)}" d="M208 220 H228 M222 213 l7 7 l-7 7" fill="none" stroke="{CIEL}" '
            f'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
    doc = (carte(240, 30, 260, 380)
           + '<circle cx="266" cy="62" r="14" fill="url(#fl-lueur)"/>' + texte(266, 67.5, "σ", 16, BLANC, True, "middle")
           + texte(290, 67, "Politique de placement", 14, ENCRE, True)
           + f'<line x1="258" y1="88" x2="482" y2="88" stroke="{FILET}" stroke-width="1.2"/>')
    articles = [("Profil d'investisseur", None, None, 2), ("Répartition", 52, 92, 124), ("Limites de risque", 0, 112, 74),
                ("Concentration", 0, 78, 40)]
    for j, (nom, debut, largeur, repere) in enumerate(articles):
        y, t = 122 + j * 78, 2.95 + j * 0.45
        bloc = texte(258, y, f"{j + 1:02d}", 11, VIOLET_TEXTE, True) + texte(282, y, nom, 13, ENCRE, True)
        if debut is None:  # le profil : une échelle à cinq degrés, l'un retenu
            for k in range(5):
                bloc += f'<rect x="{282 + k * 41}" y="{y + 13}" width="36" height="10" rx="5" fill="{PISTE}"/>'
            bloc += (f'<rect class="{f.apparait(t + 0.25, dy=0, echelle=0.5, duree=0.3)}" x="{282 + repere * 41}" y="{y + 13}" '
                     f'width="36" height="10" rx="5" fill="{ACCENT}"/>')
        else:  # une limite : sa piste, sa zone permise, son repère
            bloc += (f'<rect x="282" y="{y + 14}" width="200" height="8" rx="4" fill="{PISTE}"/>'
                     f'<rect class="{f.grandit(t + 0.15, t + 0.65)}" x="{282 + debut}" y="{y + 14}" width="{largeur}" height="8" rx="4" fill="{BLEU_CLAIR}"/>'
                     f'<circle class="{f.glisse(t + 0.2, t + 0.8, -repere)}" cx="{282 + repere}" cy="{y + 18}" r="6.5" fill="{ENCRE}" stroke="{BLANC}" stroke-width="2.4"/>')
        bloc += f'<rect x="282" y="{y + 34}" width="{150 - j * 18}" height="5" rx="2.5" fill="{FILET}"/>'
        doc += f'<g class="{f.apparait(t)}">{bloc}</g>'
    doc += (f'<rect class="{f.apparait(4.95, dy=0, duree=0.7)}" x="240" y="30" width="260" height="380" rx="16" fill="none" '
            f'stroke="url(#fl-lueur)" stroke-width="2.6"/>')
    de_la_fiche = "opacity: 0; transform: translate(-120px, 0px) scale(.62);"
    doc = f'<g class="{f.cle([(0, de_la_fiche), (2.15, de_la_fiche), (3.0, "opacity: 1; transform: none;"), (d, "opacity: 1; transform: none;")], courbe=ALLER)}">{doc}</g>'
    lueur = halo(370, 220, 215, 250, f.apparait(4.8, dy=0, duree=0.9))
    return f.scene(f.fin(lueur) + q + f.fin(lien + doc), titre="Une fiche simple devient une politique de placement, faite de limites")


# ---------------------------------------------------------------- 3. l'ordre, mis à l'épreuve

def epreuve(ticker: str, montant: str) -> tuple[str, str]:
    """Un billet d'ordre dessiné se remplit, le regard suit le champ en jeu, on presse « Analyser l'ordre », puis le
    champ s'élargit : trois issues, lues sur la zone de la politique. Le point y reste, en sort, ou, parti de
    dehors, s'en rapproche."""
    f = Film("fc", 7.8)
    d = f.duree
    loin = "opacity: 0; transform: translate(90px, 70px);"
    billet = (carte(20, 60, 212, 320) + texte(40, 93, "Ordre", 15, ENCRE, True)
              + champ(40, 116, 172, "Titre", ticker, f.passe(0.1, 0.8, 0.2), classe_valeur=f.fondu,
                      cache=f.tape(50, 127, 158, 30, 0.2, 0.6, max(len(str(ticker)), 1)))
              + champ(40, 190, 172, "Montant", montant, f.passe(1.0, 1.75, 0.2), classe_valeur=f.fondu,
                      cache=f.tape(50, 201, 158, 30, 1.15, 1.6, max(len(str(montant)), 1)))
              + f.onde(126, 311, 2.3, 70)
              + bouton(40, 290, 172, "Analyser l'ordre", f.appuie(2.3), f.passe(2.45, d - 0.9, 0.3))
              + f.fin(pointeur(184, 320, f.cle([(0, loin), (1.55, loin), (2.15, "opacity: 1; transform: none;"),
                                                (d, "opacity: 1; transform: none;")], courbe=ALLER))))
    # Chaque issue : sa zone, la course du point, et, à droite, sa note : un cadran sans chiffre qui se remplit à son niveau.
    issues = [("Il y reste", "compatible", MENTHE, "plein", [(0, 0), (46, -13), (94, 13), (150, 0)], 0.88),
              ("Il en sort", "en_tension", AMBRE, "anneau", [(0, 0), (56, 0), (96, -8), (150, -46)], 0.32),
              ("Il s'en rapproche", "", CIEL, "plein", [(0, 46), (56, 46), (96, 40), (150, 20)], 0.6)]
    rj = 13.0
    tourj = 2 * math.pi * rj
    arcj = 0.75 * tourj
    droite = ""
    for i, (legende, code, couleur, tete, pts, niveau) in enumerate(issues):
        y, t = 60 + i * 116, 3.0 + i * 0.85
        m = y + 50
        marque = (signe(269, y + 8, code, 5, couleur) if code else
                  f'<path d="M264 {y + 12} l5 -8 l5 8" fill="none" stroke="{couleur}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>')
        lj = arcj * niveau
        vide, pleine = "stroke-dasharray: 0.1 999;", f"stroke-dasharray: {lj:.1f} 999;"
        note = (f'<circle cx="476" cy="{m}" r="{rj}" fill="none" stroke="{BLANC}" stroke-opacity=".16" stroke-width="5" stroke-linecap="round" '
                f'stroke-dasharray="{arcj:.1f} {tourj:.1f}" transform="rotate(135 476 {m})"/>'
                f'<g transform="rotate(135 476 {m})"><circle class="{f.cle([(0, vide), (t + 0.6, vide), (t + 1.3, pleine), (d, pleine)])}" '
                f'cx="476" cy="{m}" r="{rj}" fill="none" stroke="{couleur}" stroke-width="5" stroke-linecap="round" stroke-dasharray="{lj:.1f} 999"/></g>'
                + texte(476, m + 33, "note", 12.5, CLAIR, True, "middle"))
        droite += (f'<g class="{f.apparait(t)}">{marque}' + texte(282, y + 12.5, legende, 13, BLANC, True)
                   + zone(262, m - 20, 190, 40) + note
                   + f'<circle cx="{282 + pts[0][0]}" cy="{m + pts[0][1]}" r="3.5" fill="none" stroke="{CLAIR}" stroke-width="1.6"/></g>'
                   + f.course([(282 + dx, m + dy) for dx, dy in pts], t + 0.25, t + 1.1, couleur, tete))
    regards = ["transform: translate(134px, 44px) scale(1.24);", "transform: translate(134px, 6px) scale(1.24);",
               "transform: translate(134px, -46px) scale(1.24);"]
    camera = f.cle([(0, regards[0]), (0.75, regards[0]), (1.1, regards[1]), (1.7, regards[1]), (2.05, regards[2]),
                    (2.55, regards[2]), (3.25, "transform: none;"), (d - 0.36, "transform: none;"), (d, regards[0])],
                   extra="transform-box: view-box; transform-origin: 126px 220px;", courbe=ALLER)
    return f.scene(f'<g class="{camera}">{billet}{f.fin(droite)}</g>',
                   titre="Un ordre est analysé avant d'être passé : il reste dans la politique, en sort, ou s'en rapproche")


# ---------------------------------------------------------------- 4. cinq angles, un verdict, et le pourquoi

def resultat(angles: list[dict], verdict: dict, passage: float) -> tuple[str, str]:
    """Les cadrans se remplissent un à un, le plus bas s'allume : l'angle déterminant. Le verdict tombe,
    l'explication s'écrit, deux pistes testées paraissent. angles : {nom, note, decide}."""
    f = Film("fd", 8.6)
    d = f.duree
    n = max(len(angles), 1)
    pas = 480 / n
    r = min(29.0, pas / 2 - 14)
    tour = 2 * math.pi * r
    arc = 0.75 * tour
    decor, c, fond = "", "", ""
    # Quand l'angle déterminant s'allume, les autres cadrans s'effacent un instant : un seul regard à la fois.
    retrait = (f.cle([(0, "opacity: 1;"), (1.8, "opacity: 1;"), (2.15, "opacity: .38;"), (2.55, "opacity: .38;"),
                      (3.05, "opacity: 1;"), (d, "opacity: 1;")], courbe=ALLER)
               if any(a.get("decide") for a in angles) else "")
    for i, a in enumerate(angles):
        x, y, t = 20 + pas * (i + 0.5), 88, 0.1 + i * 0.22
        pose, joue = "", ""
        if a.get("decide"):
            fond += (f'<rect class="{f.apparait(1.8, dy=0, echelle=0.92, duree=0.5)}" x="{x - pas / 2 + 4}" y="30" width="{pas - 8}" height="152" rx="14" '
                     f'fill="{VIOLET}" fill-opacity=".34" stroke="{LILAS}" stroke-opacity=".7" stroke-width="1.4"/>')
            joue += (f.anneau(x, y, 1.85, r + 6, LILAS)
                     + texte(x, 160, "Angle", 10.5, LILAS, True, "middle", f.apparait(1.95))
                     + texte(x, 173, "déterminant", 10.5, LILAS, True, "middle", f.apparait(1.95)))
        pose += (f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{BLANC}" stroke-opacity=".14" stroke-width="7" stroke-linecap="round" '
                 f'stroke-dasharray="{arc:.1f} {tour:.1f}" transform="rotate(135 {x} {y})"/>'
                 + texte(x, 140, a["nom"], 10.5, BLANC if a.get("decide") else CLAIR, True, "middle"))
        note = a.get("note")
        if note is None:
            pose += texte(x, y + 6, "—", 15, CLAIR, True, "middle")
        else:
            longueur = max(arc * max(0.0, min(100.0, note)) / 100, 0.1)
            couleur = MENTHE if note >= passage else AMBRE
            joue += (f'<g transform="rotate(135 {x} {y})"><circle class="{f.cle([(0, "stroke-dasharray: 0.1 999;"), (t, "stroke-dasharray: 0.1 999;"), (t + 0.9, f"stroke-dasharray: {longueur:.1f} 999;"), (d, f"stroke-dasharray: {longueur:.1f} 999;")])}" '
                     f'cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{couleur}" stroke-width="7" stroke-linecap="round" '
                     f'stroke-dasharray="{longueur:.1f} 999"/></g>'
                     + texte(x, y + 6.5, str(round(note)), 18, BLANC, True, "middle", f.apparait(t + 0.3, dy=0)))
        seul = "" if a.get("decide") else retrait
        decor += f'<g class="{seul}">{pose}</g>'
        c += f'<g class="{seul}">{joue}</g>'
    # Les cadrans jouent d'abord au centre de la scène, un peu plus grands ; ils montent à leur place quand le verdict tombe.
    au_centre = "transform: translate(0px, 112px) scale(1.1);"
    regard = f.cle([(0, au_centre), (2.3, au_centre), (2.95, "transform: none;"), (d - 0.36, "transform: none;"), (d, au_centre)],
                   extra="transform-box: view-box; transform-origin: 260px 100px;", courbe=ALLER)
    cadrans = f'<g class="{regard}">{f.fin(fond)}{decor}{f.fin(c)}</g>'
    c = ""
    code = verdict.get("code", "")
    teinte = SIGNES.get(code, (GRIS, VOILE))[0]
    tombe = f.cle([(0, "opacity: 0; transform: scale(1.4);"), (2.75, "opacity: 0; transform: scale(1.4);"),
                   (3.15, "opacity: 1; transform: none;"), (d, "opacity: 1; transform: none;")])
    c += (f'<defs><radialGradient id="fd-v"><stop offset="0" stop-color="{teinte}" stop-opacity=".55"/>'
          f'<stop offset="1" stop-color="{teinte}" stop-opacity="0"/></radialGradient></defs>'
          f'<ellipse class="{f.apparait(2.8, dy=0, duree=0.7)}" cx="260" cy="222" rx="150" ry="44" fill="url(#fd-v)"/>'
          + f.anneau(260, 222, 3.05, 26, teinte)
          + pastille(260, 222, verdict.get("libelle", ""), code, tombe, "middle", 16))
    # L'équipe d'agents. L'agent principal écrit l'explication : les lignes partent de lui. Il passe le mandat à
    # l'agent explorateur, qui lance des essais : certains sont refusés, deux sont gardés (les pistes testées), puis il rend compte.
    bas = (carte(20, 262, 480, 158)
           + f.anneau(46, 290, 3.5, 15, VIOLET) + jeton(46, 290, "principal", f.apparait(3.4, dy=0, echelle=0.5, duree=0.3))
           + texte(68, 288.5, "Agent principal", 12.5, VIOLET_TEXTE, True, classe=f.apparait(3.5, dx=-6, dy=0))
           + texte(480, 288.5, "Explication", 12.5, ENCRE, True, "end", f.apparait(3.6, dy=0)))
    for k, largeur in enumerate((412, 384, 262)):
        t0, t1 = 3.7 + k * 0.45, 4.2 + k * 0.45
        plume = f.cle([(0, f"opacity: 0; transform: translate({-largeur}px, 0px);"), (t0 - 0.02, f"opacity: 0; transform: translate({-largeur}px, 0px);"),
                       (t0, f"opacity: 1; transform: translate({-largeur}px, 0px);"), (t1, "opacity: 1; transform: none;"),
                       (t1 + 0.15, "opacity: 0; transform: none;"), (d, "opacity: 0; transform: none;")],
                      extra="opacity: 0;", courbe="linear")
        bas += (f'<rect class="{f.grandit(t0, t1, "linear")}" x="68" y="{297 + k * 13}" width="{largeur}" height="6" rx="3" fill="{BORD}"/>'
                f'<rect class="{plume}" x="{68 + largeur}" y="{294 + k * 13}" width="2.4" height="12" rx="1.2" fill="{VIOLET}"/>')
    haut, en_bas = "transform: translate(0px, -40px);", "transform: none;"
    passage = f.cle([(0, f"opacity: 0; {haut}"), (4.98, f"opacity: 0; {haut}"), (5.0, f"opacity: 1; {haut}"), (5.4, f"opacity: 1; {en_bas}"),
                     (5.55, f"opacity: 0; {en_bas}"), (6.98, f"opacity: 0; {en_bas}"), (7.0, f"opacity: 1; {en_bas}"),
                     (7.4, f"opacity: 1; {haut}"), (7.55, f"opacity: 0; {haut}"), (d, f"opacity: 0; {haut}")],
                    extra="opacity: 0;", courbe=ALLER)
    bas += (f'<line class="{f.apparait(4.9, dy=0, duree=0.3)}" x1="46" y1="306" x2="46" y2="348" stroke="{VIOLET}" stroke-opacity=".55" '
            f'stroke-width="1.6" stroke-dasharray="2 4" stroke-linecap="round"/>'
            f'<circle class="{passage}" cx="46" cy="347" r="3.4" fill="{VIOLET}"/>'
            + f.anneau(46, 364, 5.4, 15, VIOLET) + jeton(46, 364, "explorateur", f.apparait(5.3, dy=0, echelle=0.5, duree=0.3))
            + texte(68, 362.5, "Agent explorateur", 12.5, VIOLET_TEXTE, True, classe=f.apparait(5.4, dx=-6, dy=0))
            + texte(480, 362.5, "Pistes testées", 12.5, ENCRE, True, "end", f.apparait(6.4, dy=0)))
    for k in range(4):
        x, y, ts, tr = 68 + k * 104, 372, 5.55 + k * 0.15, 6.2 + k * 0.2
        essai = (f'<rect x="{x}" y="{y}" width="96" height="26" rx="13" fill="{VOILE}" stroke="{FILET}" stroke-width="1"/>'
                 f'<circle cx="{x + 15}" cy="{y + 13}" r="3.6" fill="none" stroke="{BORD}" stroke-width="1.6"/>'
                 f'<rect x="{x + 28}" y="{y + 10}" width="{54 - (k % 2) * 10}" height="6" rx="3" fill="{BORD}"/>')
        if k in (1, 3):  # gardé : il devient une piste testée
            essai += (f'<g class="{f.apparait(tr, dy=0, duree=0.3)}"><rect x="{x}" y="{y}" width="96" height="26" rx="13" fill="{POSITIF_PALE}" '
                      f'stroke="{POSITIF}" stroke-opacity=".55" stroke-width="1.2"/>'
                      f'<path d="M{x + 10} {y + 13} l4 4 l7 -8" fill="none" stroke="{POSITIF}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
                      f'<rect x="{x + 28}" y="{y + 10}" width="{54 - (k % 2) * 10}" height="6" rx="3" fill="{POSITIF}" fill-opacity=".38"/></g>')
            enveloppe = ""
        else:  # refusé : il s'efface, marqué d'une croix
            essai += (f'<g class="{f.apparait(tr, dy=0, duree=0.3)}"><circle cx="{x + 15}" cy="{y + 13}" r="6" fill="{VOILE}"/>'
                      f'<path d="M{x + 11} {y + 9} l8 8 M{x + 19} {y + 9} l-8 8" fill="none" stroke="{ARRET}" stroke-width="2" stroke-linecap="round"/></g>')
            enveloppe = f.cle([(0, "opacity: 1;"), (tr + 0.1, "opacity: 1;"), (tr + 0.5, "opacity: .5;"), (d, "opacity: .5;")], extra="opacity: .5;")
        bas += f'<g class="{enveloppe}"><g class="{f.apparait(ts, dx=-(26 + k * 14), dy=0, echelle=0.85, duree=0.35)}">{essai}</g></g>'
    c += f'<g class="{f.apparait(3.1, dy=16, duree=0.5)}">{bas}</g>'
    return f.scene(cadrans + f.fin(c), titre="Cinq angles notés, l'angle déterminant, le verdict, l'explication et les pistes testées")


# ---------------------------------------------------------------- 5. à vous

def billet(nom: str, titre: str, operation: str, montant: str) -> tuple[str, str]:
    """Le billet d'ordre d'un compte, dessiné ; il se remplit, le pointeur va à « Analyser l'ordre », l'appui part ;
    le verdict se fait attendre : un point d'interrogation qui bat, et ne répond jamais."""
    f = Film("fe", 6.6)
    d = f.duree
    tourne = f.cle([(0, "transform: rotate(0deg);"), (2.4, "transform: rotate(0deg);"), (d, "transform: rotate(900deg);")],
                   extra="transform-box: view-box; transform-origin: 260px 364px;", courbe="linear")
    loin = "opacity: 0; transform: translate(140px, 84px);"
    c = (f.fin(halo(260, 230, 250, 260, f.apparait(2.2, dy=0, duree=0.9)))
         + carte(120, 24, 280, 392) + texte(142, 59, "Ordre", 15, ENCRE, True) + texte(378, 59, nom, 12, GRIS, False, "end")
         + champ(142, 80, 236, "Titre", titre, classe_valeur=f.fondu,
                 cache=f.tape(152, 91, 222, 30, 0.15, 0.55, max(len(str(titre)), 1)))
         + champ(142, 144, 236, "Opération", operation, classe_valeur=f.fondu,
                 cache=f.tape(152, 155, 222, 30, 0.55, 0.85, max(len(str(operation)), 1)))
         + champ(142, 208, 236, "Montant", montant, classe_valeur=f.fondu,
                 cache=f.tape(152, 219, 222, 30, 0.85, 1.25, max(len(str(montant)), 1)))
         + f.onde(260, 297, 2.1, 84)
         + bouton(142, 276, 236, "Analyser l'ordre", f.appuie(2.1), f.passe(2.25, d - 0.9, 0.3))
         + f.fin(f'<g class="{f.apparait(2.4, dy=0, echelle=0.8)}"><circle cx="260" cy="364" r="22" fill="{VOILE}" stroke="{PISTE}" stroke-width="4"/>'
                 f'<g class="{tourne}"><circle cx="260" cy="364" r="22" fill="none" stroke="url(#fl-lueur)" stroke-width="4" stroke-linecap="round" stroke-dasharray="42 200"/></g>'
                 f'<g class="{f.bat(2.5)}">{texte(260, 371.5, "?", 21, ENCRE, True, "middle")}</g></g>'
                 + pointeur(338, 306, f.cle([(0, loin), (1.15, loin), (1.95, "opacity: 1; transform: none;"),
                                             (d, "opacity: 1; transform: none;")], courbe=ALLER))))
    return f.scene(c, titre=f"L'ordre de {nom} : {operation.lower()}, {montant} de {titre}. Le verdict reste à découvrir")
