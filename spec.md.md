# Spec: P2P Payment Request API (FastAPI)

## Summary
Bu proje, iki kullanıcı arasında **para talebi (payment request)** oluşturma ve alıcının bu talebi **onaylayarak ödeme** veya **reddetme** işlemlerini yöneten bir backend API’sidir. Sistem; **idempotency**, **audit/ledger tabanlı finansal doğruluk**, **concurrency güvenliği** ve **temel risk kontrolleri** hedefleriyle tasarlanır.

## Goals
- **Payment request yaşam döngüsü**: `PENDING → PAID | DECLINED | EXPIRED`.
- **İşlem güvenliği**: Atomic transaction + gerekli yerlerde kilitleme (pessimistic lock / `FOR UPDATE`).
- **Finansal doğruluk**: Nihai doğruluk kaynağı (source of truth) olarak **ledger** kayıtları.
- **İdempotent API**: Tekrarlanan isteklerde aynı sonucu döndürme (özellikle create/approve/decline).
- **Gözlemlenebilirlik**: Standardize hata formatı, audit ve (tasarım olarak) event üretimi.

## Non-goals
- Tam kapsamlı ödeme altyapısı entegrasyonu (bankalar, kart ağları, 3DS vb.).
- Gelişmiş KYC/AML orkestrasyonu (yalnızca alan/saha bilgisi olarak ele alınır).
- Üretim seviyesi kimlik doğrulama/otorizasyon (bu ödev için “mock/hard auth” yeterlidir).

## Users & Actors
- **Requester**: Para talebini oluşturan kullanıcı.
- **Recipient**: Talebi alan ve onaylayıp ödeyen veya reddeden kullanıcı.
- **System account**: Ücret (fee) vb. sistem işlemlerinin karşı hesabı (seed ile oluşturulması varsayılır).

## Domain Model

### Entities (logical)
- **User**
  - `user_id` (UUID, unique)
  - `kyc_status`: `VERIFIED | UNVERIFIED`
  - `status`: `ACTIVE | BLOCKED`
- **Request**
  - `request_id` (UUID, unique)
  - `requester_user_id`, `recipient_user_id`
  - `amount` (> 0), `currency`
  - `status`: `PENDING | PAID | DECLINED | EXPIRED`
  - `idempotency_key` (unique)
  - `expires_at`, `created_at`
- **PaymentAttempt**
  - `attempt_id` (UUID, unique)
  - `request_id`
  - `action_type`: `APPROVE | DECLINE`
  - `status`: `SUCCESS | FAILED | BLOCKED`
  - `failure_reason`
  - `idempotency_key` (unique)
  - `created_at`
- **Ledger**
  - `ledger_id` (UUID, unique)
  - `user_id`, `request_id`
  - `type`: `DEBIT | CREDIT`
  - `amount` (> 0)
  - `created_at`

### Invariants
- `amount` daima pozitif olmalıdır.
- `request.status` terminal durumlara geçtiğinde tekrar `PENDING` olamaz.
- `PAID` olan bir request için ledger kayıtları oluşmuş olmalıdır.
- Aynı `idempotency_key` ile tekrarlanan çağrılar **aynı sonucu** üretmelidir.

## API

### Conventions
- JSON response envelope:
  - Başarılı: `{ "success": true, "data": ... }`
  - Hata: `{ "success": false, "error": { "code": "...", "message": "...", "details": {} } }`
- Idempotency:
  - Uygulanacak endpoint’ler: create request, approve, decline.
  - İstemci `Idempotency-Key` header’ı veya request body alanı ile gönderir (uygulama kararı).

### Endpoints
- **POST `/requests`**
  - Amaç: Yeni para talebi oluştur.
  - Input: `recipient_user_id`, `amount`, `currency`
  - Output: `request_id`, `status=PENDING`, `expires_at`, `created_at`
- **GET `/requests/{id}`**
  - Amaç: Tekil talep getir.
- **GET `/requests?type=incoming|outgoing`**
  - Amaç: Gelen/giden talepleri listele.
