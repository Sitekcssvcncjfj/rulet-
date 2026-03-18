import logging
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from config import BOT_TOKEN
from db import (
    init_db,
    get_group_settings,
    set_group_enabled,
    set_group_cooldown,
    update_user_stats,
    get_user_stats,
    get_leaderboard,
    get_last_play,
    set_last_play,
)
from game import spin_chamber

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


def is_group(chat_type):
    return chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ["administrator", "creator"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 Rus Ruleti Botu aktif!\n\n"
        "Komutlar:\n"
        "/rusruleti - oyunu başlat\n"
        "/panel - butonlu oyun paneli\n"
        "/istatistik - kendi istatistiğin\n"
        "/liderlik - grup liderlik tablosu\n"
        "/ac - oyunu aç (admin)\n"
        "/kapat - oyunu kapat (admin)\n"
        "/cooldown 15 - cooldown ayarla (admin)"
    )


async def rusruleti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat
    user = update.effective_user
    bot = context.bot

    if not is_group(chat.type):
        await message.reply_text("Bu oyun sadece gruplarda oynanır.")
        return

    settings = get_group_settings(chat.id)

    if not settings["enabled"]:
        await message.reply_text("🚫 Oyun bu grupta kapalı.")
        return

    last_play = get_last_play(chat.id, user.id)
    now = int(time.time())
    remaining = settings["cooldown"] - (now - last_play)

    if remaining > 0:
        await message.reply_text(f"⏳ Tekrar oynamak için {remaining} saniye bekle.")
        return

    try:
        member = await bot.get_chat_member(chat.id, bot.id)
        if not member.can_restrict_members:
            await message.reply_text("Beni admin yap ve kullanıcı yasaklama yetkisi ver.")
            return
    except Exception:
        await message.reply_text("Bot yetkileri kontrol edilemedi.")
        return

    set_last_play(chat.id, user.id)

    await message.reply_text("🔫 Tambur çevriliyor...")

    survived = spin_chamber(settings["loss_chance"])
    update_user_stats(chat.id, user.id, user.username or "", user.first_name or "", survived)

    if survived:
        await message.reply_text(f"😎 {user.first_name} hayatta kaldı!")
    else:
        try:
            await bot.ban_chat_member(chat.id, user.id)
            await bot.unban_chat_member(chat.id, user.id, only_if_banned=True)
            await message.reply_text(f"💥 {user.first_name} kaybetti ve gruptan atıldı!")
        except Exception as e:
            await message.reply_text(f"💥 {user.first_name} kaybetti ama atılamadı.\nHata: {e}")


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not is_group(chat.type):
        await update.message.reply_text("Panel sadece grupta çalışır.")
        return

    keyboard = [
        [InlineKeyboardButton("🔫 Tetiği Çek", callback_data="play_rr")],
        [InlineKeyboardButton("📊 İstatistik", callback_data="my_stats")],
        [InlineKeyboardButton("🏆 Liderlik", callback_data="leaderboard")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🎯 Rus Ruleti Paneli", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat
    bot = context.bot

    await query.answer()

    if not is_group(chat.type):
        await query.edit_message_text("Bu panel sadece gruplarda çalışır.")
        return

    if query.data == "my_stats":
        stats = get_user_stats(chat.id, user.id)
        await query.message.reply_text(
            f"📊 {user.first_name} istatistikleri:\n"
            f"Oyun: {stats['plays']}\n"
            f"Hayatta Kalma: {stats['survives']}\n"
            f"Kaybetme: {stats['losses']}"
        )
        return

    if query.data == "leaderboard":
        rows = get_leaderboard(chat.id)
        if not rows:
            await query.message.reply_text("Henüz veri yok.")
            return

        text = "🏆 Liderlik Tablosu:\n\n"
        for i, row in enumerate(rows, start=1):
            first_name, username, survives, losses, plays = row
            display = f"{first_name}"
            if username:
                display += f" (@{username})"
            text += f"{i}. {display} - ✅ {survives} | 💥 {losses} | 🎮 {plays}\n"

        await query.message.reply_text(text)
        return

    if query.data == "play_rr":
        settings = get_group_settings(chat.id)

        if not settings["enabled"]:
            await query.message.reply_text("🚫 Oyun bu grupta kapalı.")
            return

        last_play = get_last_play(chat.id, user.id)
        now = int(time.time())
        remaining = settings["cooldown"] - (now - last_play)

        if remaining > 0:
            await query.message.reply_text(f"⏳ {remaining} saniye sonra tekrar dene.")
            return

        try:
            member = await bot.get_chat_member(chat.id, bot.id)
            if not member.can_restrict_members:
                await query.message.reply_text("Beni admin yap ve ban yetkisi ver.")
                return
        except Exception:
            await query.message.reply_text("Yetki kontrolünde hata oluştu.")
            return

        set_last_play(chat.id, user.id)
        survived = spin_chamber(settings["loss_chance"])
        update_user_stats(chat.id, user.id, user.username or "", user.first_name or "", survived)

        if survived:
            await query.message.reply_text(f"😎 {user.first_name} hayatta kaldı!")
        else:
            try:
                await bot.ban_chat_member(chat.id, user.id)
                await bot.unban_chat_member(chat.id, user.id, only_if_banned=True)
                await query.message.reply_text(f"💥 {user.first_name} kaybetti ve gruptan atıldı!")
            except Exception as e:
                await query.message.reply_text(f"💥 {user.first_name} kaybetti ama atılamadı.\nHata: {e}")


async def istatistik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut sadece grupta çalışır.")
        return

    stats = get_user_stats(chat.id, user.id)
    await update.message.reply_text(
        f"📊 {user.first_name} istatistikleri:\n"
        f"Oyun: {stats['plays']}\n"
        f"Hayatta Kalma: {stats['survives']}\n"
        f"Kaybetme: {stats['losses']}"
    )


async def liderlik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut sadece grupta çalışır.")
        return

    rows = get_leaderboard(chat.id)
    if not rows:
        await update.message.reply_text("Henüz veri yok.")
        return

    text = "🏆 Liderlik Tablosu:\n\n"
    for i, row in enumerate(rows, start=1):
        first_name, username, survives, losses, plays = row
        display = f"{first_name}"
        if username:
            display += f" (@{username})"
        text += f"{i}. {display} - ✅ {survives} | 💥 {losses} | 🎮 {plays}\n"

    await update.message.reply_text(text)


async def ac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut sadece grupta çalışır.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Sadece admin kullanabilir.")
        return

    set_group_enabled(chat.id, True)
    await update.message.reply_text("✅ Oyun açıldı.")


async def kapat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut sadece grupta çalışır.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Sadece admin kullanabilir.")
        return

    set_group_enabled(chat.id, False)
    await update.message.reply_text("🚫 Oyun kapatıldı.")


async def cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut sadece grupta çalışır.")
        return

    if not await is_admin(update, context):
        await update.message.reply_text("Sadece admin kullanabilir.")
        return

    if not context.args:
        await update.message.reply_text("Kullanım: /cooldown 15")
        return

    try:
        seconds = int(context.args[0])
        if seconds < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Geçerli bir sayı gir.")
        return

    set_group_cooldown(chat.id, seconds)
    await update.message.reply_text(f"⏳ Cooldown {seconds} saniye olarak ayarlandı.")


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN bulunamadı.")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rusruleti", rusruleti))
    app.add_handler(CommandHandler("rurulet", rusruleti))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("istatistik", istatistik))
    app.add_handler(CommandHandler("liderlik", liderlik))
    app.add_handler(CommandHandler("ac", ac))
    app.add_handler(CommandHandler("kapat", kapat))
    app.add_handler(CommandHandler("cooldown", cooldown))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
