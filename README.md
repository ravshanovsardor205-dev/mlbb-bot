# MLBB Duo Finder Bot (Railway Production)

## 1. Nimalar Bor
- Multi-admin (`ADMIN_IDS`)
- Persistent SQLite (`DATABASE=/data/mlbb.db`)
- Majburiy kanal/guruh obuna (muddat bilan)
- Reklama scheduler (HH.MM.SS interval + kunlik expiry)
- User profile, duo qidirish, e'lon, xabarlar
- Admin panel, audit, req check, backup, qahramon boshqaruvi

## 2. O'rnatish
```bash
pip install -r requirements.txt
```

`.env.example` nusxasi:
```bash
cp .env.example .env
```

`BOT_TOKEN`, `ADMIN_IDS`ni to'ldiring.

## 3. Ishga Tushirish
```bash
python mlbb_bot_updated.py
```

## 4. Railway Uchun Muhim
- Railway projectga Volume ulang.
- `DATABASE=/data/mlbb.db` qilib env kiriting.
- Shunda redeploy/push bo'lsa ham ma'lumotlar saqlanadi.

## 5. Admin Buyruqlari
- `/admin`
- `/stats`
- `/users`
- `/block <id> [sabab]`
- `/unblock <id>`
- `/blacklist`
- `/admin_msg <id> <text>`
- `/audit_user <id>`
- `/announcement_history <id>`
- `/add_char`, `/list_chars`, `/del_char <id>`
- `/backup`

Reklama:
- `/set_ad KUN HH.MM.SS MATN`
- `/show_ad`
- `/ad_on`
- `/ad_off`

Majburiy obuna:
- `/req_add CHAT_ID LINK KUN [NOM]`
- `/req_remove CHAT_ID`
- `/req_list`
- `/req_check USER_ID`
- `/chat_id`
- `/get_chat_id`

## 6. Eslatma
- Required chatlar uchun bot o'sha chatlarda bo'lishi kerak.
- Public chat bo'lsa admin qilish tavsiya etiladi.
- Private chatlarda ham bot member bo'lishi shart.