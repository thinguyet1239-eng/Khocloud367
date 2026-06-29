#!/usr/bin/env python3
import logging, random, string, httpx
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN    = "8808511573:AAG-kPwmgJE10u1vxFOlB2whIEItNKozSKs"
ADMIN_ID     = 8766063561
SUPABASE_URL = "https://jiployprjehmzbxswixl.supabase.co"
SUPABASE_KEY = "sb_publishable_0Lv86sgJ1kep3psyqh17eQ_-pRXGNy4"
WEBSITE_URL  = "https://moewloverapi.netlify.app"
COIN_NAME    = "Coin"
UPTO_TOKEN   = "d71f101e2ea5ead6c431a3f7e25ab0eab6446770"
LINK4M_API   = "6a4165b5c0f32b0c1f6355a7"

TASK_TYPES = {
    "upto3":  {"label": "Upto Step 3", "coin": 350, "emoji": "⚡", "advert": 3},
    "upto4":  {"label": "Upto Step 4", "coin": 367, "emoji": "🔥", "advert": 5},
    "link4m": {"label": "Link4m",      "coin": 300, "emoji": "🌐"},
}

try:
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Supabase kết nối thành công")
except Exception as e:
    logger.error(f"Supabase lỗi: {e}")
    raise

# ── DB ──
def get_user(uid):
    try:
        r = db.table("users").select("*").eq("user_id", uid).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        logger.error(f"get_user lỗi: {e}")
        return None

def get_or_create_user(uid, username, full_name):
    try:
        u = get_user(uid)
        if not u:
            u = {"user_id": uid, "username": username, "full_name": full_name, "balance": 0, "is_banned": False}
            db.table("users").insert(u).execute()
        return u
    except Exception as e:
        logger.error(f"get_or_create_user lỗi: {e}")
        return None

def update_balance(uid, amount):
    try:
        u = get_user(uid)
        if not u: return 0
        nb = u["balance"] + amount
        db.table("users").update({"balance": nb}).eq("user_id", uid).execute()
        return nb
    except Exception as e:
        logger.error(f"update_balance lỗi: {e}")
        return 0

def is_banned(uid):
    u = get_user(uid)
    return u.get("is_banned", False) if u else False

def gen_code(n=8):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

def count_link4m_today(uid):
    try:
        today = date.today().isoformat()
        ids = [t["id"] for t in db.table("tasks").select("id").eq("task_type", "link4m").eq("is_active", True).execute().data]
        if not ids: return 0
        return len(db.table("task_completions").select("id").eq("user_id", uid).eq("completed_date", today).in_("task_id", ids).execute().data)
    except Exception as e:
        logger.error(f"count_link4m lỗi: {e}")
        return 0

# ── API ──
async def shorten_upto(url, advert):
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://uptolink.vip/api?api={UPTO_TOKEN}&url={url}&advert={advert}")
            d = r.json()
            if d.get("status") == "success": return d["shortenedUrl"]
    except Exception as e:
        logger.error(f"shorten_upto lỗi: {e}")
    return url

async def shorten_link4m(url):
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://link4m.co/api-shorten/v2?api={LINK4M_API}&url={url}")
            d = r.json()
            if d.get("status") == "success": return d["shortenedUrl"]
    except Exception as e:
        logger.error(f"shorten_link4m lỗi: {e}")
    return url

# ── GUARDS ──
def banned_guard(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        u = update.effective_user
        get_or_create_user(u.id, u.username or "", u.full_name or "")
        if is_banned(u.id):
            await update.effective_message.reply_text("🚫 Tài khoản của bạn đã bị khóa.")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_ID:
            await update.effective_message.reply_text("🚫 Không có quyền admin!")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper

# ── MENU ──
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Số dư", callback_data="sodu"),
         InlineKeyboardButton("📋 Nhiệm vụ", callback_data="nhiem_vu")],
        [InlineKeyboardButton("🛍️ Cửa hàng", callback_data="cuahang"),
         InlineKeyboardButton("🔄 Quy đổi", callback_data="quy_doi")],
    ])

def task_kb(uid):
    left = max(0, 2 - count_link4m_today(uid))
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ Upto Step 3 — 350 {COIN_NAME}", callback_data="tt_upto3")],
        [InlineKeyboardButton(f"🔥 Upto Step 4 — 367 {COIN_NAME}", callback_data="tt_upto4")],
        [InlineKeyboardButton(f"🌐 Link4m — 300 {COIN_NAME} (còn {left}/2)", callback_data="tt_link4m")],
    ])

