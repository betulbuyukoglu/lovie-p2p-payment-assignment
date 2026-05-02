# Plan: P2P Payment Request API (FastAPI)

## Approach
- **Vertical slice**: Önce en küçük uçtan uca akış (create → get/list → approve/decline) çalışır hale getirilecek.
- **Correctness-first**: Ledger, state transitions ve idempotency “sonradan ek” değil, çekirdek parça olacak.
- **DB-driven**: Migration + constraint + unique index’ler, uygulama mantığını destekleyecek.

## Target Structure
Hedef proje yapısı (taslak kodda belirtilen mimari):

- `app.py`: FastAPI entrypoint, router bağlama, startup
- `core/`: `config.py`, `db.py`, `security.py`, `errors.py`
- `models/`: `user.py`, `request.py`, `ledger.py`, `payment_attempt.py`
- `schemas/`: request/response Pydantic şemaları
- `services/`: `request_service.py`, `payment_service.py`, `ledger_service.py`, `risk_service.py`, `fee_service.py`, `event_service.py`
- `api/`: `auth.py`, `requests.py`, `payments.py`
- `db/migrations/`: alembic
- `worker/expire_requests.py`
- `tests/`: unit + integration (asgari)

## Milestones

### M0 — Repo Hygiene (Done definition)
- `spec.md` ve `plan.md` mevcut.
- `requirements.txt` var ve çalıştırılabilir.
- Çalıştırma dokümantasyonu (README veya `spec.md` içerisindeki kurulum adımları) net.

### M1 — Database & Migrations
- **Alembic kurulumu**: async SQLAlchemy uyumlu.
- **Tablolar ve constraint’ler**:
  - `users(user_id unique)`
  - `requests(request_id unique, idempotency_key unique, amount>0)`
  - `payment_attempts(attempt_id unique, idempotency_key unique)`
  - `ledger(ledger_id unique, amount>0)`
- **Enum’lar**:
  - request status: `PENDING|PAID|DECLINED|EXPIRED`
  - kyc status: `VERIFIED|UNVERIFIED`
  - user status: `ACTIVE|BLOCKED`
  - ledger type: `DEBIT|CREDIT`

### M2 — Core Plumbing
- `core/config.py`: `DB_URL`, `JWT_SECRET`, `CORS_ALLOW_ORIGINS`, fee policy config.
- `core/db.py`: async engine + session factory + Base.
- `core/errors.py`: standart hata şeması + hata kodları.
- `core/security.py`: mock JWT decode/encode ve request context’e user bağlama.

### M3 — API Contract + Schemas
- `schemas/` altında:
  - Create request input / response
  - Request detail / list response
  - Approve/decline response
  - Error envelope
- Envelope standardı: `{success, data}` / `{success, error}` her route için.

### M4 — Services (Business Logic)
Servis bazlı implementasyon:
- **RequestService**
  - create: requester ↔ recipient doğrulama, expiration set, idempotency handling
  - get/list: incoming/outgoing filtreleme
  - expire: `PENDING` → `EXPIRED`
- **PaymentService**
  - approve: state check, concurrency lock, risk check, ledger write, attempt record
  - decline: state check, attempt record, status update
- **LedgerService**
  - paid işlemi için debit/credit çift kayıt (ve varsa fee)
- **RiskService**
  - baseline kurallar: blocked user, velocity/rate limit placeholder
- **FeeService**
  - config’e göre fee hesaplama ve ledger yansıtma
- **EventService**
  - outbox kaydı (opsiyonel milestone) veya no-op

### M5 — Routes
- `POST /requests`
- `GET /requests/{id}`
- `GET /requests?type=incoming|outgoing`
- `POST /requests/{id}/approve`
- `POST /requests/{id}/decline`
- `GET /healthz`

### M6 — Background Worker (Expiration)
- `worker/expire_requests.py`:
  - periyodik çalıştırma (loop + sleep veya cron uyumlu tek-shot)
  - `expires_at < now()` ve `status=PENDING` olanları `EXPIRED` yapma
- Worker idempotent olmalı (tekrar çalıştırınca tekrar iş yapmamalı).

### M7 — Tests
Minimum test paketi:
- **Unit**
  - fee calculation
  - state transition guard’ları (`approve` sadece PENDING)
  - idempotency davranışı (aynı key → aynı sonuç)
- **Integration**
  - create → approve akışı: ledger kayıtları oluşuyor mu
  - create → decline akışı
  - expire olmuş request approve edilemiyor

## Idempotency Design (Implementation Notes)
- Her idempotent endpoint için:
  - `Idempotency-Key` zorunlu hale getirilecek (veya request body’de `idempotency_key`).
  - Aynı key ile gelen isteklerde:
    - önceki response deterministik olarak dönülecek veya
    - “conflict” (farklı payload) durumunda `IDEMPOTENCY_CONFLICT` hatası verilecek.

## Error Taxonomy (Initial)
- `REQUEST_NOT_FOUND`
- `REQUEST_NOT_PENDING`
- `REQUEST_EXPIRED`
- `USER_BLOCKED`
- `KYC_NOT_VERIFIED` (opsiyonel)
- `INSUFFICIENT_FUNDS` (domain genişletilirse)
- `IDEMPOTENCY_CONFLICT`
- `VALIDATION_ERROR`

## Operational Checklist
- Env:
  - `DB_URL=postgresql+asyncpg://...`
  - `JWT_SECRET=...`
  - `CORS_ALLOW_ORIGINS=["http://localhost:3000"]`
  - Fee config (ör. `FEE_ENABLED`, `FEE_TYPE`, `FEE_VALUE`)
- Run:
  - `alembic upgrade head`
  - `uvicorn app:app --reload`
  - (opsiyonel) `python worker/expire_requests.py`

## Definition of Done
- Tüm endpoint’ler ayakta ve envelope formatı tutarlı.
- Approve/decline işlemleri concurrency-safe.
- Ledger kayıtları ödemeyi temsil ediyor ve tekrar işlem yok (idempotency).
- Expiration worker çalışıyor ve terminal state’e geçmiş request tekrar değişmiyor.
- En az 6–10 adet unit/integration test yeşil.

