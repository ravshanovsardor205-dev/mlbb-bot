# ⚡ QUICK START - TEZKOR BOSHLASH

**Agar tezda Railroad-ga yuklashni xohlaysiz, bu yerni o'qing!**

---

## 🎯 5 DAQIQADA SETUP

### 1️⃣ GITHUB ACCOUNT (Agar yo'q bo'lsa)
https://github.com/signup

### 2️⃣ RAILWAY ACCOUNT (Agar yo'q bo'lsa)
https://railway.app → **Login with GitHub**

### 3️⃣ YA'NI QANDAY QILISH?

```bash
# Terminal-ni oching (Windows: PowerShell, Mac/Linux: Terminal)

# 1. Boringizga o'ting
cd Desktop  # yoki istalgan joy

# 2. Papka yarating
mkdir mlbb-bot
cd mlbb-bot

# 3. Git-ni ishga tushiring
git init
git config --global user.name "Sizning Ismi"
git config --global user.email "email@gmail.com"

# 4. Barcha fayllarni shunaqa joyga qo'ying:
#    - mlbb_bot_updated.py
#    - requirements.txt
#    - .env
#    - .env.example
#    - .gitignore
#    - Procfile
#    - runtime.txt
#    - README.md

# 5. Push qiling
git add .
git commit -m "MLBB Bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mlbb-bot.git
git push -u origin main
```

**GitHub-da username va token kiritib ENTER bosing**

### 4️⃣ RAILWAY-DA DEPLOY

1. https://railway.app → **New Project**
2. **Deploy from GitHub** 
3. `mlbb-bot` tanlang
4. **Deploy** bosing
5. **Variables**:
   - `BOT_TOKEN` = 
   - `DATABASE` = `mlbb.db`

---

## ✅ TAYYOR!

**5 daqiqa keyin bot 24/7 ishga tushgan bo'ladi!** 🎉

---

## 📝 TOKEN QANDAY O'RNATISH?

### Windows/Mac/Linux:

`.env` faylni oching va yozing:

```
BOT_TOKEN=
DATABASE=mlbb.db
```

---

## 🆘 MUAMMO BO'LSA?

| Muammo | Yechim |
|--------|--------|
| Git o'rnatilmagan | https://git-scm.com dan yuklab o'rnatang |
| Token kerak | @BotFather-dan oling: /start → /newbot |
| Railway build xatosi | requirements.txt tekshiring |
| Bot ishga tushmamoqda | Railway logs-ni ko'ring |

---

## 🚀 BITTADA DASTUR

```bash
git add . && git commit -m "MLBB Bot" && git push
```

Bittada buyruq - sekundlarda deploy! ⚡

---

**Savollar bo'lsa: README.md va SETUP_GUIDE.md o'qing** 📖

