#!/usr/bin/env python3
"""
Générateur de site statique pour le club de peinture sur figurines.

Usage :
    python3 build.py            # génère le site dans _site/
    python3 build.py --clean    # supprime _site/ puis regénère

Contenu :
    content/figurines/*.md   -> 1 fiche par figurine (front-matter YAML + Markdown)
    content/pages/*.md       -> pages statiques (le club, rejoindre...)
    content/evenements.yaml  -> agenda du club
    photos/<slug>/*.jpg|png  -> photos d'une figurine (la 1ère = photo principale)

Zéro backend, zéro base de données : tout est généré en HTML statique.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent
CONTENT = ROOT / "content"
PHOTOS = ROOT / "photos"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUT = ROOT / "_site"

THUMB_SIZE = (720, 720)      # taille max des vignettes de galerie
LARGE_SIZE = (1600, 1600)    # taille max des photos plein écran
SITE = {
    "nom": "Fig'78",          # <- personnalisez ici
    "accroche": "Club de peinture sur figurines & jeux de figurines",
    "discord": "https://discord.gg/vezt7M4neS",
    "instagram": "https://www.instagram.com/fig78_club/",
    "email": "contact@votre-club.fr",
}

MD = markdown.Markdown(extensions=["extra", "smarty"])


# --------------------------------------------------------------------------- #
#  Modèle de données
# --------------------------------------------------------------------------- #
@dataclass
class Figurine:
    slug: str
    titre: str
    peintre: str = "?"
    jeu: str = ""
    faction: str = ""
    techniques: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    date: date | None = None
    palette: list[dict] = field(default_factory=list)  # [{nom, couleur}]
    photos: list[str] = field(default_factory=list)  # chemins définis dans l'éditeur, dans l'ordre
    corps_html: str = ""
    photo_principale: str = ""      # URL relative de la vignette
    photo_grande: str = ""          # URL relative du grand format
    galerie: list[dict] = field(default_factory=list)  # [{thumb, large}]

    @property
    def tous_tags(self) -> list[str]:
        base = [t for t in ([self.jeu, self.faction] + self.techniques + self.tags) if t]
        # dédoublonne en gardant l'ordre
        return list(dict.fromkeys(base))


# --------------------------------------------------------------------------- #
#  Parsing du contenu
# --------------------------------------------------------------------------- #

def vers_date(val) -> date | None:
    """Accepte un objet date (YAML natif) ou une chaîne ISO (écrite par le CMS)."""
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val:
        return date.fromisoformat(val[:10])
    return None


def parse_front_matter(path: Path) -> tuple[dict, str]:
    """Sépare le front-matter YAML (entre '---') du corps Markdown."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm) or {}, body.strip()
    return {}, text.strip()


def charger_figurines() -> list[Figurine]:
    figurines = []
    for path in sorted((CONTENT / "figurines").glob("*.md")):
        meta, body = parse_front_matter(path)
        MD.reset()
        fig = Figurine(
            slug=path.stem,
            titre=meta.get("titre", path.stem),
            peintre=meta.get("peintre", "?"),
            jeu=meta.get("jeu", ""),
            faction=meta.get("faction", ""),
            techniques=meta.get("techniques", []) or [],
            tags=meta.get("tags", []) or [],
            date=vers_date(meta.get("date")),
            palette=meta.get("palette", []) or [],
            photos=meta.get("photos", []) or [],
            corps_html=MD.convert(body),
        )
        figurines.append(fig)
    # plus récentes d'abord
    figurines.sort(key=lambda f: f.date or date.min, reverse=True)
    return figurines


def charger_evenements() -> list[dict]:
    path = CONTENT / "evenements.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    evts = data.get("evenements", data if isinstance(data, list) else []) or []
    for e in evts:
        e["date"] = vers_date(e.get("date"))
    evts.sort(key=lambda e: e["date"] or date.min)
    # ne garde que le futur (et aujourd'hui)
    return [e for e in evts if (e["date"] or date.min) >= date.today()]


def charger_pages() -> list[dict]:
    pages = []
    for path in sorted((CONTENT / "pages").glob("*.md")):
        meta, body = parse_front_matter(path)
        MD.reset()
        pages.append({
            "slug": path.stem,
            "titre": meta.get("titre", path.stem.replace("-", " ").title()),
            "ordre": meta.get("ordre", 99),
            "html": MD.convert(body),
        })
    pages.sort(key=lambda p: p["ordre"])
    return pages


# --------------------------------------------------------------------------- #
#  Photos : vignettes WebP via Pillow, ou placeholder SVG si aucune photo
# --------------------------------------------------------------------------- #
def placeholder_svg(fig: Figurine) -> str:
    """Placeholder déterministe (couleur dérivée du slug) encodé en data-URI."""
    h = hashlib.sha256(fig.slug.encode()).hexdigest()
    hue = int(h[:2], 16) * 360 // 255
    initiales = "".join(w[0] for w in fig.titre.split()[:2]).upper()
    svg = f"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 720 720'>