- **POST `/requests/{id}/approve`**
  - Amaç: Talebi onayla ve ödemeyi gerçekleştir.
  - Side effects: Ledger kayıtları + request status update + payment attempt kaydı.
- **POST `/requests/{id}/decline`**
  - Amaç: Talebi reddet.
  - Side effects: request status update + payment attempt kaydı.
- **GET `/healthz`**
  - Amaç: Sistem sağlık kontrolü.

## Business Rules
- **Expiration**
  - `expires_at` dolunca `PENDING` durumundaki talepler `EXPIRED` olur.
  - Gerçekleştirme: Worker/cron ile periyodik tarama.
- **Risk & Fraud (baseline)**
  - Kural tabanlı minimum kontroller: hız/limit/rate limit, `BLOCKED` kullanıcı kısıtları.
  - `UNVERIFIED` KYC için ek kısıtlar proje ihtiyacına göre (varsayılan: read-only bilgi).
- **Fee (policy-driven)**
  - Ücretin sabit/yüzde/opsiyonel oluşu **config** ile yönetilir.
  - Fee uygulanırsa ledger üzerinde sistem hesabına uygun kredi/debit kayıtları oluşur.

## Architecture

### High-level
- **FastAPI** HTTP API
- **PostgreSQL** veri katmanı
- **SQLAlchemy (async)** ORM + transaction yönetimi
- **Alembic** migration

### Layering (target)
- `api/`: route/controller
- `services/`: iş mantığı (RequestService, PaymentService, LedgerService, RiskService, FeeService, EventService)
- `models/`: ORM entity’ler
- `schemas/`: Pydantic request/response şemaları
- `core/`: config, db, security, error types
- `worker/`: expiration task

### Concurrency & Consistency
- Onay/ödeme akışında aynı request’e eşzamanlı işlemlere karşı:
  - request satırını `SELECT ... FOR UPDATE` ile kilitleme
  - tek seferlik state transition (PENDING’den çıkış)

## Events (Design)
- Önerilen: Outbox pattern
  - DB’de event kaydı (transaction içinde)
  - Ayrı worker publish eder
- Bu ödev kapsamında event yayınlama “tasarım kararı” olarak dokümante edilir.

## Security & Privacy
- **Auth**: JWT (mock/hard auth), en azından kullanıcı kimliği bağlamı.
- **Validation**: currency/amount/id formatları.
- **Auditability**: PaymentAttempt + Ledger ile denetlenebilir değişiklikler.
- **Secrets**: `JWT_SECRET`, `DB_URL` gibi değerler `.env`/config’ten gelir.

## Observability
- Standard hata kodları: ör. `INSUFFICIENT_FUNDS`, `REQUEST_NOT_FOUND`, `REQUEST_NOT_PENDING`, `USER_BLOCKED`, `IDEMPOTENCY_CONFLICT`.
- Request id / correlation id (header) önerilir.

## Open Questions / Decisions
Bu maddeler, mevcut kod taslağında “belirsiz” olarak listelenen ve netleştirilmesi gereken kararlardır:
- Fee politikası: sabit mi yüzdesel mi, oran/değer, default davranış.
- Event üretimi: sync mi async mi (outbox önerisi).
- Auth kapsamı: yalnız email mock mu, JWT claim seti ne olmalı.
- Currency: yalnız `TRY` mi, enum mu, çoklu currency desteği olacak mı.
- Expiration çalıştırma biçimi: worker mı cron mu.

## Acceptance Criteria (Spec-level)
- Talep oluşturma, görüntüleme, listeleme, onaylama, reddetme akışları çalışır.
- Aynı `Idempotency-Key` ile tekrarlanan çağrılar tekrar işlem yapmaz.
- `approve` sadece `PENDING` taleplerde başarılı olur; aksi durumda deterministik hata döndürür.
- `expires_at` sonrası `PENDING` talepler `EXPIRED` olur ve approve edilemez.
- Hata formatı tüm endpoint’lerde tutarlıdır.