def task_text(uid):
    left = max(0, 2 - count_link4m_today(uid))
    return (
        "📋 *CHỌN LOẠI NHIỆM VỤ*\n\n"
        "⚡ *Upto Step 3* — 350 Coin\n"
        "🔥 *Upto Step 4* — 367 Coin\n"
        f"🌐 *Link4m* — 300 Coin _(giới hạn 2/ngày, còn {left})_\n\n"
        "Chọn loại bên dưới:"
    )

# ── USER COMMANDS ──
@banned_guard
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.full_name
    await update.message.reply_text(
        f"👋 Chào *{name}*! Chào mừng đến với bot!\n\n"
        "• /sodu – Xem số dư\n"
        "• /nhiem\\_vu – Nhận nhiệm vụ\n"
        "• /nhapma <mã> – Nhập mã thưởng\n"
        "• /cuahang – Xem sản phẩm\n"
        "• /quy\\_doi <id> – Đổi sản phẩm",
        parse_mode="Markdown", reply_markup=main_kb()
    )

@banned_guard
async def cmd_sodu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("❌ Lỗi lấy thông tin, thử lại!"); return
    await update.message.reply_text(
        f"💰 *Số dư tài khoản*\n\n👤 {u['full_name']}\n🪙 *{u['balance']} {COIN_NAME}*",
        parse_mode="Markdown"
    )

@banned_guard
async def cmd_nhiem_vu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(task_text(uid), parse_mode="Markdown", reply_markup=task_kb(uid))

@banned_guard
async def cmd_nhapma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Cú pháp: `/nhapma <mã>`", parse_mode="Markdown"); return
    code = context.args[0].upper().strip()
    uid = update.effective_user.id
    try:
        res = db.table("tasks").select("*").eq("reward_code", code).eq("is_active", True).execute()
        if not res.data:
            await update.message.reply_text("❌ Mã không hợp lệ hoặc đã hết hạn!"); return
        task = res.data[0]
        if db.table("task_completions").select("id").eq("user_id", uid).eq("task_id", task["id"]).execute().data:
            await update.message.reply_text("⚠️ Bạn đã nhập mã này rồi!"); return
        db.table("task_completions").insert({
            "user_id": uid, "task_id": task["id"], "completed_date": date.today().isoformat()
        }).execute()
        nb = update_balance(uid, task["coin_reward"])
        info = TASK_TYPES.get(task.get("task_type", "upto3"), TASK_TYPES["upto3"])
        await update.message.reply_text(
            f"✅ *Hoàn thành {info['label']}!*\n\n🎁 +{task['coin_reward']} {COIN_NAME}\n💰 Số dư: *{nb} {COIN_NAME}*",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"nhapma lỗi: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra, thử lại!")

