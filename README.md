# Pilahin #PilahAjaDulu
Pilahin is an application that driving people's behaviour to sort their waste properly. This application is designed to incentivise people to sort their waste by providing rewards for proper waste sorting. 

Setting out from the problem of overcapacity of waste in Teluk Punggur landfills, the application aims to reduce the amount of waste that ends up in landfills by encouraging people to sort their waste properly.

The application allows users to track their waste sorting habits, earn points for correctly sorted waste, and redeem those points for rewards.

Rewards could be a ticket for point gambling, or a privilege for the segregated waste to be picked up.

## Project structure

```
doa-ibu-batam-hackathon/
├── requirements.txt        # top-level Python deps (venv for the whole repo)
└── src/
    ├── backend/             # FastAPI service
    │   ├── main.py / app/main.py   # entrypoint (`python -m src.backend.app.main`)
    │   ├── app/
    │   │   ├── api/routes/  # HTTP endpoints: health, users, waste, rewards, report
    │   │   ├── core/        # settings/config (env vars, e.g. LLM_PROVIDER)
    │   │   ├── schemas/     # Pydantic request/response models
    │   │   └── services/    # business logic: waste classifier, transactions,
    │   │                    # report generator, and an LLM provider abstraction
    │   │                    # (openai / claude / ollama, picked via LLM_PROVIDER)
    │   └── pipeline/        # standalone CV proof-of-concept: segment a photo of
    │                        # mixed garbage (Mask2Former) and classify each item
    │                        # (ViT waste-classifier) — wired into the backend via
    │                        # app/services/waste_classifier.py
    └── frontend/             # client apps, one per point of view (see below)
        ├── household/
        ├── waste_bank/
        └── whole/
```

Backend flow in short: a user uploads a waste photo → `waste.py` route → `waste_classifier.py`
→ `pipeline/segment_classify.py` finds and labels each item → points are awarded and
transactions recorded → `report.py` + `report_generator.py` can later summarize a user's
habits via the pluggable LLM provider.

## Planned `/frontend`

`src/frontend/` is scaffolded as several separate client apps, each built for a different
person interacting with the system rather than one app with role-based screens. All are
currently placeholders (empty `README.md` per folder) and not yet implemented.

- **`household/`** — the consumer-facing app for individual households: submit a photo of
  sorted waste, track points earned, browse and redeem rewards.
- **`waste_bank/`** — the operator app for a *bank sampah* (waste bank) / pickup staff:
  verify incoming submissions, manage pickups, and handle point payouts or redemptions on
  the collection side.
- **`whole/`** — a city/organization-wide view aggregating data across all households and
  waste banks (e.g. landfill-diversion stats, program-wide reporting) — intended for
  program admins rather than end users.

Start Backend: 
```bash
python -m src.backend.app.main
```

