#!/usr/bin/env python3
"""Build the dashboard's checked-in portrait and entity media.

Portraits are resolved from the P18 claim already attached to each person's
Wikidata identity in the dashboard.  The script downloads a Commons thumbnail,
normalises it to a compact WebP, and records source/licence metadata.  People
without a verified image keep an explicit local silhouette; the UI never makes
runtime requests to third-party image services.
"""

from __future__ import annotations

import html
import io
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts" / "dashboard.html"
OUT = ROOT / "assets" / "media"
PORTRAITS = OUT / "portraits"
UA = "IranArchivesTimeline/1.0 (static media builder; research project)"

# Explicit, reviewed fallbacks for people whose dashboard identity has no
# usable Wikidata P18 portrait.  These are direct images from an official
# profile, the person's verified public account, or the cited biographical
# source.  Copyright remains with the named source unless that source says
# otherwise; the manifest keeps the original page for attribution.
PORTRAIT_OVERRIDES = {
    "آنا کلی": ("https://pbs.twimg.com/profile_images/1958545655439224832/M0oKTGeH.jpg", "https://x.com/AnnaKellyGOP", "حساب عمومی رسمی"),
    "ابراهیم الهاشمی": ("https://www.iicom.org/wp-content/uploads/Ibrahim-Sultan-Al-Hashmi.jpg", "https://www.iicom.org/profile/ibrahim-sultan-al-hashmi-h-e/", "صفحه معرفی رسمی"),
    "ابراهیم عقیل": ("https://i.arabi21.com/arabi21/908x510/9202420135856148312893.jpg", "https://arabi21.com/story/1627388/", "تصویر آرشیوی رسانه"),
    "اشکان ملکی": ("https://www.iranhr.net/media/content/images/Ashkan_Maleki_and_Mehrdad_Mohammadinia_8rDDI0E.jpg.885x520_q85_box-0%2C0%2C3682%2C2167_crop_detail_upscale.jpg", "https://www.iranhr.net/en/articles/8789/", "سازمان حقوق بشر ایران"),
    "امیرحسین حاتمی": ("https://admin.zendan.info/Attachments/%D8%AD%D8%A7%D8%AA%D9%85%DB%8C-1.jpg", "https://ipa.united4iran.org/en/prisoner/11706", "اطلس زندان‌های ایران"),
    "امیرسعید ایروانی": ("https://newsimg.koreatimes.co.kr/2025/09/28/b240bb93-6daa-4f7f-a28e-dca5b53c2094.jpg", "https://www.koreatimes.co.kr/foreignaffairs/20250928/uns-reimposition-of-sanctions-on-iran-to-have-limited-impact-on-korea-foreign-ministry", "تصویر خبری"),
    "بهروز فراهانی": ("https://iranhr.net/media/content/images/BFs.jpg", "https://iranhr.net/fa/articles/5238/", "سازمان حقوق بشر ایران"),
    "حمزه خلیلی": ("https://i.iranintl.com/images/rdk9umy0/production/6b802a87a4df749670abdffd49979af03a22e096-1200x799.jpg?rect=0,85,1200,630&w=1200&h=630&q=66&fit=max&auto=format", "https://www.iranintl.com/fa/202404186918", "تصویر خبری"),
    "حسین محبی": ("https://cdn.nournews.ir/thumbnail/kkfGC46Pfq5P/aaL6Ouk78g_pB0jNFGRVmiUbnHhPUYnxssUDEixi34PP4Z-TV2Q2UIxFeAYFYy5E4Mlu3OKv6bxG_KKG-zK8D1cYdKPKrY3gW8wppxTSvBUy0bhEjLyOnsDl2N5O5452/173205076.jpg", "https://nournews.ir/en/news/356274/strait-of-hormuz-reality-determined-on-ground-irgc-spokesperson", "تصویر منبع آرشیو"),
    "رائد کریملی": ("https://www.arabnews.com/sites/default/files/userimages/20/rayed.jpg", "https://www.arabnews.com/node/1568436/amp", "تصویر معرفی دیپلمات"),
    "رضا امیری مقدم": ("https://www.jomhornews.com/images/docs/000161/n00161240-b.jpg", "https://www.jomhornews.com/fa/news/161240/", "تصویر خبری"),
    "ساک نوپتایسونگ": ("https://image.mfa.go.th/mfa/0/wdW3FTtVMc/2026-04-22/2.jpg", "https://chengdu.thaiembassy.org/", "وزارت خارجه تایلند؛ تصویر جلسه"),
    "شفقت علی خان": ("https://www.arabnews.com/sites/default/files/pictures/February/3913761/2025/mofaspox.jpg", "https://www.arabnews.com/node/2590186/", "تصویر نشست رسمی"),
    "علیا احمد بن سیف آل ثانی": ("https://www.gulf-times.com/gulftimes/uploads/images/2026/03/12/425312.jpg", "https://www.gulf-times.com/article/722286/", "تصویر خبری"),
    "غلامحسین درزی": ("https://d2udx5iz3h7s4h.cloudfront.net/2026/1/16/67447d5679e29389136effb6/image/5a33d4898dd2ad0441c61c46b9abdaec58cf8c48beee5720d99c0e778e1e6ecf.JPG", "https://www.trtfarsi.com/article/7d7b33b83ace", "تصویر نشست رسمی"),
    "فتح‌الله آوری": ("https://gdb.voanews.com/2A308366-85A9-4C0B-8BAA-36AC85CABA23.jpg", "https://ir.voanews.com/a/fathullah-avari-execution-judiciary/8157274.html", "تصویر منبع آرشیو"),
    "رویا برومند": ("https://i0.wp.com/blog.iranrights.org/wp-content/uploads/2014/03/20140312_EP-004772_MCU_027.jpg?fit=1200%2C800&ssl=1", "https://blog.iranrights.org/no-more-talk-its-time-for-iran-to-act-roya-boroumand/", "مرکز عبدالرحمن برومند"),
    "لادن برومند": ("https://www.gedistatic.it/content/gedi/img/huffingtonpost/2024/11/29/141019928-727b3547-29bd-4eea-88d3-c6cf350d2345.jpg", "https://www.huffingtonpost.it/esteri/2024/11/30/news/ladan_boroumand_islamismo_contro_i_valori_della_democrazia_liberale-17857515/", "تصویر مصاحبه"),
    "مائو نینگ": ("https://storage.united24media.com/thumbs/x/a/3e/e16aeeaad63104e00066c337b57be3ea.jpg", "https://united24media.com/latest-news/china-says-its-position-on-russias-full-scale-invasion-of-ukraine-has-not-changed-16230", "تصویر نشست رسمی"),
    "ماجد الانصاری": ("https://www.qatar-tribune.com/watanqatartribune/uploads/images/2026/09/05/386385.jpg", "https://www.qatar-tribune.com/article/252172/", "تصویر نشست رسمی"),
    "مایک نیدهام": ("https://images.axios.com/8tp0l6E_S72e6KQxppQTVLZy3to=/0x535:5134x3423/1366x768/2026/05/25/1779748219195.jpeg", "https://www.axios.com/2026/05/26/mike-needham-rubio-deputy-national-security-advisor", "تصویر خبری"),
    "محمد حبیبی": ("http://iranhr.net/media/content/images/Mohammad_Habibi_-_FA.png", "https://iranhr.net/fa/people/6356/", "سازمان حقوق بشر ایران"),
    "محمد محدثین": ("https://www.ncr-iran.org/en/wp-content/uploads/2022/01/mohammad-mohadesin-002.jpg", "https://www.ncr-iran.org/en/about-ncri/ncri/foreign-affairs-committee-chair/", "صفحه معرفی سازمانی"),
    "محمدهادی حاجی‌رحیمی": ("https://i.iranintl.com/images/rdk9umy0/production/e1130845ed6242373c189e0c3ba5f3051c408d6a-1276x1091.jpg?auto=format&fit=max&h=630&rect=0%2C158%2C1276%2C670&w=1200", "https://www.iranintl.com/en/202405174265", "تصویر خبری"),
    "مریم معمارصادقی": ("https://pbs.twimg.com/profile_images/1860818202051088384/i7apY3-4_400x400.jpg", "https://x.com/memarsadeghi", "حساب عمومی رسمی"),
    "مهرداد اخلاقی کتابچی": ("https://cdn.ajel.sa/articles/2026-10/%D9%85%D9%87%D8%B1%D8%AF%D8%A7%D8%AF-%D8%A3%D8%AE%D9%84%D8%A7%D9%82%D9%8A-%D9%83%D8%AA%D8%A7%D8%A8%D8%AC%D9%8A-7XqKiNK-.webp", "https://english.ajel.sa/world/u2578vc3e", "تصویر خبری"),
    "مهرداد مارتی یوسفیانی": ("https://news.gooya.com/2025/02/13/Mehrdad_Youssefiani.jpg", "https://news.gooya.com/2025/02/post-95296.php", "تصویر نویسنده"),
    "مهرداد محمدی‌نیا": ("https://admin.zendan.info/Attachments/%D9%85%D9%87%D8%B1%D8%AF%D8%A7%D8%AF-1.jpg", "https://ipa.united4iran.org/fa/prisoner/11710", "اطلس زندان‌های ایران"),
    "مهسا علیمردانی": ("https://www.oii.ox.ac.uk/wp-content/uploads/2017/09/mahsa-700x395.jpg", "https://www.oii.ox.ac.uk/people/profiles/mahsa-alimadeni/", "دانشگاه آکسفورد"),
    "واهان کوستانیان": ("https://www.mfa.am/images/staff/1/17875654256934.jpeg", "https://www.mfa.am/fr/deputy-ministers/184", "وزارت خارجه ارمنستان"),
    "کاوه شهروز": ("https://media.assettype.com/westernstandard%2F2024-02%2F65b0f824-7ee1-485e-a079-fef23c19ec00%2FKaveh_Shahrooz.webp?ar=40%3A21&auto=format%2Ccompress&enlarge=true&mode=crop&ogImage=true&overlay=false&overlay_position=bottom&overlay_width=100&w=1200", "https://www.westernstandard.news/canadian/federal-conservative-nomination-candidate-withdraws-from-race-over-foreign-meddling-from-iran/52617", "تصویر خبری"),
    "گیسو نیا": ("https://miro.medium.com/v2/resize%3Afit%3A1400/1%2AfQn42ktpG-cEdsv7ZnP4Ow.jpeg", "https://medium.com/humanist-voices/interview-with-gissou-nia-on-becoming-involved-in-human-rights-work-3e568bdd96bd", "تصویر مصاحبه"),
    "یوسف پزشکیان": ("https://ynet-pic1.yit.co.il/picserver6/wcm_upload/2026/03/17/SJu2hGP9bx/98765.png", "https://www.ynetnews.com/article/r1dvdnvcbe", "تصویر ترکیبی خبری"),
    "ژای جون": ("https://photo-cdn.urdupoint.com/media/2019/09/_2/740x404/pic_1567429628.jpg", "https://www.urdupoint.com/en/world/china-appoints-ambassador-zhai-jun-as-special-702967.html", "تصویر معرفی دیپلمات"),
}


