from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.db.session import SessionFactory, close_database
from app.modules.catalog.models import Offer, Product, ProductMedia, Supplier

REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_SOURCE_DIR = (
    REPO_ROOT
    / "frontend"
    / "royal_canin_hq_metric_retail_complete_2026-07-16"
    / "royal_canin_hq_metric_retail"
)
_DEFAULT_PUBLIC_CATALOG_DIR = (
    REPO_ROOT / "frontend" / "pet-platform-frontend" / "public" / "catalog"
)
# Overridable so this can run inside a container that only has the backend
# checked out (e.g. the built `api` image, bind-mounting these two paths in
# from the host) rather than the full monorepo layout REPO_ROOT assumes.
SOURCE_DIR = Path(os.environ.get("RC_IMPORT_SOURCE_DIR", str(_DEFAULT_SOURCE_DIR)))
MANIFEST_PATH = SOURCE_DIR / "manifest.csv"
PUBLIC_CATALOG_DIR = Path(
    os.environ.get("RC_IMPORT_PUBLIC_CATALOG_DIR", str(_DEFAULT_PUBLIC_CATALOG_DIR))
)

# Dev/demo import only. Source manifest.csv/README.md say to verify commercial
# reuse permission for Royal Canin's images/trademarks before shipping this
# beyond local development -- see PACKAGE_MANIFEST.md-adjacent discussion in
# the release-closure work. This importer is not wired into any migration or
# startup path; it only runs when invoked explicitly.
SUPPLIER_INTERNAL_NAME = "Royal Canin UK retail catalog import (dev/demo data)"
SUPPLIER_COUNTRY_CODE = "GB"

SPECIES_FA = {"dog": "سگ", "cat": "گربه"}
FORM_FA = {"dry": "غذای خشک", "wet": "غذای تر", "other": "غذا", "powder": "شیرخشک"}

# Longest-phrase-first transliteration/translation for recurring multi-word
# breed names and Royal Canin line vocabulary found in manifest.csv's
# `product` column. Anything not covered here falls back to per-word lookup
# in WORD_FA, and anything not in either dict is left in English rather than
# guessed -- see `leftover` reporting in translate_line().
PHRASE_FA: list[tuple[str, str]] = [
    ("west highland white terrier", "وست‌هایلند‌وایت‌تریر"),
    ("norwegian forest cat", "گربه جنگل نروژ"),
    ("miniature schnauzer", "اشنوزر مینیاتوری"),
    ("cavalier king charles", "کاوالیر کینگ چارلز"),
    ("british shorthair", "بریتیش‌شورت‌هیر"),
    ("labrador retriever", "لابرادور رتریور"),
    ("golden retriever", "گلدن رتریور"),
    ("german shepherd", "ژرمن‌شپرد"),
    ("french bulldog", "بولداگ فرانسوی"),
    ("yorkshire terrier", "یورکشایر تریر"),
    ("jack russell", "جک راسل"),
    ("great dane", "گریت دین"),
    ("bichon frise", "بیشون فریزه"),
    ("maine coon", "مین‌کون"),
    ("shih tzu", "شیتزو"),
    ("hair&skin", "پوست و مو"),
    ("skin & coat", "پوست و مو"),
    ("light weight", "کنترل وزن"),
    ("appetite control", "کنترل اشتها"),
    ("mother & babycat", "مادر و بچه‌گربه"),
    ("mother & babydog", "مادر و توله‌سگ"),
    ("babycat milk", "شیر بچه‌گربه"),
    ("babydog milk", "شیر توله‌سگ"),
    ("chunks in gravy", "تکه در سس"),
    ("chunks in jelly", "تکه در ژله"),
    ("thin slices in gravy", "ورقه‌نازک در سس"),
    ("thin slices in jelly", "ورقه‌نازک در ژله"),
    ("morsels in gravy", "لقمه در سس"),
    ("morsels in jelly", "لقمه در ژله"),
    ("loaf in sauce", "پاته در سس"),
    ("ultra soft mousse", "موس نرم"),
    ("airlift mousse", "موس هوادار"),
    ("immunity & digestion chews", "جویدنی ایمنی و گوارش"),
    ("joint & ageing chews", "جویدنی مفاصل و سالمندی"),
    ("skin & coat chews", "جویدنی پوست و مو"),
    ("digestion chews", "جویدنی گوارش"),
    ("training treats", "تشویقی آموزش"),
    ("long hair", "پشم‌بلند"),
    ("x-small", "نژاد بسیار کوچک"),
]

