# Flowcharts & User Journeys

Pilahin has three account roles, enforced via `role` on `users` (`app/api/deps.py::require_roles`):

| Role | Who | Provisioned by |
|---|---|---|
| `user` | Household / individual submitting waste | Public self-signup (`POST /users`) |
| `waste_bank` | *Bank sampah* operator / pickup staff, scoped to one or more regions | An `authorized` account (`POST /users/waste-bank-admins`) |
| `authorized` | Program admin, city/organization-wide oversight | Bootstrapped out-of-band (`scripts/create_admin.py`) |

Maps to the three planned frontends: `src/frontend/household`, `src/frontend/waste_bank`, `src/frontend/whole`.

## Submission lifecycle (all roles touch this)

Every waste submission moves through one status machine, enforced by a DB `CHECK` constraint on
`waste_submissions.status`:

```mermaid
stateDiagram-v2
    [*] --> pending_choice: user uploads photo\nPOST /waste/submit\n(segmentation + classification,\ntokens issued)
    pending_choice --> pending_pickup: user picks "pickup"\nPOST /waste/submissions/{id}/delivery-method
    pending_choice --> pending_dropoff: user picks "self_dropoff"
    pending_pickup --> collected: waste_bank/authorized\nPOST /waste/pickups/{id}/collect
    pending_dropoff --> dropped_off: intake system confirms\nPOST /waste/dropoffs/{id}/confirm
    collected --> [*]
    dropped_off --> [*]
```

## 1. User (household) journey

```mermaid
flowchart TD
    A[Sign up\nPOST /users] --> B[Log in\nPOST /auth/login → JWT]
    B --> C[Upload sorted-waste photo\nPOST /waste/submit]
    C --> D[Mask2Former segments objects,\nViT classifier labels each one]
    D --> E[Each object gets a\npoint-range token]
    E --> F{Choose delivery method\nPOST /waste/submissions/id/delivery-method}
    F -->|pickup| G[Shown next day's\ncollection slot]
    F -->|self_dropoff| H[Shown nearest waste_bank\ncovering their region]
    G --> I[Wait for waste_bank\nto collect]
    H --> J[Physically drop off\nat that waste_bank]
    E --> K["Draw token(s)\nPOST /waste/tokens/id/draw"]
    K --> L[Points credited to\npoints_balance]
    L --> M[Browse reward catalog\nGET /rewards]
    M --> N[Redeem points\nPOST /rewards/redeem]
    L --> O[Review own submission history\nGET /waste/history]
    L --> P[Read AI-generated activity report\nGET /report/id]
```

Note: as implemented, drawing a token (`K`) isn't gated on the submission actually being collected or
dropped off — it only checks that the caller owns the token. So a user can draw their points as soon as
a submission is scored, independent of where steps `G`–`J` are in progress.

## 2. Waste bank (operator) journey

```mermaid
flowchart TD
    A[Account provisioned by an\nauthorized admin, scoped to\none or more regions\nPOST /users/waste-bank-admins] --> B[Log in\nPOST /auth/login\nJWT bakes in region_ids]
    B --> C["View pickups awaiting collection\nin my region(s)\nGET /waste/pickups"]
    C --> D[Go collect the waste\nin person]
    D --> E[Mark it collected\nPOST /waste/pickups/id/collect]
    B --> F[Self-dropoff user arrives\nat my location]
    F --> G[Intake system confirms drop-off\nPOST /waste/dropoffs/id/confirm]
    B --> H["Review full submission history\nfor my region(s)\nGET /waste/history"]
```

`GET /waste/dropoffs/{id}/confirm` is meant to be triggered automatically by an intake device (e.g. a
QR/badge scan at the bin), not clicked manually by staff — see the docstring on
`confirm_dropoff` in [`app/api/routes/waste.py`](../src/backend/app/api/routes/waste.py).

## 3. Authorized (program admin) journey

```mermaid
flowchart TD
    A[Log in\nPOST /auth/login] --> B[Create regions\nPOST /regions]
    B --> C["Provision waste_bank admins,\nassign to region(s)\nPOST /users/waste-bank-admins"]
    A --> D[Monitor pickups city-wide,\noptional ?region_id= filter\nGET /waste/pickups]
    A --> E[Monitor full history,\nfilter by region / user / status\nGET /waste/history]
    A --> F[Can also collect / confirm\non behalf of any region\nPOST /waste/pickups/id/collect\nPOST /waste/dropoffs/id/confirm]
    A --> G[Look up any user's profile\nGET /users/id]
```

`authorized` is a superset of `waste_bank`'s permissions on the waste workflow (unscoped by region),
plus the only role that can create regions and provision `waste_bank` accounts.