def fetch_json(url: str, attempts: int = 4) -> dict:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch_bytes(url: str, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise AssertionError("unreachable")


def people_registry() -> dict:
    source = LAYOUT.read_text(encoding="utf-8")
    start = source.index("const PEOPLE=") + len("const PEOPLE=")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(source[start : index + 1])
    raise RuntimeError("PEOPLE registry was not closed")


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def entity_claims(qids: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for offset in range(0, len(qids), 45):
        batch = qids[offset : offset + 45]
        params = urllib.parse.urlencode(
            {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "props": "claims",
                "format": "json",
            }
        )
        payload = fetch_json("https://www.wikidata.org/w/api.php?" + params)
        result.update(payload.get("entities", {}))
        time.sleep(0.15)
    return result


def commons_metadata(filenames: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for offset in range(0, len(filenames), 35):
        batch = filenames[offset : offset + 35]
        params = urllib.parse.urlencode(
            {
                "action": "query",
                "titles": "|".join("File:" + name for name in batch),
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": "480",
                "format": "json",
                "formatversion": "2",
            }
        )
        payload = fetch_json("https://commons.wikimedia.org/w/api.php?" + params)
        for page in payload.get("query", {}).get("pages", []):
            info = (page.get("imageinfo") or [{}])[0]
            title = page.get("title", "")
            if title.startswith("File:"):
                result[title[5:]] = info
        time.sleep(0.15)
    return result


def image_claim(entity: dict, properties: tuple[str, ...] = ("P18",)) -> str:
    claims = entity.get("claims", {})
    for prop in properties:
        try:
            return claims[prop][0]["mainsnak"]["datavalue"]["value"]
        except (KeyError, IndexError, TypeError):
            pass
    return ""


def normalise_portrait(raw: bytes, destination: Path) -> None:
    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((360, 360), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (360, 360), "#e4ebdd")
        canvas.paste(image, ((360 - image.width) // 2, (360 - image.height) // 2))
        canvas.save(destination, "WEBP", quality=80, method=6)


def normalise_logo(raw: bytes, destination: Path) -> None:
    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        image.thumbnail((240, 180), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (240, 180), (255, 255, 255, 0))
        canvas.alpha_composite(image, ((240 - image.width) // 2, (180 - image.height) // 2))
        canvas.save(destination, "WEBP", quality=86, method=6)


def build_entity_media() -> dict:
    flags_dir = OUT / "flags"
    logos_dir = OUT / "logos"
    flags_dir.mkdir(parents=True, exist_ok=True)
    logos_dir.mkdir(parents=True, exist_ok=True)
    flag_sets = {
        "ir": ["ایران", "ایران پهلوی"],
        "us": ["آمریکا", "ایالات متحده", "ایالات متحده آمریکا"],
        "il": ["اسرائیل"], "qa": ["قطر"], "om": ["عمان"],
        "sa": ["عربستان", "عربستان سعودی"], "tr": ["ترکیه"],
        "ru": ["روسیه"], "cn": ["چین", "جمهوری خلق چین"],
        "gb": ["بریتانیا", "انگلیس"], "fr": ["فرانسه"],
        "de": ["آلمان"], "it": ["ایتالیا"], "iq": ["عراق"],
        "lb": ["لبنان"], "sy": ["سوریه", "جمهوری عربی سوریه"],
        "jo": ["اردن"], "eg": ["مصر"], "ae": ["امارات", "امارات متحده عربی"],
        "pk": ["پاکستان"], "in": ["هند"], "am": ["ارمنستان"],
        "az": ["آذربایجان", "جمهوری آذربایجان"], "ye": ["یمن"],
        "bh": ["بحرین"], "kw": ["کویت"], "ch": ["سوئیس"],
        "ca": ["کانادا"], "af": ["افغانستان"], "kz": ["قزاقستان"],
        "tm": ["ترکمنستان"], "ps": ["فلسطین", "دولت فلسطین", "سرزمین‌های فلسطینی‌نشین"],
        "ar": ["آرژانتین"],
    }
    manifest: dict[str, dict] = {}
    for code, aliases in flag_sets.items():
        destination = flags_dir / f"{code}.svg"
        if not destination.exists():
            destination.write_bytes(fetch_bytes(f"https://flagcdn.com/{code}.svg"))
        entry = {
            "kind": "flag",
            "src": f"/iran-archives-timeline/assets/media/flags/{code}.svg",
            "alt": f"پرچم {aliases[0]}",
            "source": f"https://flagcdn.com/{code}.svg",
            "license": "پرچم ملی؛ منبع فایل FlagCDN/Wikimedia Commons",
        }
        for alias in aliases:
            manifest[alias] = entry

    institutions = {
        "Q1065": ["سازمان ملل", "سازمان ملل متحد"],
        "Q41984": ["آژانس بین‌المللی انرژی اتمی", "آژانس اتمی"],
        "Q458": ["اتحادیه اروپا"],
        "Q7184": ["ناتو", "پیمان آتلانتیک شمالی"],
        "Q182675": ["سپاه پاسداران", "سپاه پاسداران انقلاب اسلامی", "سپاه"],
        "Q789915": ["وزارت خارجه آمریکا", "وزارت امور خارجه آمریکا"],
        "Q35525": ["کاخ سفید"],
        "Q13371": ["کنست", "پارلمان اسرائیل"],
        "Q186831": ["ارتش اسرائیل", "نیروهای دفاعی اسرائیل"],
        "Q7795": ["اوپک", "سازمان کشورهای صادرکننده نفت"],
        "Q37470": ["شورای امنیت", "شورای امنیت سازمان ملل"],
    }
    claims = entity_claims(list(institutions))
    qid_files = {
        qid: image_claim(claims.get(qid, {}), ("P154", "P94", "P18"))
        for qid in institutions
    }
    logo_meta = commons_metadata(sorted({value for value in qid_files.values() if value}))
    for qid, aliases in institutions.items():
        filename = qid_files.get(qid, "")
        info = logo_meta.get(filename, {})
        thumb = info.get("thumburl") or info.get("url")
        if not thumb:
            continue
        destination = logos_dir / f"{qid.lower()}.webp"
        try:
            if not destination.exists():
                normalise_logo(fetch_bytes(thumb), destination)
        except Exception as error:
            print(f"logo failed: {aliases[0]}: {error}")
            continue
        ext = info.get("extmetadata", {})
        field = lambda key: clean_html((ext.get(key) or {}).get("value"))
        entry = {
            "kind": "logo",
            "src": f"/iran-archives-timeline/assets/media/logos/{destination.name}",
            "alt": f"نشان {aliases[0]}",
            "source": info.get("descriptionurl") or info.get("url") or "",
            "license": field("LicenseShortName") or field("UsageTerms"),
            "licenseUrl": field("LicenseUrl"),
            "author": field("Artist") or field("Credit"),
        }
        for alias in aliases:
            manifest[alias] = entry
    (OUT / "entities.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {"entityAliases": len(manifest), "logos": len(list(logos_dir.glob('*.webp'))), "flags": len(list(flags_dir.glob('*.svg')))}


def placeholder(destination: Path, initials: str) -> None:
    image = Image.new("RGB", (360, 360), "#e4ebdd")
    draw = ImageDraw.Draw(image)
    draw.ellipse((22, 18, 338, 334), fill="#d2dfca", outline="#bdcdb5", width=4)
    draw.ellipse((120, 72, 240, 192), fill="#f8f8f1")
    draw.ellipse((78, 190, 282, 338), fill="#f8f8f1")
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 46)
        draw.text((180, 310), initials, anchor="mm", font=font, fill="#1c4b3a")
    except OSError:
        pass
    image.save(destination, "WEBP", quality=82, method=6)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PORTRAITS.mkdir(parents=True, exist_ok=True)
    people = people_registry()
    canonical: dict[str, dict] = {}
    for name, record in people.items():
        canonical.setdefault(record.get("canonical") or name, record)
    old_manifest_path = OUT / "portraits.json"
    old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8")) if old_manifest_path.exists() else {}

    qids = sorted({record["qid"] for record in canonical.values() if record.get("qid")})
    entities = entity_claims(qids)
    qid_to_filename = {qid: image_claim(entities.get(qid, {})) for qid in qids}
    metadata = commons_metadata(sorted({name for name in qid_to_filename.values() if name}))

    manifest: dict[str, dict] = {}

    def build_one(item: tuple[int, tuple[str, dict]]) -> tuple[str, dict, bool]:
        index, (name, record) = item
        qid = record.get("qid", "")
        filename = qid_to_filename.get(qid, "")
        info = metadata.get(filename, {})
        override = PORTRAIT_OVERRIDES.get(name)
        output_name = f"{slug(qid or 'person-' + str(index))}.webp"
        destination = PORTRAITS / output_name
        previous = old_manifest.get(name, {})
        if destination.exists() and previous and not previous.get("placeholder"):
            return name, previous, True
        entry = {
            "src": f"/iran-archives-timeline/assets/media/portraits/{output_name}",
            "alt": f"چهره {name}",
            "wikidata": f"https://www.wikidata.org/wiki/{qid}" if qid else "",
            "source": "",
            "license": "",
            "licenseUrl": "",
            "author": "",
            "placeholder": True,
        }
        thumb = info.get("thumburl") or info.get("url")
        if not thumb and override:
            thumb = override[0]
        success = False
        if thumb:
            try:
                if not destination.exists() or override:
                    normalise_portrait(fetch_bytes(thumb), destination)
                ext = info.get("extmetadata", {})
                field = lambda key: clean_html((ext.get(key) or {}).get("value"))
                entry.update(
                    {
                        "source": info.get("descriptionurl") or info.get("url") or "",
                        "license": field("LicenseShortName") or field("UsageTerms"),
                        "licenseUrl": field("LicenseUrl"),
                        "author": field("Artist") or field("Credit"),
                        "placeholder": False,
                    }
                )
                if override:
                    entry.update(
                        {
                            "source": override[1],
                            "license": "حقوق تصویر نزد منبع",
                            "licenseUrl": override[1],
                            "author": override[2],
                            "placeholder": False,
                        }
                    )
                success = True
            except Exception as error:
                print(f"portrait failed: {name}: {error}")
        if not destination.exists():
            initials = "".join(part[0] for part in name.split()[:2] if part)
            placeholder(destination, initials)
        return name, entry, success

    jobs = list(enumerate(sorted(canonical.items()), start=1))
    downloaded = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(build_one, item) for item in jobs]
        for done, future in enumerate(as_completed(futures), start=1):
            name, entry, success = future.result()
            manifest[name] = entry
            downloaded += int(success)
            if done % 20 == 0:
                print(f"processed {done}/{len(jobs)}", flush=True)

    (OUT / "portraits.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    entity_summary = build_entity_media()
    print(
        json.dumps(
            {
                "people": len(canonical),
                "wikidata": len(qids),
                "portraits": downloaded,
                "placeholders": len(canonical) - downloaded,
                **entity_summary,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
