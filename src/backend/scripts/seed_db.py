"""Bulk mock-data seeder, localized to Batam, for local/dev databases.

Populates every table in `app.db` (regions, users, waste_bank_regions,
waste_submissions, wastes, waste_tokens, rewards, redemptions) with
plausible, internally-consistent fake data:

  - `regions` = Batam's 12 real kecamatan (districts).
  - `users` addresses are built from real kelurahan (sub-districts) +
    street/complex names actually used around Batam.
  - `waste_label` categories line up with `app/services/rewards_policy.py`,
    and each `waste_tokens` [start_range, end_range] is derived with that
    same module so drawn points stay plausible.
  - `rewards` is a Batam-flavored catalog (pulsa, e-wallet top-ups, Barelang
    ferry vouchers, Nagoya Hill/Mega Mall vouchers, etc).
  - Every seeded user shares one known password (see --password) so you can
    log in as any of them.

Usage (from src/backend), against a local/dev DATABASE_URL only:
    python -m scripts.seed_db --reset
    python -m scripts.seed_db --users 500 --waste-bank 20 --seed 7

Never point this at a shared/production database — `--reset` truncates
every table it touches before reseeding.
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, text

from app.core.security import hash_password
from app.db import (
    get_engine,
    init_db,
    redemptions,
    regions as regions_table,
    rewards as rewards_table,
    users,
    waste_bank_regions,
    waste_submissions,
    waste_tokens,
    wastes,
)
from app.services.rewards_policy import compute_token_range

# ---------------------------------------------------------------------------
# Batam geography — 12 real kecamatan, each with a handful of real kelurahan.
# ---------------------------------------------------------------------------

BATAM_DISTRICTS: dict[str, list[str]] = {
    "Batu Ampar": ["Batu Merah", "Sungai Jodoh", "Tanjung Sengkuang", "Kampung Seraya"],
    "Lubuk Baja": ["Baloi Indah", "Batu Selicin", "Kampung Pelita", "Lubuk Baja Kota", "Tanjung Uma"],
    "Sekupang": ["Tanjung Riau", "Tiban Baru", "Tiban Indah", "Tiban Lama", "Patam Lestari", "Sungai Harapan"],
    "Nongsa": ["Batu Besar", "Kabil", "Ngenang", "Sambau"],
    "Batu Aji": ["Buliang", "Bukit Tempayan", "Kibing", "Tanjung Uncang"],
    "Sagulung": ["Sagulung Kota", "Sungai Binti", "Sungai Lekop", "Sungai Langkai", "Tembesi"],
    "Bengkong": ["Bengkong Indah", "Bengkong Laut", "Bengkong Sadai", "Tanjung Buntung"],
    "Batam Kota": ["Baloi Permai", "Belian", "Sukajadi", "Taman Baloi", "Teluk Tering", "Sungai Panas"],
    "Bulang": ["Bulang Lintang", "Pantai Gelam", "Pulau Buluh", "Pulau Setokok", "Temoyong"],
    "Galang": ["Air Raja", "Galang Baru", "Karas", "Rempang Cate", "Sembulang", "Subang Mas"],
    "Belakang Padang": ["Kasu", "Pecong", "Pemping", "Sekanak Raya", "Tanjung Sari"],
    "Sei Beduk": ["Duriangkang", "Mangsang", "Muka Kuning", "Tanjung Piayu"],
}

STREETS = [
    "Jl. Ahmad Yani", "Jl. Sudirman", "Jl. Yos Sudarso", "Jl. Engku Putri", "Jl. Raja Ali Haji",
    "Jl. R.E. Martadinata", "Jl. Laksamana Bintan", "Jl. Duyung", "Jl. Bunga Raya", "Jl. Hang Tuah",
    "Jl. Diponegoro", "Jl. Gajah Mada", "Jl. Imam Bonjol", "Jl. Sultan Abdurrahman", "Jl. Basuki Rahmat",
    "Jl. Nusantara", "Jl. Cendrawasih", "Jl. Melati", "Jl. Anggrek", "Jl. Kenanga",
    "Jl. Seraya", "Jl. Batu Besar", "Jl. Brigjen Katamso", "Jl. Sultan Iskandar Muda",
    "Perumahan Bida Ayu", "Komplek Botania", "Perumahan Taman Raja", "Villa Muka Kuning",
    "Kompleks Sukajadi Permai", "Ruko Nagoya Point", "Perum Griya Kartika Mas", "Komplek Kepri Mall",
    "Perumahan Legenda Malaka", "Komplek Anggrek Mas",
]

MALE_FIRST_NAMES = [
    "Ahmad", "Muhammad", "Budi", "Andi", "Rizky", "Dedi", "Hendra", "Agus", "Bambang", "Fajar",
    "Rian", "Yusuf", "Rahmat", "Iqbal", "Fikri", "Arif", "Wahyu", "Dimas", "Doni", "Eko",
    "Fauzan", "Hadi", "Irfan", "Joko", "Kurniawan", "Lukman", "Maulana", "Nanda", "Oki", "Putra",
    "Ridho", "Sandi", "Taufik", "Umar", "Vino", "Wira", "Yudi", "Zainal", "Herman", "Firman",
    "Gilang", "Hafiz", "Ilham", "Junaidi", "Kevin", "Leo", "Marco", "Nico", "Panji", "Reza",
    "Sutrisno", "Teguh", "Usman", "Wahid", "Yanto", "Zulkifli", "Ridwan", "Syahrul", "Tengku Aditya",
    "Raja Farhan",
]
FEMALE_FIRST_NAMES = [
    "Siti", "Nur", "Dewi", "Sri", "Ani", "Rina", "Yuni", "Fitri", "Wulan", "Ratna",
    "Indah", "Lestari", "Maya", "Nadia", "Putri", "Rani", "Sari", "Tuti", "Umi", "Vina",
    "Wati", "Yanti", "Zahra", "Amelia", "Bella", "Citra", "Dian", "Eka", "Fani", "Gita",
    "Hana", "Intan", "Julia", "Kartika", "Lina", "Mira", "Nita", "Okta", "Prita", "Ratih",
    "Suci", "Tia", "Ulfa", "Vera", "Winda", "Yasmin", "Aisyah", "Bunga", "Cahaya", "Diah",
    "Ella", "Farah", "Ghina", "Hasna", "Ika", "Jihan", "Karin", "Laila", "Melati", "Nabila",
    "Tengku Aisyah", "Raja Salsabila",
]
SURNAMES = [
    "Pratama", "Saputra", "Wijaya", "Santoso", "Kurniawan", "Hidayat", "Nasution", "Siregar",
    "Simanjuntak", "Sitompul", "Harahap", "Tampubolon", "Panjaitan", "Batubara", "Lubis",
    "Hutagalung", "Rangkuti", "Ramadhan", "Firdaus", "Setiawan", "Gunawan", "Halim", "Susanto",
    "Tanoto", "Wibowo", "Suryadi", "Utama", "Al Rasyid", "Sagala", "Sinaga", "Tan", "Lim",
    "Kusuma", "Salim", "Widjaja", "Setiadi", "Ongko", "Hartono", "Chandra", "Kusnadi", "Yamin",
    "Effendi", "Syahputra", "Anggraini", "Damanik", "Purnama", "Wahyudi", "Rachman", "Zulfikar",
]
EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "yahoo.co.id", "outlook.com", "icloud.com"]

# waste_label categories mirror app/services/rewards_policy.py's keys, each
# mapped to plausible COCO detections + a realistic per-item weight range.
CATEGORY_PROFILE: dict[str, dict] = {
    "plastic": {
        "weight": 6, "coco": ["bottle", "cup", "bowl", "handbag", "backpack", "suitcase", "umbrella", "toothbrush"],
        "kg": (0.02, 1.5),
    },
    "paper": {
        "weight": 5, "coco": ["book", "cup"], "kg": (0.05, 2.0),
    },
    "glass": {
        "weight": 2, "coco": ["wine glass", "vase", "bottle"], "kg": (0.1, 3.0),
    },
    "metal": {
        "weight": 3, "coco": ["fork", "knife", "spoon", "scissors"], "kg": (0.05, 5.0),
    },
    "battery": {
        "weight": 1, "coco": ["cell phone", "remote", "mouse", "keyboard", "laptop", "hair drier", "tv"],
        "kg": (0.01, 0.3),
    },
    "organic": {
        "weight": 5, "coco": ["banana", "apple", "orange", "sandwich", "broccoli", "carrot", "hot dog", "pizza",
                               "donut", "cake", "potted plant"],
        "kg": (0.05, 3.0),
    },
}
CATEGORIES = list(CATEGORY_PROFILE)
CATEGORY_WEIGHTS = [CATEGORY_PROFILE[c]["weight"] for c in CATEGORIES]

REWARDS_CATALOG = [
    ("Pulsa Telkomsel 10rb", "Voucher isi ulang pulsa Telkomsel senilai Rp10.000.", 100, 200),
    ("Pulsa Indosat 10rb", "Voucher isi ulang pulsa Indosat Ooredoo senilai Rp10.000.", 100, 200),
    ("Saldo GoPay 20rb", "Top-up saldo GoPay senilai Rp20.000.", 180, 150),
    ("Saldo OVO 20rb", "Top-up saldo OVO senilai Rp20.000.", 180, 150),
    ("Saldo DANA 20rb", "Top-up saldo DANA senilai Rp20.000.", 180, 150),
    ("Saldo ShopeePay 20rb", "Top-up saldo ShopeePay senilai Rp20.000.", 180, 150),
    ("Voucher Indomaret 25rb", "Voucher belanja Indomaret se-Batam senilai Rp25.000.", 220, 120),
    ("Voucher Alfamart 25rb", "Voucher belanja Alfamart se-Batam senilai Rp25.000.", 220, 120),
    ("Paket Sembako Mini", "Beras 2kg + minyak goreng 1L, diambil di bank sampah setempat.", 500, 60),
    ("Minyak Goreng 1 Liter", "Minyak goreng kemasan 1 liter.", 250, 80),
    ("Beras Lokal 5kg", "Beras lokal Kepri kemasan 5kg.", 600, 50),
    ("Tumbler Pilahin", "Tumbler stainless ramah lingkungan bertuliskan #PilahAjaDulu.", 350, 100),
    ("Tas Belanja Ramah Lingkungan", "Tote bag kanvas pengganti kantong plastik.", 150, 150),
    ("Payung Lipat Pilahin", "Payung lipat dengan logo Pilahin.", 400, 70),
    ("Kupon BBM Pertalite 1L", "Kupon penukaran BBM Pertalite 1 liter di SPBU rekanan Batam.", 300, 90),
    ("Voucher Feri Batam Centre - HarbourBay", "Potongan tiket feri domestik rute Batam Centre - HarbourBay.", 450, 40),
    ("Tiket Masuk Ocarina Batam", "Tiket masuk kawasan kuliner & hiburan Ocarina Batam Centre.", 400, 60),
    ("Voucher Nagoya Hill 50rb", "Voucher belanja Mall Nagoya Hill senilai Rp50.000.", 550, 40),
    ("Voucher Mega Mall Batam Centre 50rb", "Voucher belanja Mega Mall Batam Centre senilai Rp50.000.", 550, 40),
    ("Kaos Pilahin Edisi Terbatas", "Kaos katun edisi terbatas #PilahAjaDulu.", 480, 60),
    ("Kompos Organik 5kg", "Pupuk kompos organik hasil olahan sampah, kemasan 5kg.", 200, 100),
    ("Bibit Cabai Rawit", "Paket bibit cabai rawit untuk ditanam di rumah.", 80, 200),
    ("Stiker Pilahin", "Stiker vinyl edisi #PilahAjaDulu.", 20, 300),
    ("Pin Emblem Pilahin", "Pin emblem logam #PilahAjaDulu.", 30, 250),
    ("Permen Kemasan Kecil", "Sekantong permen kemasan kecil.", 25, 300),
    ("Voucher Parkir Gratis", "Voucher parkir gratis 1x di kawasan Nagoya/Baloi.", 40, 180),
    ("Sabun Cuci Tangan Herbal", "Sabun cuci tangan herbal ramah lingkungan.", 120, 150),
    ("Detergen Ramah Lingkungan 1kg", "Detergen biodegradable kemasan 1kg.", 260, 90),
    ("Masker Kain Tenun Melayu", "Masker kain motif tenun Melayu Riau.", 140, 120),
    ("Voucher Potong Rambut", "Voucher potong rambut di barbershop rekanan.", 300, 60),
    ("Voucher Cuci Motor", "Voucher cuci motor di gerai rekanan se-Batam.", 250, 70),
    ("Gift Card Pilahin 100rb", "Gift card senilai Rp100.000, berlaku di merchant rekanan.", 900, 30),
    ("Sepeda Lipat Pilahin", "Sepeda lipat — hadiah utama program #PilahAjaDulu.", 8000, 5),
    ("Smartphone Entry-Level", "Smartphone entry-level — hadiah utama program #PilahAjaDulu.", 15000, 3),
]


def slugify_name(name: str) -> str:
    return "".join(ch for ch in name.lower().replace(" ", ".") if ch.isalnum() or ch == ".")


def unique_email(name: str, used: set[str], rng: random.Random) -> str:
    base = slugify_name(name)
    domain = rng.choice(EMAIL_DOMAINS)
    candidate = f"{base}@{domain}"
    n = 1
    while candidate in used:
        n += 1
        candidate = f"{base}{n}@{domain}"
    used.add(candidate)
    return candidate


def random_datetime(rng: random.Random, start: datetime, end: datetime) -> datetime:
    delta = end - start
    seconds = rng.uniform(0, delta.total_seconds())
    return start + timedelta(seconds=seconds)


def build_address(rng: random.Random, district: str) -> str:
    kelurahan = rng.choice(BATAM_DISTRICTS[district])
    street = rng.choice(STREETS)
    number = rng.randint(1, 199)
    rt = rng.randint(1, 12)
    rw = rng.randint(1, 8)
    return f"{street} No. {number}, RT {rt:02d}/RW {rw:02d}, Kel. {kelurahan}, Kec. {district}, Batam, Kepri"


def make_person_name(rng: random.Random) -> str:
    if rng.random() < 0.5:
        first = rng.choice(MALE_FIRST_NAMES)
    else:
        first = rng.choice(FEMALE_FIRST_NAMES)
    return f"{first} {rng.choice(SURNAMES)}"


def reset_all_tables(conn) -> None:
    conn.execute(
        text(
            "TRUNCATE TABLE redemptions, waste_tokens, wastes, waste_submissions, "
            "waste_bank_regions, rewards, users, regions RESTART IDENTITY CASCADE"
        )
    )


def chunked(rows: list[dict], size: int = 500):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--users", type=int, default=250, help="Number of role='user' accounts (default: 250)")
    parser.add_argument("--waste-bank", type=int, default=16, help="Number of waste_bank admins (default: 16)")
    parser.add_argument("--authorized", type=int, default=3, help="Number of authorized admins (default: 3)")
    parser.add_argument("--password", default="Password123!", help="Shared password for every seeded account")
    parser.add_argument("--seed", type=int, default=42, help="Random seed, for reproducible output")
    parser.add_argument(
        "--reset", action="store_true", help="TRUNCATE every table before seeding (destructive, local/dev only!)"
    )
    args = parser.parse_args()

    engine = get_engine()
    db_url = engine.url.render_as_string(hide_password=True)
    print(f"Target database: {db_url}")
    if not args.reset:
        confirm = input(
            "This will INSERT a large volume of mock data into the above database. "
            "Continue? [y/N] "
        )
        if confirm.strip().lower() != "y":
            print("Aborted.")
            return

    rng = random.Random(args.seed)
    init_db()

    now = datetime.now(timezone.utc)
    earliest = now - timedelta(days=270)

    password_hash, password_salt = hash_password(args.password)

    with engine.begin() as conn:
        if args.reset:
            print("Resetting (TRUNCATE ... RESTART IDENTITY CASCADE) ...")
            reset_all_tables(conn)

        # -- regions -----------------------------------------------------
        district_names = list(BATAM_DISTRICTS)
        region_rows = conn.execute(
            insert(regions_table).returning(regions_table.c.id, regions_table.c.name),
            [{"name": name} for name in district_names],
        ).all()
        region_id_by_name = {name: rid for rid, name in region_rows}
        region_ids = list(region_id_by_name.values())
        print(f"regions: {len(region_ids)}")

        # -- authorized admins --------------------------------------------
        used_emails: set[str] = set()
        authorized_rows = []
        for i in range(args.authorized):
            name = make_person_name(rng) if i > 0 else "Ops Admin Pilahin"
            email = f"admin{i + 1}@pilahin.id" if i > 0 else "admin@pilahin.id"
            used_emails.add(email)
            authorized_rows.append(
                {
                    "email": email,
                    "name": name,
                    "password_hash": password_hash,
                    "password_salt": password_salt,
                    "role": "authorized",
                    "address": None,
                    "region_id": None,
                }
            )
        authorized_ids = [
            row[0]
            for row in conn.execute(insert(users).returning(users.c.id), authorized_rows).all()
        ]
        print(f"users (authorized): {len(authorized_ids)}")

        # -- waste_bank admins, 1-3 regions each --------------------------
        waste_bank_rows = []
        wb_region_links: list[dict] = []
        for i in range(args.waste_bank):
            name = f"Bank Sampah {rng.choice(district_names)} - {make_person_name(rng)}"
            email = unique_email(f"wastebank{i + 1}.{name}", used_emails, rng)
            waste_bank_rows.append(
                {
                    "email": email,
                    "name": name,
                    "password_hash": password_hash,
                    "password_salt": password_salt,
                    "role": "waste_bank",
                    "address": None,
                    "region_id": None,
                }
            )
        waste_bank_ids = [
            row[0]
            for row in conn.execute(insert(users).returning(users.c.id), waste_bank_rows).all()
        ]
        # Guarantee every region has at least one covering waste_bank admin,
        # then hand out 0-2 extra regions on top.
        region_to_waste_banks: dict[int, list[int]] = {rid: [] for rid in region_ids}
        for idx, wb_id in enumerate(waste_bank_ids):
            primary_region = region_ids[idx % len(region_ids)]
            covered = {primary_region}
            for _ in range(rng.randint(0, 2)):
                covered.add(rng.choice(region_ids))
            for rid in covered:
                wb_region_links.append({"user_id": wb_id, "region_id": rid})
                region_to_waste_banks[rid].append(wb_id)
        if wb_region_links:
            conn.execute(insert(waste_bank_regions), wb_region_links)
        # Any region nobody landed on falls back to a random admin.
        for rid, covering in region_to_waste_banks.items():
            if not covering and waste_bank_ids:
                wb_id = rng.choice(waste_bank_ids)
                conn.execute(insert(waste_bank_regions).values(user_id=wb_id, region_id=rid))
                region_to_waste_banks[rid].append(wb_id)
        print(f"users (waste_bank): {len(waste_bank_ids)}")

        # -- regular users --------------------------------------------------
        regular_rows = []
        regular_region_ids: list[int | None] = []
        for _ in range(args.users):
            name = make_person_name(rng)
            email = unique_email(name, used_emails, rng)
            has_region = rng.random() > 0.05  # ~5% incomplete profiles
            district = rng.choice(district_names) if has_region else None
            region_id = region_id_by_name[district] if district else None
            address = build_address(rng, district) if district else None
            regular_rows.append(
                {
                    "email": email,
                    "name": name,
                    "password_hash": password_hash,
                    "password_salt": password_salt,
                    "role": "user",
                    "address": address,
                    "region_id": region_id,
                }
            )
            regular_region_ids.append(region_id)
        regular_ids = [
            row[0]
            for row in conn.execute(insert(users).returning(users.c.id), regular_rows).all()
        ]
        print(f"users (regular): {len(regular_ids)}")

        # -- rewards ----------------------------------------------------
        reward_rows = conn.execute(
            insert(rewards_table).returning(rewards_table.c.id, rewards_table.c.cost_points, rewards_table.c.stock),
            [
                {"title": title, "description": desc, "cost_points": cost, "stock": stock}
                for title, desc, cost, stock in REWARDS_CATALOG
            ],
        ).all()
        print(f"rewards: {len(reward_rows)}")

        # -- waste_submissions + wastes + waste_tokens -------------------
        submission_rows: list[dict] = []
        submission_meta: list[dict] = []  # parallel list: {user_id, region_id, created_at}
        for user_id, region_id in zip(regular_ids, regular_region_ids):
            num_submissions = rng.choices(
                [0, 1, 2, 3, 4, 5, 6, 7], weights=[5, 15, 20, 20, 15, 10, 8, 7]
            )[0]
            for _ in range(num_submissions):
                created_at = random_datetime(rng, earliest, now)
                age_days = (now - created_at).days
                collected_prob = 0.8 if age_days > 14 else 0.3
                status = "collected" if rng.random() < collected_prob else "pending_pickup"
                submission_meta.append({"user_id": user_id, "region_id": region_id, "created_at": created_at, "status": status})

        submission_ids: list[int] = []
        for batch in chunked(
            [
                {
                    "user_id": m["user_id"],
                    "created_at": m["created_at"],
                    "segmented_image_path": None,
                    "results_grid_path": None,
                    # Synthetic data always models the pickup flow — it
                    # already skips straight past "pending_choice".
                    "delivery_method": "pickup",
                    "status": m["status"],
                    "collected_by": None,
                    "collected_at": None,
                }
                for m in submission_meta
            ]
        ):
            rows = conn.execute(insert(waste_submissions).returning(waste_submissions.c.id), batch).all()
            submission_ids.extend(r[0] for r in rows)

        # Fill in collected_by/collected_at for collected submissions, batched.
        collect_updates = []
        for sub_id, meta in zip(submission_ids, submission_meta):
            if meta["status"] != "collected":
                continue
            candidates = region_to_waste_banks.get(meta["region_id"]) or []
            collector = rng.choice(candidates) if candidates and rng.random() < 0.85 else rng.choice(authorized_ids)
            collected_at = meta["created_at"] + timedelta(hours=rng.uniform(2, 96))
            if collected_at > now:
                collected_at = now
            collect_updates.append({"sub_id": sub_id, "collected_by": collector, "collected_at": collected_at})

        if collect_updates:
            from sqlalchemy import bindparam, update

            stmt = (
                update(waste_submissions)
                .where(waste_submissions.c.id == bindparam("sub_id"))
                .values(collected_by=bindparam("collected_by"), collected_at=bindparam("collected_at"))
            )
            for batch in chunked(collect_updates):
                conn.execute(stmt, batch)

        print(f"waste_submissions: {len(submission_ids)}")

        waste_rows: list[dict] = []
        waste_meta: list[dict] = []  # {submission_created_at}
        for sub_id, meta in zip(submission_ids, submission_meta):
            num_objects = rng.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]
            for obj_index in range(num_objects):
                category = rng.choices(CATEGORIES, weights=CATEGORY_WEIGHTS)[0]
                profile = CATEGORY_PROFILE[category]
                coco_label = rng.choice(profile["coco"])
                lo, hi = profile["kg"]
                weight_kg = round(rng.uniform(lo, hi), 3)
                img_w, img_h = 800, 600
                x1 = rng.randint(0, img_w - 60)
                y1 = rng.randint(0, img_h - 60)
                x2 = min(img_w, x1 + rng.randint(40, 250))
                y2 = min(img_h, y1 + rng.randint(40, 250))
                waste_rows.append(
                    {
                        "submission_id": sub_id,
                        "obj_index": obj_index,
                        "coco_label": coco_label,
                        "segmentation_score": round(rng.uniform(0.55, 0.98), 4),
                        "bbox_x1": x1,
                        "bbox_y1": y1,
                        "bbox_x2": x2,
                        "bbox_y2": y2,
                        "waste_label": category,
                        "waste_confidence": round(rng.uniform(0.5, 0.99), 4),
                        "weight_kg": weight_kg,
                    }
                )
                waste_meta.append({"created_at": meta["created_at"]})

        waste_ids: list[int] = []
        for batch in chunked(waste_rows):
            rows = conn.execute(insert(wastes).returning(wastes.c.id), batch).all()
            waste_ids.extend(r[0] for r in rows)
        print(f"wastes: {len(waste_ids)}")

        token_rows: list[dict] = []
        user_points: dict[int, int] = {uid: 0 for uid in regular_ids}
        sub_owner_by_id = {sid: meta["user_id"] for sid, meta in zip(submission_ids, submission_meta)}
        waste_owner_sub = [wr["submission_id"] for wr in waste_rows]

        for waste_id, wr, wm, owner_sub in zip(waste_ids, waste_rows, waste_meta, waste_owner_sub):
            start_range, end_range = compute_token_range(wr["waste_label"], wr["weight_kg"], wr["waste_confidence"])
            used = rng.random() < 0.55
            drawn_points = None
            drawn_at = None
            if used:
                drawn_points = rng.randint(start_range, end_range)
                drawn_at = wm["created_at"] + timedelta(hours=rng.uniform(0, 48))
                if drawn_at > now:
                    drawn_at = now
                user_points[sub_owner_by_id[owner_sub]] += drawn_points
            token_rows.append(
                {
                    "waste_id": waste_id,
                    "start_range": start_range,
                    "end_range": end_range,
                    "used": used,
                    "drawn_points": drawn_points,
                    "drawn_at": drawn_at,
                }
            )

        for batch in chunked(token_rows):
            conn.execute(insert(waste_tokens), batch)
        print(f"waste_tokens: {len(token_rows)}")

        # -- redemptions --------------------------------------------------
        redemption_rows = []
        reward_stock = {rid: stock for rid, _cost, stock in reward_rows}
        reward_cost = {rid: cost for rid, cost, _stock in reward_rows}
        reward_ids = [rid for rid, _cost, _stock in reward_rows]

        spending_candidates = [uid for uid, pts in user_points.items() if pts > 0]
        rng.shuffle(spending_candidates)
        for uid in spending_candidates:
            remaining = user_points[uid]
            affordable = [rid for rid in reward_ids if reward_cost[rid] <= remaining and reward_stock[rid] > 0]
            attempts = 0
            while affordable and remaining > 0 and attempts < 6:
                attempts += 1
                reward_id = rng.choice(affordable)
                cost = reward_cost[reward_id]
                if cost > remaining or reward_stock[reward_id] <= 0:
                    affordable = [rid for rid in reward_ids if reward_cost[rid] <= remaining and reward_stock[rid] > 0]
                    continue
                status = rng.choices(["pending", "fulfilled", "cancelled"], weights=[30, 60, 10])[0]
                redemption_rows.append({"reward_id": reward_id, "user_id": uid, "status": status})
                reward_stock[reward_id] -= 1
                if status != "cancelled":
                    remaining -= cost
                if rng.random() < 0.3:
                    break
                affordable = [rid for rid in reward_ids if reward_cost[rid] <= remaining and reward_stock[rid] > 0]
            user_points[uid] = remaining

        for batch in chunked(redemption_rows):
            conn.execute(insert(redemptions), batch)
        print(f"redemptions: {len(redemption_rows)}")

        # -- final points_balance + reward stock -------------------------
        from sqlalchemy import bindparam, update

        balance_updates = [{"uid": uid, "bal": max(pts, 0)} for uid, pts in user_points.items()]
        stmt = update(users).where(users.c.id == bindparam("uid")).values(points_balance=bindparam("bal"))
        for batch in chunked(balance_updates):
            conn.execute(stmt, batch)

        stock_updates = [{"rid": rid, "stock": stock} for rid, stock in reward_stock.items()]
        stmt = update(rewards_table).where(rewards_table.c.id == bindparam("rid")).values(stock=bindparam("stock"))
        for batch in chunked(stock_updates):
            conn.execute(stmt, batch)

    print("\nDone.")
    print(f"All seeded accounts share the password: {args.password!r}")
    print(f"Sample login: {regular_rows[0]['email']!r} / {args.password!r}" if regular_rows else "")


if __name__ == "__main__":
    main()
