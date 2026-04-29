# 🤖 Swing Trade Bot — Paper Trading MVP

Sunucusuz, GitHub Actions ile çalışan bir paper trading swing trade botu. Firebase Firestore veritabanı ve Telegram bildirimleri ile entegredir.

> ⚠️ **Bu bot gerçek emir göndermez.** Sadece paper trading yapar. Canlı işlem desteği bu versiyonda yoktur.

---

## 📋 Özellikler

- **Paper Trading**: Gerçek emir göndermeden trade simülasyonu
- **Swing Trade**: 1-2 hafta süreli pozisyonlar için sinyal üretimi
- **Çift Timeframe**: 1D trend filtresi + 4H giriş sinyali
- **Risk Yönetimi**: ATR bazlı stop-loss, R/R minimum 1:2, pozisyon boyutlandırma
- **Firestore Veritabanı**: Tüm trade, sinyal ve bot verileri kaydedilir
- **Telegram Bildirimleri**: Trade açılış, kapanış ve hata bildirimleri
- **GitHub Actions**: Her 4 saatte bir otomatik çalışma
- **Distributed Lock**: Aynı anda birden fazla bot çalışmasını önler
- **Sadece LONG**: Short, futures, leverage desteklenmez

---

## 🏗 Proje Yapısı

```
swing-trade-bot/
├── app/
│   ├── main.py                  # Ana giriş noktası
│   ├── config.py                # Environment variable yönetimi
│   ├── firebase/
│   │   ├── client.py            # Firebase Admin SDK init
│   │   ├── repositories.py      # Firestore CRUD işlemleri
│   │   └── lock_manager.py      # Distributed lock
│   ├── exchange/
│   │   └── binance_market_data.py  # Binance public API
│   ├── indicators/
│   │   ├── ema.py               # EMA hesaplama
│   │   ├── rsi.py               # RSI hesaplama
│   │   └── atr.py               # ATR hesaplama
│   ├── strategies/
│   │   ├── base.py              # StrategySignal dataclass
│   │   └── daily_trend_4h_entry.py  # Ana strateji
│   ├── risk/
│   │   ├── position_sizer.py    # Pozisyon boyutlandırma
│   │   └── risk_manager.py      # Risk doğrulama
│   ├── execution/
│   │   └── paper_executor.py    # Paper trade yönetimi
│   ├── notification/
│   │   └── telegram.py          # Telegram bildirimleri
│   └── utils/
│       └── logger.py            # Loglama
├── tests/
│   ├── test_indicators.py
│   ├── test_risk_manager.py
│   └── test_strategy.py
├── .github/workflows/
│   └── swing-bot.yml            # GitHub Actions cron
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚀 Kurulum

### 1. Depoyu Klonlayın

```bash
git clone https://github.com/your-username/swing-trade-bot.git
cd swing-trade-bot
```

### 2. Python Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables

```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

---

## 🔥 Firebase Setup

### 1. Firebase Projesi Oluşturun