@banned_guard
async def cmd_cuahang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        products = db.table("products").select("*").eq("is_active", True).execute().data
        if not products:
            await update.message.reply_text("🛍️ Cửa hàng chưa có sản phẩm."); return
        text = "🛍️ *CỬA HÀNG*\n\n"
        for p in products:
            text += f"🆔 `{p['id']}` | 📦 {p['name']}\n📝 {p.get('description','')}\n💰 {p['coin_price']} {COIN_NAME} | {'%d còn' % p['stock'] if p['stock'] > 0 else 'Hết hàng'}\n\n"
        await update.message.reply_text(text + "💡 `/quy_doi <ID>` để đổi", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cuahang lỗi: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra, thử lại!")

@banned_guard
async def cmd_quy_doi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ `/quy_doi <ID>`", parse_mode="Markdown"); return
    try:
        pid = int(context.args[0])
    except:
        await update.message.reply_text("❌ ID phải là số!"); return
    try:
        prod = db.table("products").select("*").eq("id", pid).eq("is_active", True).execute()
        if not prod.data: await update.message.reply_text("❌ Sản phẩm không tồn tại!"); return
        p = prod.data[0]
        if p["stock"] <= 0: await update.message.reply_text("❌ Hết hàng!"); return
        uid = update.effective_user.id
        u = get_user(uid)
        if u["balance"] < p["coin_price"]:
            await update.message.reply_text(f"❌ Không đủ {COIN_NAME}!\n💰 Có: {u['balance']} | Cần: {p['coin_price']}"); return
        item = db.table("product_items").select("*").eq("product_id", pid).eq("is_sold", False).limit(1).execute()
        if not item.data: await update.message.reply_text("❌ Hết hàng trong kho!"); return
        it = item.data[0]
        update_balance(uid, -p["coin_price"])
        db.table("product_items").update({"is_sold": True, "sold_to": uid}).eq("id", it["id"]).execute()
        db.table("products").update({"stock": p["stock"] - 1}).eq("id", pid).execute()
        db.table("exchanges").insert({"user_id": uid, "product_id": pid, "item_id": it["id"], "coin_spent": p["coin_price"]}).execute()
        nb = get_user(uid)["balance"]
        await update.message.reply_text(
            f"✅ *Đổi thành công!*\n\n📦 {p['name']}\n🎁 `{it['item_data']}`\n\n💰 Còn: {nb} {COIN_NAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"quy_doi lỗi: {e}")
        await update.message.reply_text("❌ Có lỗi xảy ra, thử lại!")

# ── SHOW TASK ──
async def show_task(query, uid, task_type):
    try:
        if task_type == "link4m" and count_link4m_today(uid) >= 2:
            await query.edit_message_text("⛔ Hết 2 lượt Link4m hôm nay!\nQuay lại vào ngày mai 🕐"); return
        all_tasks = db.table("tasks").select("*").eq("is_active", True).eq("task_type", task_type).execute().data
        done_ids = {c["task_id"] for c in db.table("task_completions").select("task_id").eq("user_id", uid).execute().data}
        pending = [t for t in all_tasks if t["id"] not in done_ids]
        info = TASK_TYPES[task_type]
        if not pending:
            await query.edit_message_text(
                f"{info['emoji']} Không còn nhiệm vụ *{info['label']}*!\nAdmin sẽ thêm sớm 💪",
                parse_mode="Markdown"
            ); return
        task = pending[0]
        await query.edit_message_text(
            f"{info['emoji']} *NHIỆM VỤ #{task['id']} — {info['label']}*\n\n"
            f"📌 {task['title']}\n🎁 Thưởng: *{task['coin_reward']} {COIN_NAME}*\n\n"
            f"👆 Vượt link → Sao chép mã → Nhập `/nhapma <mã>`\n\n"
            f"🔗 {task['short_link']}\n\n📊 Còn {len(pending)} nhiệm vụ loại này",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Chọn loại khác", callback_data="nhiem_vu")]])
        )
    except Exception as e:
        logger.error(f"show_task lỗi: {e}")
        await query.edit_message_text("❌ Có lỗi xảy ra, thử lại!")

# ── ADMIN ──
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔧 *ADMIN PANEL*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Thêm NV Upto3", callback_data="adm_upto3"),
         InlineKeyboardButton("🔥 Thêm NV Upto4", callback_data="adm_upto4")],
        [InlineKeyboardButton("🌐 Thêm NV Link4m", callback_data="adm_link4m")],
        [InlineKeyboardButton("🛍️ Thêm sản phẩm", callback_data="adm_product"),
         InlineKeyboardButton("📦 Thêm hàng", callback_data="adm_stock")],
        [InlineKeyboardButton("🚫 Ban", callback_data="adm_ban"),
         InlineKeyboardButton("✅ Unban", callback_data="adm_unban")],
        [InlineKeyboardButton("👥 DS user", callback_data="adm_users"),
         InlineKeyboardButton("💰 Cộng coin", callback_data="adm_coin")],
    ]))

