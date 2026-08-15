# Pilahin #PilahAjaDulu
Pilahin is an application that driving people's behaviour to sort their waste properly. This application is designed to incentivise people to sort their waste by providing rewards for proper waste sorting. 

The application allows users to track their waste sorting habits, earn points for correctly sorted waste, and redeem those points for rewards.

Rewards could be a ticket for point gambling, or a privilege for the segregated waste to be picked up.

## Problem statement

Teluk Punggur, Batam's main landfill, is running over capacity because household waste isn't sorted
before disposal. Pilahin targets the root behavior — it incentivizes people to sort their waste
properly at the source, so less of it ends up in landfill in the first place.

## Links

| | |
|---|---|
| **GitHub repo** | https://github.com/naufalad/doa-ibu-batam-hackathon |
| **Application link** | _[PLACEHOLDER — fill in once deployed to Render]_ |
| **Pitch video** | _[PLACEHOLDER — fill in]_ |
| **Pitch slide deck** | _[PLACEHOLDER — fill in]_ |

## Documentation

See [`/docs`](docs/) for the ER diagram, user journeys/flowcharts per role, software architecture &
tech stack (Render + Supabase deployment), full API endpoint list, and AI-tool/team disclaimers:

- [ER diagram](docs/er-diagram.md)
- [Flowcharts & user journeys](docs/user-journeys.md)
- [Software architecture & tech stack](docs/architecture.md)
- [API endpoints](docs/api-endpoints.md)
- [Disclaimer: AI tools, group & members](docs/disclaimer.md)
- [Outstanding work](docs/todo.md)

## Project structure

```
doa-ibu-batam-hackathon/
└── src/
    ├── backend/             # FastAPI service — self-contained: main.py +
    │   │                    # requirements.txt + app/ all live here and
    │   │                    # resolve relative to this directory, so it
    │   │                    # doubles as the Vercel project root.
    │   ├── main.py           # app factory + entrypoint (`python main.py`,
    │   │                     # or `uvicorn main:app`, run from src/backend)
    │   ├── requirements.txt
    │   ├── app/
    │   │   ├── api/routes/  # HTTP endpoints: health, users, waste, rewards, report
    │   │   ├── core/        # settings/config (env vars, e.g. LLM_PROVIDER)
    │   │   ├── schemas/     # Pydantic request/response models
    │   │   └── services/    # business logic: waste classifier, pickup-slot
    │   │                    # scheduler, rewards/points policy, transactions,
    │   │                    # report generator, and an LLM provider abstraction
    │   │                    # (openai / claude / ollama, picked via LLM_PROVIDER)
    │   └── pipeline/        # standalone CV proof-of-concept: segment a photo of
    │                        # mixed garbage (Mask2Former) and classify each item
    │                        # (ViT waste-classifier) — wired into the backend via
    │                        # app/services/waste_classifier.py
    └── frontend/             # client apps, one per point of view (see below)
        ├── household/
        ├── waste_bank/
        └── municipal/
```

Backend flow in short: a user uploads a waste photo → `waste.py` route → `waste_classifier.py`
→ `pipeline/segment_classify.py` finds and labels each item → each item gets a point-range
token (`rewards_policy.py`, weighted by the classifier's confidence) and the submission sits
at status `pending_choice` until the user picks a delivery method via
`POST /waste/submissions/{id}/delivery-method`: `pickup` schedules the next collection round
(`pickup_scheduler.py`) for a waste_bank to collect, `self_dropoff` points them to the nearest
waste_bank to hand it to directly. Once the token is drawn, points are credited and
transactions recorded → `report.py` + `report_generator.py` can later summarize a user's
habits via the pluggable LLM provider.

## Planned `/frontend`

`src/frontend/` is scaffolded as several separate client apps, each built for a different
person interacting with the system rather than one app with role-based screens.

- **`household/`** — the consumer-facing app for individual households: submit a photo of
  sorted waste, track points earned, browse and redeem rewards. Still a placeholder
  (empty `README.md`), not yet implemented.
- **`waste_bank/`** — the operator app for a *bank sampah* (waste bank) / pickup staff:
  verify incoming submissions, manage pickups/dropoffs, and handle point payouts or
  redemptions on the collection side. Still a placeholder (empty `README.md`), not yet
  implemented.
- **`municipal/`** — a city/organization-wide view aggregating data across all households and
  waste banks (e.g. landfill-diversion stats, program-wide reporting), for program admins
  rather than end users. Renamed from the earlier `whole/` placeholder; has a first working
  `index.html` prototype.

Start Backend (from `src/backend`):
```bash
cd src/backend
python main.py           # dev, auto-reload
# or: uvicorn main:app --reload
```