<rect width='720' height='720' fill='hsl({hue} 22% 18%)'/>
<circle cx='360' cy='330' r='150' fill='none' stroke='hsl({hue} 45% 45%)' stroke-width='6'/>
<ellipse cx='360' cy='560' rx='170' ry='36' fill='hsl({hue} 30% 26%)'/>
<text x='360' y='355' font-family='Georgia,serif' font-size='96' fill='hsl({hue} 50% 70%)'
      text-anchor='middle' dominant-baseline='middle'>{initiales}</text>
<text x='360' y='665' font-family='monospace' font-size='26' fill='hsl({hue} 20% 55%)'
      text-anchor='middle'>photo à venir</text></svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def traiter_photos(fig: Figurine) -> None:
    """Génère vignette + grand format WebP pour chaque photo de la figurine.

    Ordre déterminé par le champ `photos` du front-matter (renseigné depuis
    l'éditeur, glisser-déposer pour réordonner). Si ce champ est vide (fiche
    non migrée), on retombe sur l'ancien comportement : scan alphabétique de
    photos/<slug>/.
    """
    if fig.photos:
        sources = [p for p in (ROOT / chemin.lstrip("/") for chemin in fig.photos) if p.exists()]
    else:
        src_dir = PHOTOS / fig.slug
        sources = sorted(
            p for p in (src_dir.glob("*") if src_dir.exists() else [])
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
    if not sources:
        uri = placeholder_svg(fig)
        fig.photo_principale = fig.photo_grande = uri
        return

    from PIL import Image  # importé ici : Pillow optionnel si aucune photo

    dest = OUT / "photos" / fig.slug
    dest.mkdir(parents=True, exist_ok=True)
    for i, src in enumerate(sources):
        with Image.open(src) as im:
            im = im.convert("RGB")
            for suffix, size in (("thumb", THUMB_SIZE), ("large", LARGE_SIZE)):
                copie = im.copy()
                copie.thumbnail(size, Image.LANCZOS)
                copie.save(dest / f"{src.stem}-{suffix}.webp", "WEBP", quality=82)
        rel = f"photos/{fig.slug}/{src.stem}"
        entry = {"thumb": f"{rel}-thumb.webp", "large": f"{rel}-large.webp"}
        fig.galerie.append(entry)
        if i == 0:
            fig.photo_principale = entry["thumb"]
            fig.photo_grande = entry["large"]


# --------------------------------------------------------------------------- #
#  Rendu
# --------------------------------------------------------------------------- #
def build(clean: bool = False) -> None:
    if clean and OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(exist_ok=True)
    (OUT / "figurines").mkdir(exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    env.globals.update(site=SITE, css=css, annee=date.today().year)

    figurines = charger_figurines()
    for fig in figurines:
        traiter_photos(fig)
    evenements = charger_evenements()
    pages = charger_pages()
    tous_les_tags = sorted({t for f in figurines for t in f.tous_tags})

    # Accueil / galerie
    (OUT / "index.html").write_text(
        env.get_template("index.html").render(
            figurines=figurines,
            a_la_une=figurines[0] if figurines else None,
            evenements=evenements[:3],
            tags=tous_les_tags,
            pages=pages,
            racine=".",
        ),
        encoding="utf-8",
    )

    # Fiches figurines
    tpl_fig = env.get_template("figurine.html")
    for fig in figurines:
        (OUT / "figurines" / f"{fig.slug}.html").write_text(
            tpl_fig.render(fig=fig, pages=pages, racine=".."),
            encoding="utf-8",
        )

    # Pages statiques (le club, rejoindre, ...)
    tpl_page = env.get_template("page.html")
    for page in pages:
        (OUT / f"{page['slug']}.html").write_text(
            tpl_page.render(page=page, evenements=evenements, pages=pages, racine="."),
            encoding="utf-8",
        )

    # Photos brutes : nécessaire pour les images insérées directement dans le
    # corps Markdown (pages, description de figurine...), en plus des vignettes
    # WebP déjà générées par traiter_photos() pour les galeries de figurines.
    if PHOTOS.exists():
        shutil.copytree(PHOTOS, OUT / "photos", dirs_exist_ok=True)

    # Images statiques (logo...)
    img_src = STATIC / "img"
    if img_src.exists():
        shutil.copytree(img_src, OUT / "img", dirs_exist_ok=True)

    # Interface d'administration (Sveltia CMS)
    admin_src = ROOT / "admin"
    if admin_src.exists():
        shutil.copytree(admin_src, OUT / "admin", dirs_exist_ok=True)

    print(f"✔ Site généré dans {OUT}/")
    print(f"  {len(figurines)} figurine(s), {len(pages)} page(s), "
          f"{len(evenements)} événement(s) à venir")
    print("  Prévisualisation : python3 -m http.server -d _site 8000")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clean", action="store_true", help="supprime _site/ avant build")
    args = ap.parse_args()
    try:
        build(clean=args.clean)
    except Exception as exc:  # message d'erreur lisible pour les non-devs
        print(f"✘ Erreur de build : {exc}", file=sys.stderr)
        sys.exit(1)
