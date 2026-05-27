# 🚀 MLBB BOT - GITHUB VA RAILWAY-GA DEPLOYMENT QOʻLLANMA

> **Vaqt:** ~30 daqiqa  
> **Qiyinchilik:** Oson ⭐⭐⭐

---

## 📋 TALAB QILINADI

✅ GitHub account (https://github.com)  
✅ Railway account (https://railway.app)  
✅ Git o'rnatilgan (https://git-scm.com)  

---

## 🔧 QADAM 1: GIT O'RNATISH (AGAR O'RNATILMAGAN BO'LSA)

### Windows-da:
1. https://git-scm.com/download/win ga o'ting
2. EXE faylni yuklab, **Next, Next, Install** bosing
3. **Git Bash** yoki **Terminal** ochib tekshiring:

```bash
git --version
```

✅ Versiyon ko'rinsa - tayyor!

### Mac-da:
```bash
brew install git
```

### Linux-da:
```bash
sudo apt install git
```

---

## 💻 QADAM 2: KODNI TAYYORLASH (LOKAL MASHINA)

### 1. Papka yarating

```bash
# Terminal/PowerShell ochib:
mkdir mlbb-bot
cd mlbb-bot
```

### 2. Barcha fayllarni shunaqa o'rnating:

```
mlbb-bot/
├── mlbb_bot_updated.py
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── Procfile
├── runtime.txt
├── README.md
└── .git/
```

**Quyidagi fayllarni yuklab oling:**
- `mlbb_bot_updated.py` ← Bot kodi
- `requirements.txt` ← Kutubxonalar
- `.env` ← Token (RAHSIYA - Git-ga yuklash kerak emas!)
- `.env.example` ← Template
- `.gitignore` ← Git ignorlash
- `Procfile` ← Railway uchun
- `runtime.txt` ← Python versiyasi
- `README.md` ← Qo'llanma

---

## 🔑 QADAM 3: TOKEN O'RNATISH

### `.env` faylni oching va token qo'ying:

```env
BOT_TOKEN=8830561217:AAGfXR1HhpZMgvmeJW7DUaF2xdiby1j845c
DATABASE=mlbb.db
```

> ⚠️ **MUHIM:** Bu fayl `.gitignore`-da bor, Git-ga yuklash kerak emas!

---

## 📦 QADAM 4: GITHUB-DA REPOSITORY YARATISH

### 4.1 GitHub-ga o'ting

1. https://github.com ga kiriting
2. **+** (Yuqori right) → **New repository**

### 4.2 Repository sozlashtirlash

```
Repository name:        mlbb-bot
Description:           MLBB Duo Finder Bot
Visibility:            Public
☐ Initialize with README  (TANLANG!)
☐ Add .gitignore         (TANLANG!)
☐ Add a license          (SHUNAQA BO'SH QOYING)
```

**Create repository** bosing ✅

### 4.3 Repository URL-i nusxalang

Masalan: `https://github.com/YOUR_USERNAME/mlbb-bot.git`

---

## 🔄 QADAM 5: GIT-NI SOZLASH VA PUSH QILISH

### 5.1 Terminal-da shunaqa bajaring:

```bash
cd mlbb-bot
```

### 5.2 Git-ni ishga tushirish (BIR MARTA)

```bash
git config --global user.name "Sizning Ismi"
git config --global user.email "emailingiz@gmail.com"
```

**Masalan:**
```bash
git config --global user.name "Alisher Omonov"
git config --global user.email "alisher@gmail.com"
```

### 5.3 Git repository-ni ishga tushirish

```bash
git init
git add .
git commit -m "MLBB Bot - Sherik Topish"
git branch -M main
```

### 5.4 GitHub-ga ulash va push qilish

```bash
git remote add origin https://github.com/YOUR_USERNAME/mlbb-bot.git
git push -u origin main
```

**GitHub username va token kiritib qayta bosing!**

---

## 🔐 GITHUB PERSONAL ACCESS TOKEN (AGAR KERAK BO'LSA)

Agar parol kerak desa, token ishlating:

### Token yaratish:

1. GitHub → **Settings** (Yuqori right → Settings)
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token (classic)** bosing
4. **Scopes** da `repo` tanlang
5. **Generate token** bosing
6. Token nusxalang (keyin ko'rinmaydi!)

### Push-da ishlatish:

```bash
git push -u origin main
```

Ko'rsatilganda:
```
Username: YOUR_USERNAME
Password: [token-ni paste qiling]
```

---

## 🚀 QADAM 6: RAILWAY-GA DEPLOYMENT

### 6.1 Railway-ga kirish

1. https://railway.app ga o'ting
2. **Login** → **GitHub bilan kiriting** ✅

### 6.2 New Project yaratish

1. **New Project** bosing
2. **Deploy from GitHub repo** tanlang

### 6.3 Repository tanlang

1. `mlbb-bot` repository-ni tanlang
2. **Deploy** bosing

✅ Railway avtomatik:
- Kodni pull qiladi
- `requirements.txt`-dan dependencies o'rnatadi
- `Procfile`-dan botni ishga tushiradi

### 6.4 Environment Variables qo'shish

1. Railway dashboard-da **Tokens** bo'limi
2. **+ Variable** bosing
3. Qo'shing:

```
BOT_TOKEN = 8830561217:AAGfXR1HhpZMgvmeJW7DUaF2xdiby1j845c
DATABASE = mlbb.db
```

4. **Save** bosing ✅

---

## ✅ DEPLOYMENT TUGATILDI!

Endi bot **24/7** ishga tushgan!

### Tekshirish:

1. Railway dashboard-da **Deployments** → Oxirgi
2. **Logs** tab-iga o'ting
3. Ko'ring:
   ```
   ✅ Database initialized
   ✅ BOT ISHGA TUSHDI!
   ```

✨ Bot hazir ishga tushgan! Telegram-da `/start` bosib test qiling!

---

## 🔄 O'ZGARTIRISHLAR QILISH (KEYING)

Agar kodda o'zgartirish kerak bo'lsa:

```bash
# 1. Kodni o'zgartiring
# 2. Save qiling
# 3. Terminal-da:

git add .
git commit -m "O'zgartirishning tavsifi"
git push
```

**Railway avtomatik yangi version deploy qiladi!** 🚀

---

## 🐛 DEBUGGING

### Railway logs-ni ko'rish:

1. Railway dashboard
2. **Deployments** → Oxirgi deployment
3. **Logs** bosing
4. Barcha xabarlar ko'rinadi

### Muammolar:

**❌ Build xatosi**
- `requirements.txt` to'g'ri ekanligini tekshiring
- Token-ni tekshiring

**❌ Database xatosi**
- `DATABASE` o'zgaruvchini tekshiring

**❌ Bot ishga tushmamoqda**
- `.env` faylda token qiymati bor ekanligini tekshiring
- Procfile to'g'ri ekanligini tekshiring

---

## 📞 FOYDALI HAVOLALAR

- **GitHub:** https://github.com
- **Railway:** https://railway.app
- **Git:** https://git-scm.com
- **Python:** https://python.org

---

## 🎉 TAYYOR!

Bot 24/7 ishga tushgan va siz lokal mashina yoqishga kerak emas!

**Telegram-da botni ishlatish uchun: @mlbb_qidiruv_bot**

Xosh! 🚀