WORD_FA = {
    "adult": "بالغ",
    "puppy": "توله‌سگ",
    "kitten": "بچه‌گربه",
    "care": "مراقبت",
    "ageing": "سالمند",
    "sterilised": "عقیم‌شده",
    "sterilized": "عقیم‌شده",
    "indoor": "خانگی",
    "outdoor": "بیرون‌رو",
    "digestive": "گوارشی",
    "urinary": "مجاری ادراری",
    "dental": "دندان",
    "hairball": "گلوله‌مو",
    "dermacomfort": "آرامش پوست",
    "joint": "مفاصل",
    "starter": "شروع‌کننده",
    "instinctive": "غریزی",
    "sensory": "حسی",
    "feel": "لمس",
    "smell": "بو",
    "taste": "طعم",
    "sensible": "متعادل",
    "fussy": "بدغذا",
    "fit": "تناسب‌اندام",
    "giant": "نژاد غول‌پیکر",
    "maxi": "نژاد بزرگ",
    "medium": "نژاد متوسط",
    "mini": "نژاد کوچک",
    "in": "در",
    "loaf": "پاته",
    "mousse": "موس",
    "energy": "پرانرژی",
    "junior": "نوجوان",
    "gravy": "سس",
    "jelly": "ژله",
    "milk": "شیر",
    "chews": "جویدنی",
    "control": "کنترل",
    "beagle": "بیگل",
    "bengal": "بنگال",
    "boxer": "باکسر",
    "bulldog": "بولداگ",
    "chihuahua": "چیواوا",
    "cocker": "کوکر",
    "dachshund": "داشهند",
    "dalmatian": "دالمیشن",
    "maltese": "مالتیز",
    "pomeranian": "پومرانین",
    "poodle": "پودل",
    "pug": "پاگ",
    "rottweiler": "روتوایلر",
    "schnauzer": "اشنوزر",
    "sphynx": "اسفینکس",
    "siamese": "سیامی",
    "ragdoll": "رگدال",
    "persian": "پرشین",
}

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa_num(value: float) -> str:
    if float(value).is_integer():
        value = int(value)
    return str(value).translate(_PERSIAN_DIGITS)


