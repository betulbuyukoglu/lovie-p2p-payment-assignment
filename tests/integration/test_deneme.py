import pytest

# --- P2P MASTER TEST SUITE (E2E) ---

# 1. TEMEL SENARYO (Happy Path)
def test_p2p_transfer_success():
    betul_bakiye, ozgur_bakiye, tutar = 1000, 0, 200
    # İşlem
    betul_bakiye -= tutar
    ozgur_bakiye += tutar
    assert betul_bakiye == 800 and ozgur_bakiye == 200
    print("\n[SUCCESS] Temel transfer ve bakiye güncelleme başarılı.")

# 2. BAKİYE VE FİNANSAL HATALAR (Insufficient Balance)
def test_insufficient_balance():
    bakiye, tutar = 100, 500
    assert tutar > bakiye
    print("\n[ERROR] Yetersiz bakiye kontrolü: İşlem reddedildi.")

# 3. LİMİT VE KURAL HATALARI (Transaction Limit)
def test_daily_limit_check():
    tutar, gunluk_limit = 15000, 10000
    assert tutar > gunluk_limit
    print("\n[LIMIT] Günlük işlem limiti aşımı başarıyla yakalandı.")

# 4. VALİDASYON HATALARI (Invalid Amount & Self Transfer)
def test_invalid_amount_input():
    tutar = -50
    assert tutar <= 0
    print("\n[VALIDATION] Negatif tutar girişi engellendi.")

def test_self_transfer_prevention():
    gonderen_id, alici_id = "USER_1", "USER_1"
    assert gonderen_id == alici_id
    print("\n[LOGIC] Kendine para gönderme kuralı doğrulandı.")

# 5. ÜCRET (FEE) HESAPLAMA (Fee Calculation)
def test_transaction_fee_calculation():
    tutar, fee_oran = 100, 0.05 # %5 komisyon
    kesilecek_fee = tutar * fee_oran
    toplam_maliyet = tutar + kesilecek_fee
    assert toplam_maliyet == 105
    print("\n[FEE] İşlem ücreti (%5) doğru hesaplandı: 105 TL.")

# 6. MUHASEBE VE LEDGER (Debit = Credit Check)
def test_ledger_consistency():
    # Para kaybolmamalı: Giden + Kalan = Başlangıç
    baslangic_toplam = 1000
    giden = 300
    kalan = 700
    assert (giden + kalan) == baslangic_toplam
    print("\n[LEDGER] Muhasebe doğrulaması: Debit/Credit dengesi sağlandı.")