async def _add_task(update, context, task_type):
    info = TASK_TYPES[task_type]
    text = " ".join(context.args) if context.args else ""
    if not text or "|" not in text:
        await update.message.reply_text(f"📋 `/admin_add_{task_type} Tiêu đề | https://link.com`", parse_mode="Markdown"); return
    title, original_link = [x.strip() for x in text.split("|", 1)]
    code = gen_code()
    site_url = f"{WEBSITE_URL}/?code={code}"
    await update.message.reply_text("⏳ Đang rút gọn link...")
    try:
        short = await shorten_link4m(site_url) if task_type == "link4m" else await shorten_upto(site_url, info["advert"])
        db.table("tasks").insert({
            "title": title, "original_link": original_link, "short_link": short,
            "reward_code": code, "task_type": task_type, "coin_reward": info["coin"],
            "created_by": update.effective_user.id, "created_date": date.today().isoformat(), "is_active": True
        }).execute()
        await update.message.reply_text(
            f"✅ *{info['label']} thêm thành công!*\n\n📌 {title}\n🔗 {short}\n🎟️ Mã: `{code}`\n🎁 {info['coin']} {COIN_NAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"add_task lỗi: {e}")
        await update.message.reply_text(f"❌ Lỗi: {e}")

@admin_only
async def admin_add_upto3(u, c): await _add_task(u, c, "upto3")
@admin_only
async def admin_add_upto4(u, c): await _add_task(u, c, "upto4")
@admin_only
async def admin_add_link4m(u, c): await _add_task(u, c, "link4m")

@admin_only
async def admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    parts = [x.strip() for x in text.split("|")]
    if len(parts) < 3:
        await update.message.reply_text("`/admin_add_product Tên | Mô tả | Giá`", parse_mode="Markdown"); return
    try: price = int(parts[2])
    except: await update.message.reply_text("❌ Giá phải là số!"); return
    try:
        db.table("products").insert({"name": parts[0], "description": parts[1], "coin_price": price, "stock": 0, "is_active": True}).execute()
        await update.message.reply_text(f"✅ Thêm sản phẩm: *{parts[0]}* — {price} {COIN_NAME}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

@admin_only
async def admin_add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text or "|" not in text:
        await update.message.reply_text("`/admin_add_stock <ID> | nội dung`", parse_mode="Markdown"); return
    pid_str, item_data = [x.strip() for x in text.split("|", 1)]
    try: pid = int(pid_str)
    except: await update.message.reply_text("❌ ID phải là số!"); return
    try:
        prod = db.table("products").select("*").eq("id", pid).execute()
        if not prod.data: await update.message.reply_text("❌ Sản phẩm không tồn tại!"); return
        db.table("product_items").insert({"product_id": pid, "item_data": item_data, "is_sold": False}).execute()
        ns = prod.data[0]["stock"] + 1
        db.table("products").update({"stock": ns}).eq("id", pid).execute()
        await update.message.reply_text(f"✅ Thêm hàng! *{prod.data[0]['name']}* — tồn kho: {ns}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

@admin_only
async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("`/admin_ban <id>`", parse_mode="Markdown"); return
    try: tid = int(context.args[0])
    except: await update.message.reply_text("❌ ID phải là số!"); return
    u = get_user(tid)
    if not u: await update.message.reply_text("❌ User không tồn tại!"); return
    db.table("users").update({"is_banned": True}).eq("user_id", tid).execute()
    await update.message.reply_text(f"🚫 Đã ban `{tid}` ({u['full_name']})", parse_mode="Markdown")
    try: await context.bot.send_message(tid, "🚫 Tài khoản của bạn đã bị khóa.")
    except: pass

@admin_only
async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("`/admin_unban <id>`", parse_mode="Markdown"); return
    try: tid = int(context.args[0])
    except: await update.message.reply_text("❌ ID phải là số!"); return
    u = get_user(tid)
    if not u: await update.message.reply_text("❌ User không tồn tại!"); return
    db.table("users").update({"is_banned": False}).eq("user_id", tid).execute()
    await update.message.reply_text(f"✅ Đã unban `{tid}`", parse_mode="Markdown")
    try: await context.bot.send_message(tid, "✅ Tài khoản đã được mở khóa!")
    except: pass

@admin_only
async def admin_add_coin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: await update.message.reply_text("`/admin_add_coin <id> <coin>`", parse_mode="Markdown"); return
    try: tid, amt = int(context.args[0]), int(context.args[1])
    except: await update.message.reply_text("❌ ID và coin phải là số!"); return
    if not get_user(tid): await update.message.reply_text("❌ User không tồn tại!"); return
    nb = update_balance(tid, amt)
    await update.message.reply_text(f"✅ Cộng {amt} {COIN_NAME} → `{tid}` | Còn: {nb}", parse_mode="Markdown")
    try: await context.bot.send_message(tid, f"🎁 Admin cộng *{amt} {COIN_NAME}*!\n💰 Số dư: {nb}", parse_mode="Markdown")
    except: pass

@admin_only
async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        users = db.table("users").select("*").order("created_at", desc=True).limit(20).execute().data
        if not users: await update.message.reply_text("👥 Chưa có user."); return
        text = "👥 *DS USER (20 mới nhất)*\n\n"
        for u in users:
            text += f"{'🚫' if u['is_banned'] else '✅'} `{u['user_id']}` {u['full_name']} | 💰{u['balance']}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

@admin_only
async def admin_list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tasks = db.table("tasks").select("*").order("id", desc=True).limit(20).execute().data
        if not tasks: await update.message.reply_text("📋 Chưa có nhiệm vụ."); return
        text = "📋 *DS NHIỆM VỤ*\n\n"
        for t in tasks:
            info = TASK_TYPES.get(t.get("task_type", "upto3"), TASK_TYPES["upto3"])
            text += f"{'🟢' if t['is_active'] else '🔴'} {info['emoji']} #{t['id']} {t['title']} | `{t['reward_code']}`\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

# ── CALLBACK ──
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = q.data
    try:
        if d == "sodu":
            u = get_user(uid)
            await q.edit_message_text(f"💰 *Số dư*\n\n👤 {u['full_name']}\n🪙 *{u['balance']} {COIN_NAME}*", parse_mode="Markdown")
        elif d == "nhiem_vu":
            await q.edit_message_text(task_text(uid), parse_mode="Markdown", reply_markup=task_kb(uid))
        elif d == "tt_upto3": await show_task(q, uid, "upto3")
        elif d == "tt_upto4": await show_task(q, uid, "upto4")
        elif d == "tt_link4m": await show_task(q, uid, "link4m")
        elif d == "cuahang":
            products = db.table("products").select("*").eq("is_active", True).execute().data
            if not products: await q.edit_message_text("🛍️ Cửa hàng chưa có sản phẩm."); return
            text = "🛍️ *CỬA HÀNG*\n\n"
            for p in products:
                text += f"🆔 `{p['id']}` | {p['name']} | 💰{p['coin_price']} | {'%d còn' % p['stock'] if p['stock'] > 0 else 'Hết hàng'}\n"
            await q.edit_message_text(text + "\n💡 `/quy_doi <ID>`", parse_mode="Markdown")
        elif d == "quy_doi":
            await q.edit_message_text("🔄 Dùng lệnh: `/quy_doi <ID>`\nXem: /cuahang", parse_mode="Markdown")
        elif d in ("adm_upto3","adm_upto4","adm_link4m","adm_product","adm_stock","adm_ban","adm_unban","adm_coin"):
            hints = {
                "adm_upto3":  "⚡ `/admin_add_upto3 Tiêu đề | https://link.com`",
                "adm_upto4":  "🔥 `/admin_add_upto4 Tiêu đề | https://link.com`",
                "adm_link4m": "🌐 `/admin_add_link4m Tiêu đề | https://link.com`",
                "adm_product":"🛍️ `/admin_add_product Tên | Mô tả | Giá`",
                "adm_stock":  "📦 `/admin_add_stock <ID> | nội dung`",
                "adm_ban":    "🚫 `/admin_ban <user_id>`",
                "adm_unban":  "✅ `/admin_unban <user_id>`",
                "adm_coin":   "💰 `/admin_add_coin <user_id> <coin>`",
            }
            await q.edit_message_text(hints[d], parse_mode="Markdown")
        elif d == "adm_users":
            users = db.table("users").select("*").order("created_at", desc=True).limit(20).execute().data
            text = "👥 *DS USER*\n\n" + "".join(f"{'🚫' if u['is_banned'] else '✅'} `{u['user_id']}` {u['full_name']} | 💰{u['balance']}\n" for u in users)
            await q.edit_message_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"callback lỗi [{d}]: {e}")
        try: await q.edit_message_text("❌ Có lỗi xảy ra, thử lại!")
        except: pass

# ── MAIN ──
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    cmds = [
        ("start", start), ("sodu", cmd_sodu), ("nhiem_vu", cmd_nhiem_vu),
        ("nhapma", cmd_nhapma), ("cuahang", cmd_cuahang), ("quy_doi", cmd_quy_doi),
        ("admin", admin_panel), ("admin_add_upto3", admin_add_upto3),
        ("admin_add_upto4", admin_add_upto4), ("admin_add_link4m", admin_add_link4m),
        ("admin_add_product", admin_add_product), ("admin_add_stock", admin_add_stock),
        ("admin_ban", admin_ban), ("admin_unban", admin_unban),
        ("admin_add_coin", admin_add_coin), ("admin_list_users", admin_list_users),
        ("admin_list_tasks", admin_list_tasks),
    ]
    for cmd, fn in cmds:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(CallbackQueryHandler(callback_handler))
    print("🤖 Bot đang chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