def translate_line(raw: str) -> tuple[str, list[str]]:
    """Best-effort Persian transliteration of a Royal Canin line/breed name.

    Returns (translated text, leftover untranslated English words) so the
    caller can report translation gaps instead of silently guessing.
    """
    text = re.sub(r"FOR APAC SKUs ONLY:.*", "", raw, flags=re.IGNORECASE)
    text = text.replace("�", "").replace("®", "").replace("™", "")
    text = re.sub(r"\s+-\s+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    for phrase, fa in sorted(PHRASE_FA, key=lambda item: -len(item[0])):
        text = re.compile(re.escape(phrase), re.IGNORECASE).sub(fa, text)

    leftover: list[str] = []

    def replace_word(match: re.Match[str]) -> str:
        token = match.group(0)
        fa = WORD_FA.get(token.lower())
        if fa is not None:
            return fa
        leftover.append(token)
        return token

    text = re.sub(r"[A-Za-z']+", replace_word, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text, leftover


def parse_pack_grams(pack_size: str) -> int:
    s = pack_size.strip().lower()
    if m := re.fullmatch(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*g", s):
        return round(int(m.group(1)) * float(m.group(2)))
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*kg", s):
        return round(float(m.group(1)) * 1000)
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*g", s):
        return round(float(m.group(1)))
    raise ValueError(f"unrecognized pack_size: {pack_size!r}")


def pack_size_label_fa(pack_size: str) -> str:
    s = pack_size.strip().lower()
    if m := re.fullmatch(r"(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*g", s):
        return f"{_fa_num(int(m.group(1)))}×{_fa_num(float(m.group(2)))} گرم"
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*kg", s):
        return f"{_fa_num(float(m.group(1)))} کیلوگرم"
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*g", s):
        return f"{_fa_num(float(m.group(1)))} گرم"
    return pack_size


# Synthetic demo pricing. manifest.csv carries no price data at all (it is a
# packshot/EAN scrape, not a price feed) -- these are plausible placeholder
# IRR-per-kg figures for local/demo use only, not real Royal Canin prices.
PRICE_PER_KG_IRR = {
    ("mainmeal", "dry"): 950_000,
    ("mainmeal", "wet"): 1_600_000,
    ("mainmeal", "other"): 1_100_000,
    ("mainmeal", "powder"): 2_200_000,
    ("care_and_treats", None): 1_400_000,
    ("supplement", None): 1_800_000,
}
MIN_PRICE_IRR = 180_000


def synth_price_irr(food_type: str, form: str, grams: int) -> int:
    key = (food_type, form) if (food_type, form) in PRICE_PER_KG_IRR else (food_type, None)
    per_kg = PRICE_PER_KG_IRR.get(key, 1_000_000)
    raw = per_kg * grams / 1000
    rounded = round(raw / 10_000) * 10_000
    return max(rounded, MIN_PRICE_IRR)


@dataclass
class ManifestRow:
    species: str
    product: str
    food_type: str
    pack_size: str
    ean: str
    local_image: str


def load_manifest() -> list[ManifestRow]:
    with MANIFEST_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            ManifestRow(
                species=row["species"],
                product=row["product"],
                food_type=row["food_type"],
                pack_size=row["pack_size"],
                ean=row["ean"],
                local_image=row["local_image"],
            )
            for row in reader
        ]
    deduped: dict[str, ManifestRow] = {}
    for row in rows:
        deduped.setdefault(row.ean, row)
    return list(deduped.values())


def detect_form(product_field: str) -> str:
    segment = product_field.split(" - ")[2].strip().lower() if " - " in product_field else ""
    if segment in FORM_FA:
        return segment
    return "other"


def extract_line_name(product_field: str) -> str:
    """`<year> - <src> - <Form> - <Species> - <LINE...> - Zone Europe - ...`
    -> `<LINE...>`. Falls back to the whole field if the shape is unexpected.
    """
    parts = [p.strip() for p in product_field.split(" - ")]
    if len(parts) <= 4:
        return product_field
    end = next((i for i, p in enumerate(parts) if p == "Zone Europe"), len(parts))
    if end <= 4:
        return parts[4]
    return " - ".join(parts[4:end])


async def import_catalog(*, dry_run: bool) -> None:
    try:
        await _import_catalog(dry_run=dry_run)
    finally:
        await close_database()


async def _import_catalog(*, dry_run: bool) -> None:
    rows = load_manifest()
    groups: dict[str, list[ManifestRow]] = {}
    for row in rows:
        groups.setdefault(row.product, []).append(row)

    leftover_words: Counter[str] = Counter()
    products_created = 0
    products_reused = 0
    offers_created = 0
    offers_skipped = 0
    images_copied = 0

    async with SessionFactory() as session:
        supplier = await session.scalar(
            select(Supplier).where(Supplier.internal_name == SUPPLIER_INTERNAL_NAME)
        )
        if supplier is None:
            supplier = Supplier(
                internal_name=SUPPLIER_INTERNAL_NAME,
                country_code=SUPPLIER_COUNTRY_CODE,
                active=True,
            )
            session.add(supplier)
            await session.flush()

        for product_field, group_rows in groups.items():
            first = group_rows[0]
            species_fa = SPECIES_FA[first.species]
            form = detect_form(product_field)
            line_fa, leftover = translate_line(extract_line_name(product_field))
            leftover_words.update(w.lower() for w in leftover)

            existing_offer = await session.scalar(
                select(Offer).where(Offer.sku == f"rc-{first.ean}")
            )
            if existing_offer is not None:
                found = await session.get(Product, existing_offer.product_id)
                if found is None:
                    raise RuntimeError(
                        f"offer {existing_offer.sku} references missing product "
                        f"{existing_offer.product_id}"
                    )
                product = found
                products_reused += 1
            else:
                if first.food_type == "mainmeal":
                    category_fa = FORM_FA.get(form, "غذا")
                elif first.food_type == "care_and_treats":
                    category_fa = "تشویقی/میان‌وعده"
                else:
                    category_fa = "مکمل"
                name_fa = f"رویال کنین {line_fa} - {category_fa} {species_fa}".strip()
                product = Product(
                    name_fa=name_fa[:300],
                    description_fa=(
                        f"محصول رویال کنین برای {species_fa}: {line_fa} ({category_fa})."
                    )[:2000],
                    status="active",
                )
                session.add(product)
                await session.flush()
                products_created += 1

                image_source = SOURCE_DIR / first.local_image
                dest_dir = PUBLIC_CATALOG_DIR / first.species
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / Path(first.local_image).name
                if not dry_run and image_source.is_file():
                    shutil.copy2(image_source, dest_path)
                    images_copied += 1
                public_reference = f"/catalog/{first.species}/{Path(first.local_image).name}"
                session.add(
                    ProductMedia(
                        product_id=product.id,
                        media_type="image",
                        public_reference=public_reference,
                        alt_text_fa=f"تصویر بسته‌بندی {name_fa}"[:500],
                        sort_order=0,
                        active=True,
                    )
                )

            for row in group_rows:
                sku = f"rc-{row.ean}"
                if await session.scalar(select(Offer).where(Offer.sku == sku)):
                    offers_skipped += 1
                    continue
                grams = parse_pack_grams(row.pack_size)
                unit_label_fa = "کیسه" if form == "dry" else "پوچ" if form == "wet" else "بسته"
                title_fa = f"رویال کنین {line_fa} - {pack_size_label_fa(row.pack_size)}"[:300]
                session.add(
                    Offer(
                        product_id=product.id,
                        supplier_id=supplier.id,
                        sku=sku,
                        title_fa=title_fa,
                        unit_label_fa=unit_label_fa,
                        price_irr=synth_price_irr(row.food_type, form, grams),
                        status="active",
                        minimum_shelf_life_months=12 if form == "dry" else 6,
                    )
                )
                offers_created += 1

            if product.nominal_quantity_grams is None and group_rows:
                product.nominal_quantity_grams = parse_pack_grams(group_rows[0].pack_size)

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    print(
        "royal_canin_import_complete "
        f"dry_run={dry_run} products_created={products_created} "
        f"products_reused={products_reused} offers_created={offers_created} "
        f"offers_skipped={offers_skipped} images_copied={images_copied}"
    )
    if leftover_words:
        top = leftover_words.most_common(20)
        print(f"untranslated_word_fallbacks_top20={top}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse and validate without writing to the database or copying images",
    )
    args = parser.parse_args()
    asyncio.run(import_catalog(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
