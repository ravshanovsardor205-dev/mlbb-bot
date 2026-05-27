# 🎮 MLBB Duo Finder Bot

Mobile Legends: Bang Bang uchun sherik topish botasi. Foydalanuvchilar o'zlarining rankni va rollarini belgilash orqali mos keladigan sherikni topa oladi.

## 🌟 Xususiyatlari

✅ **Profil boshqarish**
- Rank va rollarni tanlash
- Profil tahrirlash

✅ **Sherik qidirish**
- Ranklar bo'yicha qidirish
- Rol bo'yicha filterlash
- Faqat e'lon bergan sheriklar

✅ **E'lon berish**
- O'zingizni e'lon qiling
- Sheriklar sizi topib xabar yuborsin

✅ **Chat funksionalligi**
- Sheriklar bilan xabar yuborish
- Chat tarixi saqlanishi

---

## 🚀 Lokal ishlatish

### 1. Repository Clone Qiling

```bash
git clone https://github.com/YOUR_USERNAME/mlbb-bot.git
cd mlbb-bot
```

### 2. Virtual Environment Yarating (Ixtiyoriy)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Kutubxonalarni O'rnating

```bash
pip install -r requirements.txt
```

### 4. .env Fayl Yarating

`.env.example`-ni `.env` sifatida ko'chirib:

```bash
cp .env.example .env
```

**`.env` faylini tahrirlang:**

```
BOT_TOKEN=8830561217:AAGfXR1HhpZMgvmeJW7DUaF2xdiby1j845c
```

> 🔐 **Eslab qoling:** Token-ni hech kunga jo'natmang!

### 5. Botni Ishga Tushiring

```bash
python mlbb_bot_updated.py
```

Agar hamma to'g'ri bo'lsa:
```
2026-05-27 00:49:50,009 [INFO] ✅ Database initialized
2026-05-27 00:49:50,014 [INFO] ✅ BOT ISHGA TUSHDI!
```

---

## ☁️ RAILWAY-GA 24/7 DEPLOYMENT

### 📋 Talab qilinadi:
- GitHub account
- Railway account

### 🔧 Setup qadamlari:

#### **Qadam 1: Kodni GitHub-ga yuklash**

1. GitHub-ga o'ting: https://github.com
2. **New repository** yarating
3. Nom: `mlbb-bot`
4. **Create repository** bosing

#### **Qadam 2: Git-ni o'rnatish (agar o'rnatilmagan bo'lsa)**

- Windows: https://git-scm.com/download/win
- Mac: `brew install git`
- Linux: `sudo apt install git`

#### **Qadam 3: Kodni GitHub-ga jo'natish**

Reponi yo'lga o'ting va quyidagi buyruqlarni bajaring:

```bash
# Terminal/PowerShell-ni oching
cd mlbb-bot

# Git-ni ishga tushirish
git config --global user.name "Sizning Ismi"
git config --global user.email "emailingiz@gmail.com"

# Repository-ni ishga tushirish
git init
git add .
git commit -m "MLBB Bot - Sherik Topish"
git branch -M main

# Remote qo'shish (GitHub linkingizni o'rnating)
git remote add origin https://github.com/YOUR_USERNAME/mlbb-bot.git

# Yuklash
git push -u origin main
```

**GitHub parol o'rniga Personal Access Token ishlatish:**
1. GitHub → **Settings** → **Developer settings** → **Personal access tokens**
2. **Generate new token (classic)** bosing
3. **repo** tanlang
4. Copy qiling va push-da token kiritish paytida paste qiling

#### **Qadam 4: Railway-ga ulanish**

1. https://railway.app ga o'ting
2. **GitHub bilan kiriting**
3. **New Project** bosing
4. **Deploy from GitHub repo** tanlang
5. Reponi tanlang: `mlbb-bot`
6. **Deploy** bosing

#### **Qadam 5: Environment Variables Qo'shish**

Railway dashboard-da:
1. **Variables** tab-iga o'ting
2. **New Variable** bosing
3. Qo'shing:

```
BOT_TOKEN = 8830561217:AAGfXR1HhpZMgvmeJW7DUaF2xdiby1j845c
```

4. **Save** bosing

#### **Qadam 6: Deployment Natija**

Agar hamma to'g'ri bo'lsa, Railway avtomatik:
- ✅ Kodni pull qiladi
- ✅ requirements.txt-dan dependencies o'rnatadi
- ✅ Procfile asosida botni ishga tushiradi
- ✅ 24/7 ishga tushiradi
- ✅ Qo'pol bo'lsa avtomatik restart qiladi

---

## 📊 Database

Bot `mlbb.db` faylida SQLite database ishlatadi:

```
users          - Foydalanuvchi ma'lumotlari
messages       - Chat xabarlari
announcements  - E'lonlar
```

> ⚠️ **Railway-da:** Database har deployment-da reset bo'ladi. Uni saqlab qolish uchun PostgreSQL ishlating (Railway-da bepul).

---

## 🐛 Debugging

Log-larni ko'rish uchun Railway dashboard-da:
1. **Deployments** → Oxirgi deployment
2. **Logs** tab-iga o'ting
3. Barcha xabarlar ko'rinadi

---

## 📝 O'zgartirishlar qilish

Railway avtomatik yangi push-larni deploy qiladi:

```bash
# Kodni o'zgartiring
# Keyin:
git add .
git commit -m "O'zgartirishning tavsifi"
git push
```

Railway avtomatik yuklab va deploy qiladi! 🚀

---

## 🔗 Foydali Havolalar

- **BotFather:** https://t.me/BotFather
- **Aiogram:** https://docs.aiogram.dev
- **Railway:** https://railway.app
- **GitHub:** https://github.com

---

## 📞 Muammolar

Agar muammo bo'lsa:
1. Railway logs-ni ko'ring
2. `.env` faylini tekshiring
3. Bot token-i to'g'ri ekanligini tekshiring
4. GitHub push-i muvaffaqiyatli ekanligini tekshiring

---

## 📜 Litsenziya

MIT License

---

**Yaratilgan:** 2026-05-27  
**Oxirgi yangilash:** 2026-05-27
