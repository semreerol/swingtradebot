# Firebase Yapılandırma Adımları

Firebase'i projenize bağlamak için aşağıdaki adımları sırasıyla uygulayın.

### Adım 1: Firebase Projesi Oluşturma
1. Tarayıcınızda [Firebase Console](https://console.firebase.google.com/)'a gidin.
2. **"Proje Ekle" (Add project)** butonuna tıklayın.
3. Projenize bir isim verin (örn. `swing-trade-bot`).
4. Google Analytics'i etkinleştirip etkinleştirmemek size kalmış (bu bot için gerekli değil).
5. Projeyi oluşturun.

### Adım 2: Firestore Veritabanını Kurma
1. Firebase konsolunda sol menüden **"Firestore Database"** seçeneğine tıklayın.
2. **"Veritabanı oluştur" (Create database)** butonuna tıklayın.
3. Konum seçimi yapın (size veya botu çalıştıracağınız sunucuya yakın bir yer seçin, örn. `europe-west3` veya `europe-west1`).
4. Güvenlik kuralları aşamasında **"Üretim modunda başla" (Start in production mode)** seçeneğini işaretleyip ileri deyin.

### Adım 3: Service Account (Hizmet Hesabı) Anahtarını Alma
Botun veritabanına erişebilmesi için bir kimlik dosyasına (JSON) ihtiyacı var:
1. Firebase konsolunda sol üstteki **Dişli çark (⚙️)** ikonuna tıklayın ve **"Proje Ayarları" (Project settings)** deyin.
2. Üst sekmelerden **"Hizmet Hesapları" (Service accounts)** sekmesine geçin.
3. Alt tarafta **"Yeni özel anahtar oluştur" (Generate new private key)** butonuna tıklayın.
4. Bu işlem bilgisayarınıza bir `.json` dosyası indirecektir. **Bu dosyayı güvenli bir yerde saklayın, kimseyle paylaşmayın.**

### Adım 4: JSON Dosyasını Projeye Ekleme
İndirdiğiniz bu JSON dosyasının içeriğini tek bir satır (string) haline getirip `.env` dosyanıza yapıştırmanız gerekiyor. Ancak `.env` dosyasında tırnak işaretleriyle vs. uğraşmamak için en iyisi şu şekilde yapmaktır:

1. İndirdiğiniz `.json` dosyasını `swing-trade-bot` klasörünün içine `firebase-service-account.json` adıyla kopyalayın.
2. Terminalinizde `swing-trade-bot` dizinindeyken şu komutu çalıştırarak JSON içeriğini tek satıra çevirin:
   ```bash
   cat firebase-service-account.json | jq -c .
   ```
   *(Eğer `jq` yüklü değilse, herhangi bir online JSON minifier aracıyla veya Python kullanarak json'ı minify edebilirsiniz.)*
   Alternatif olarak Python ile:
   ```bash
   python -c "import json,sys; print(json.dumps(json.load(sys.stdin)))" < firebase-service-account.json
   ```
3. Çıkan o uzun tek satırlık çıktıyı kopyalayın.
4. `swing-trade-bot/.env` dosyanızı açın ve `FIREBASE_SERVICE_ACCOUNT_JSON=` satırının sonuna yapıştırın.

Örnek `.env` görünümü:
```env
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"swing-trade-bot...
```

*Not: `firebase-service-account.json` dosyası `.gitignore`'a eklidir, bu yüzden GitHub'a gitmez. Ancak `.env` dosyanıza doğrudan yazmak en güvenli yöntemdir.*

### Adım 5: GitHub Actions İçin Secret Ekleme
Botu GitHub Actions üzerinde çalıştıracağımız için, bu JSON string'ini oraya da eklemeliyiz:
1. GitHub reponuzda **Settings > Secrets and variables > Actions** yolunu izleyin.
2. **"New repository secret"** butonuna tıklayın.
3. Name kısmına: `FIREBASE_SERVICE_ACCOUNT_JSON`
4. Secret kısmına: `.env` dosyanıza kopyaladığınız o tek satırlık JSON string'ini yapıştırın.
5. "Add secret" diyerek kaydedin.

Aynı şekilde `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` değerlerini de GitHub Secrets'a eklemeyi unutmayın!

Bu işlemleri tamamladıktan sonra `python -m app.main` komutunu çalıştırdığınızda bot Firestore'a bağlanacak ve gerekli koleksiyonları/ayarları otomatik oluşturacaktır.