1. [Firebase Console](https://console.firebase.google.com/) adresine gidin.
2. Yeni proje oluşturun.
3. **Firestore Database** > **Create database** > Production mode seçin.

### 2. Service Account Key

1. Firebase Console > **Project Settings** > **Service Accounts** sekmesine gidin.
2. **Generate new private key** butonuna tıklayın.
3. İndirilen JSON dosyasının tüm içeriğini kopyalayın.
4. Bu JSON'u `FIREBASE_SERVICE_ACCOUNT_JSON` environment variable'ına yapıştırın.

### Firestore Koleksiyonları

Bot ilk çalıştığında aşağıdaki koleksiyonları otomatik oluşturur:

| Koleksiyon | Doküman | Açıklama |
|---|---|---|
| `bot_settings` | `main` | Bot ayarları (symbol, risk, timeframe, vb.) |
| `strategies` | `daily_trend_4h_entry_v1` | Strateji parametreleri |
| `signals` | `signal_{id}` | Üretilen sinyaller |
| `trades` | `trade_{id}` | Paper trade'ler |
| `trade_events` | `event_{id}` | Trade yaşam döngüsü olayları |
| `bot_runs` | `run_{id}` | Her bot çalışmasının kaydı |
| `bot_locks` | `main` | Distributed lock |

### Firestore Security Rules

Production için aşağıdaki kuralları kullanın (sadece server erişimi):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

> Bot, Admin SDK ile çalıştığı için bu kurallar onu etkilemez. Kurallar sadece client SDK erişimini engeller.

---

## 📱 Telegram Bot Oluşturma

1. Telegram'da [@BotFather](https://t.me/BotFather)'a gidin.
2. `/newbot` komutunu gönderin ve isim verin.
3. Aldığınız **Bot Token**'ı `TELEGRAM_BOT_TOKEN` olarak kaydedin.
4. Botu bir gruba ekleyin veya direkt mesaj gönderin.
5. Chat ID'nizi öğrenmek için:
   - Botu başlatın (Start butonu).
   - `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini ziyaret edin.
   - JSON'daki `chat.id` değerini `TELEGRAM_CHAT_ID` olarak kaydedin.

---

## 🔐 GitHub Secrets Ayarları

Repository > **Settings** > **Secrets and variables** > **Actions** > **New repository secret**

| Secret | Açıklama |
|---|---|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase service account JSON (tam JSON string) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Telegram chat ID |

---

## 💻 Local Çalıştırma

```bash
# .env dosyasını ayarlayın
cp .env.example .env
# Değerleri doldurun

# Testleri çalıştırın
python -m pytest tests/ -v

# Botu çalıştırın
python -m app.main
```

---

## ⚙️ GitHub Actions ile Çalışma

Bot her **4 saatte bir** otomatik çalışır:

- **Cron**: `0 */4 * * *`
- **Manuel tetikleme**: Actions sekmesinden "Run workflow" butonu

### Workflow Adımları:

1. Python 3.11 kurulumu
2. Bağımlılık yükleme
3. Test çalıştırma
4. Bot çalıştırma

---

## 📊 Paper Trading Mantığı

### Çalışma Akışı

```
Bot Başlar
  ↓
Config & Firebase yükle
  ↓
Lock al (30 dk timeout)
  ↓
Açık trade var mı? ──── Evet ──→ Fiyat kontrol et
  │                                    ↓
  │                              SL/TP/Timeout?
  │                              Evet → Kapat, bildirim gönder
  │                              Hayır → Status log
  ↓
Yeni sinyal ara
  ↓
1D trend filtresi (EMA, RSI)
  ↓
4H giriş filtresi (EMA, Volume, Fiyat)
  ↓
Risk kontrolü (R/R, pozisyon boyutu)
  ↓
Paper trade oluştur
  ↓
Firestore'a yaz + Telegram bildir
  ↓
Lock serbest bırak
```

### Strateji Kuralları

**1D Trend Filtresi (Tümü geçmeli):**
- Kapanış > EMA50
- EMA20 > EMA50
- RSI 45-70 arasında

**4H Giriş Filtresi (Tümü geçmeli):**
- Kapanış > EMA20
- EMA20 > EMA50
- Kapanış, son 20 mumun en yüksek kapanışına yakın
- Volume ortalamanın üstünde (soft pass)

**Trade Parametreleri:**
- Entry: Son 4H kapanış
- Stop-loss: Entry - ATR × 2.0
- Take-profit: Entry + (Risk × 2.0)
- Maksimum süre: 14 gün

---

## 🔒 Güvenlik Notları

- Firebase service account key'inizi **asla** versiyon kontrolüne eklemeyin.
- `.gitignore` dosyası JSON key dosyalarını otomatik hariç tutar.
- Tüm hassas bilgiler GitHub Secrets üzerinden yönetilmelidir.
- Firestore Security Rules ile client erişimini kapatın.
- Telegram bot token'ınızı kimseyle paylaşmayın.

---

## ⛔ Canlı İşleme Geçiş İçin YAPILMAMASI Gerekenler

> Bu proje bir MVP paper trading botudur. Canlı işleme geçmeden önce:

1. ❌ **Bu kodu doğrudan canlıya almayın** — Kapsamlı backtesting yapılmadan gerçek para riske atılmamalıdır.
2. ❌ **Binance API key eklemeyin** — Bu versiyonda gerçek emir gönderme altyapısı yoktur.
3. ❌ **Futures/leverage eklemeyin** — Tasfiye riski çok yüksektir.
4. ❌ **Risk parametrelerini artırmayın** — %1 risk başlangıç için bile yüksek olabilir.
5. ❌ **Bot'u denetimsiz bırakmayın** — Herhangi bir otomatik trading sistemi sürekli izlenmelidir.
6. ❌ **Tek stratejiye güvenmeyin** — Paper trading sonuçları geçmiş performansı garanti etmez.

### Canlıya geçiş için minimum yapılması gerekenler:

- [ ] En az 3 ay paper trading sonuçlarını inceleyin.
- [ ] Backtesting framework'ü entegre edin.
- [ ] Rate limiting ve hata yönetimini güçlendirin.
- [ ] Binance API key yönetimini güvenli şekilde ekleyin.
- [ ] Gerçek emir gönderme modülü yazın (ayrı ve izole).
- [ ] Kill switch mekanizması ekleyin.
- [ ] Kapsamlı logging ve monitoring kurun.
- [ ] API key izinlerini minimum tutun (sadece spot, sadece okuma + trade).

---

## 📦 Gereksinimler

- Python 3.11+
- Firebase projesi (Firestore)
- Telegram bot
- GitHub hesabı (Actions için)

---

## 📜 Lisans

Bu proje kişisel kullanım içindir. Finansal tavsiye niteliği taşımaz.
