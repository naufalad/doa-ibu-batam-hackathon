# ER Diagram

Source of truth: [`src/backend/app/db.py`](../src/backend/app/db.py) (SQLAlchemy Core `Table` definitions,
no ORM). Tables are created by `init_db()` at API startup.

```mermaid
erDiagram
    REGIONS ||--o{ USERS : "region_id (home region)"
    REGIONS ||--o{ WASTE_BANK_REGIONS : "covered by"
    USERS ||--o{ WASTE_BANK_REGIONS : "covers (role=waste_bank)"
    USERS ||--o{ WASTE_SUBMISSIONS : "submits (user_id)"
    USERS ||--o{ WASTE_SUBMISSIONS : "assigned via dropoff_waste_bank_id"
    USERS ||--o{ WASTE_SUBMISSIONS : "collected_by"
    WASTE_SUBMISSIONS ||--o{ WASTES : "detected objects"
    WASTES ||--|| WASTE_TOKENS : "one point-range token each"
    USERS ||--o{ REDEMPTIONS : "redeems"
    REWARDS ||--o{ REDEMPTIONS : "redeemed as"

    REGIONS {
        int id PK
        string name UK
    }

    USERS {
        int id PK
        string email UK
        string name
        bytes password_hash "pbkdf2-hmac-sha256, 600k iter"
        bytes password_salt "random 16 bytes"
        string role "user | waste_bank | authorized"
        string address "nullable"
        int region_id FK "nullable"
        int points_balance "default 0"
    }

    WASTE_BANK_REGIONS {
        int user_id PK,FK "waste_bank admin"
        int region_id PK,FK
    }

    WASTE_SUBMISSIONS {
        int id PK
        int user_id FK
        datetime created_at
        string segmented_image_path "nullable"
        string results_grid_path "nullable"
        string delivery_method "nullable: pickup | self_dropoff"
        datetime scheduled_pickup_at "nullable, pickup only"
        int dropoff_waste_bank_id FK "nullable, self_dropoff only"
        string status "pending_choice | pending_pickup | pending_dropoff | collected | dropped_off"
        int collected_by FK "nullable"
        datetime collected_at "nullable"
    }

    WASTES {
        int id PK
        int submission_id FK
        int obj_index
        string coco_label "Mask2Former segmentation label"
        float segmentation_score
        int bbox_x1
        int bbox_y1
        int bbox_x2
        int bbox_y2
        string waste_label "ViT classifier category"
        float waste_confidence
        float weight_kg "nullable"
    }

    WASTE_TOKENS {
        int id PK
        int waste_id FK,UK "one token per waste item"
        int start_range
        int end_range
        bool used "default false"
        int drawn_points "nullable until drawn"
        datetime drawn_at "nullable until drawn"
    }

    REWARDS {
        int id PK
        string title
        string description
        int cost_points
        int stock "default 0"
    }

    REDEMPTIONS {
        int id PK
        int reward_id FK
        int user_id FK
        string status "pending | fulfilled | cancelled"
    }
```

## Notes

- **`waste_bank_regions`** is a pure many-to-many join table (composite primary key, no surrogate `id`):
  a `waste_bank` admin can cover multiple regions, and a region can (in principle) have more than one
  covering admin.
- **`users` has three FKs pointing back at itself** from `waste_submissions`: the submitter (`user_id`),
  the waste bank a self-dropoff was routed to (`dropoff_waste_bank_id`), and whoever performed the
  collection/dropoff confirmation (`collected_by`, which can be a `waste_bank` or `authorized` account).
- **`wastes` is one row per detected object**, not a JSON blob on the submission — each item is
  independently segmented, classified, and (via `waste_tokens`) earns its own point-range ticket.
- **Points are lazy-credited.** A `waste_tokens` row is a "lottery ticket": `points_balance` on `users`
  only changes when the user calls `POST /waste/tokens/{id}/draw`, which atomically marks the token
  `used` and adds a random value in `[start_range, end_range]` (see
  `app/services/rewards_policy.py`) to their balance.
- **CHECK constraints enforce the enums** at the DB level: `users.role`,
  `waste_submissions.status`, and `waste_submissions.delivery_method` — see the state diagram in
  [user-journeys.md](user-journeys.md) for how `status` actually transitions.
- **`rewards` / `redemptions` are a working skeleton**: `GET /rewards` currently always returns `[]`
  (no seed/admin-create endpoint yet), but `POST /rewards/redeem` already does the full
  balance-check → deduct → decrement-stock → record-redemption transaction.
