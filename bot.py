import logging
import time
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

from config import BOT_TOKEN, SUPPORT_URL, ADD_GROUP_URL
from db import (
    init_db,
    get_group_settings,
    set_group_enabled,
    set_group_cooldown,
    update_user_stats,
    get_user_stats,
    get_leaderboard,
    get_streak_leaderboard,
    get_death_leaderboard,
    get_last_play,
    set_last_play,
    set_revenge_target,
    get_revenge_target,
    add_revenge_win,
    create_duel,
    get_duel_for_target,
    delete_duel,
    add_duel_result,
)
from game import (
    spin_chamber,
    random_survive_message,
    random_lose_message,
    random_spin_message,
)

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


def start_menu():
    keyboard = [
        [InlineKeyboardButton("🎮 Oyun Paneli", callback_data="open_panel")],
        [InlineKeyboardButton("➕ Beni Gruba Ekle", url=ADD_GROUP_URL)],
        [InlineKeyboardButton("🛟 Destek", url=SUPPORT_URL)],
    ]
    return InlineKeyboardMarkup(keyboard)


def panel_menu():
    keyboard = [
        [InlineKeyboardButton("🔫 Tetiği Çek", callback_data="play_rr")],
        [InlineKeyboardButton("📊 İstatistik", callback_data="my_stats")],
        [InlineKeyboardButton("🏆 Liderlik", callback_data="leaderboard")],
        [InlineKeyboardButton("🔥 Seri Yaşayanlar", callback_data="streaks")],
        [InlineKeyboardButton("☠️ Ölüm Sayısı", callback_data="deaths")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎯 *KGB Rus Ruleti Botu*\n\n"
        "Grubunda arkadaşlarınla riskli ve eğlenceli bir oyun oyna.\n\n"
        "• /oyna - tetiği çek\n"
        "• /panel - butonlu panel\n"
        "• /istatistik - kişisel verin\n"
        "• /liderlik - grup sıralaması\n"
        "• /seriler - en iyi seriler\n"
        "• /olumsayisi - en çok ölenler\n"
        "• /intikam @kisi - intikam hedefi belirle\n"
        "• /duello @kisi - düello isteği gönder\n\n"
        "Botu gruba ekleyip admin yapmayı unutma."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=start_menu())


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update.effective_chat.type):
        await update.message.reply_text("Bu panel grup içinde daha eğlenceli 😏", reply_markup=start_menu())
        return

    await update.message.reply_text("🎮 Oyun Paneli", reply_markup=panel_menu())


async def do_russian_roulette(message_source, user, chat, bot):
    settings = get_group_settings(chat.id)

    if not settings["enabled"]:
        await message_source.reply_text("🚫 Oyun bu grupta kapalı.")
        return

    last_play = get_last_play(chat.id, user.id)
    now = int(time.time())
    remaining = settings["cooldown"] - (now - last_play)

    if remaining > 0:
        await message_source.reply_text(f"⏳ Tekrar oynamak için {remaining} saniye bekle.")
        return

    try:
        member = await bot.get_chat_member(chat.id, bot.id)
        if not member.can_restrict_members:
            await message_source.reply_text("Beni admin yap ve kullanıcı yasaklama yetkisi ver.")
            return
    except Exception:
        await message_source.reply_text("Bot yetkileri kontrol edilemedi.")
        return

    set_last_play(chat.id, user.id)

    spin_msg = await message_source.reply_text(random_spin_message())
    await asyncio.sleep(1.4)
    await spin_msg.edit_text("🎯 Sonuç hesaplanıyor...")
    await asyncio.sleep(1.2)

    survived = spin_chamber(settings["loss_chance"])
    update_user_stats(chat.id, user.id, user.username or "", user.first_name or "", survived)

    if survived:
        stats = get_user_stats(chat.id, user.id)
        await spin_msg.edit_text(
            f"{random_survive_message()}\n\n"
            f"👤 {user.first_name}\n"
            f"🔥 Güncel seri: {stats['streak']}\n"
            f"🏅 En iyi seri: {stats['best_streak']}"
        )
    else:
        try:
            await bot.ban_chat_member(chat.id, user.id)
            await bot.unban_chat_member(chat.id, user.id, only_if_banned=True)

            target_id = get_revenge_target(chat.id, user.id)
            revenge_text = ""
            if target_id:
                add_revenge_win(chat.id, target_id)
                revenge_text = "\n⚔️ İntikam zinciri işlendi."

            await spin_msg.edit_text(
                f"{random_lose_message()}\n\n"
                f"💥 {user.first_name} kaybetti ve gruptan atıldı!{revenge_text}"
            )
        except Exception as e:
            await spin_msg.edit_text(
                f"{random_lose_message()}\n\n"
                f"💥 {user.first_name} kaybetti ama atılamadı.\nHata: {e}"
            )


async def oyna(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not is_group(chat.type):
        await update.message.reply_text("Bu oyun sadece grupta oynanır.", reply_markup=start_menu())
        return

    await do_russian_roulette(update.message, user, chat, context.bot)


async def rusruleti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await oyna(update, context)


async def istatistik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut grup içinde çalışır.")
        return

    stats = get_user_stats(chat.id, user.id)
    await update.message.reply_text(
        f"📊 {user.first_name} istatistikleri:\n\n"
        f"🎮 Oyun: {stats['plays']}\n"
        f"✅ Hayatta kalma: {stats['survives']}\n"
        f"☠️ Ölüm: {stats['losses']}\n"
        f"🔥 Güncel seri: {stats['streak']}\n"
        f"🏅 En iyi seri: {stats['best_streak']}\n"
        f"⚔️ İntikam kazancı: {stats['revenge_wins']}\n"
        f"🥊 Düello galibiyet: {stats['duel_wins']}\n"
        f"💀 Düello mağlubiyet: {stats['duel_losses']}"
    )


async def liderlik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not is_group(chat.type):
        await update.message.reply_text("Bu komut grup içinde çalışır.")
        return

    rows = get_leaderboard(chat.id)
    if not rows:
        await update.message.reply_text("Henüz veri yok.")
        return

    text = "🏆 Liderlik Tablosu\n\n"
    for i, row in enumerate(rows, start=1):
        first_name, username, survives, losses, plays, best_streak = row
        display = first_name
        if username:
            display += f" (@{username})"
        text += f"{i}. {display}\n   ✅ {survives} | ☠️ {losses} | 🎮 {plays} | 🔥 {best_streak}\n"

    await update.message.reply_text(text)


async def seriler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not is_group(chat.type):
        await update.message.reply_text("Bu komut grup içinde çalışır.")
        return

    rows = get_streak_leaderboard(chat.id)
    if not rows:
        await update.message.reply_text("Henüz veri yok.")
        return

    text = "🔥 Seri Yaşayanlar\n\n"
    for i, row in enumerate(rows, start=1):
        first_name, username, best_streak = row
        display = first_name
        if username:
            display += f" (@{username})"
        text += f"{i}. {display} - 🔥 {best_streak}\n"

    await update.message.reply_text(text)


async def olumsayisi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not is_group(chat.type):
        await update.message.reply_text("Bu komut grup içinde çalışır.")
        return

    rows = get_death_leaderboard(chat.id)
    if not rows:
        await update.message.reply_text("Henüz veri yok.")
        return

    text = "☠️ Ölüm Sayısı Liderliği\n\n"
    for i, row in enumerate(rows, start=1):
        first_name, username, losses = row
        display = first_name
        if username:
            display += f" (@{username})"
        text += f"{i}. {display} - ☠️ {losses}\n"

    await update.message.reply_text(text)


async def intikam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut grup içinde çalışır.")
        return

    if not context.args:
        await update.message.reply_text("Kullanım: /intikam @kullanici")
        return

    target_username = context.args[0].replace("@", "").lower()
    set_revenge_target(chat.id, user.id, user.id)
    await update.message.reply_text(
        f"⚔️ {user.first_name}, intikam yemini etti.\n"
        f"Hedef olarak @{target_username} seçildi.\n"
        f"(Şimdilik kullanıcı adı bazlı gösterim, gelişmiş mention sistemi sonra eklenebilir.)"
    )


async def duello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not is_group(chat.type):
        await update.message.reply_text("Bu komut grup içinde çalışır.")
        return

    if not context.args:
        await update.message.reply_text("Kullanım: /duello @kullanici")
        return

    target_name = context.args[0]
    create_duel(chat.id, user.id, user.first_name, 0, target_name)
    await update.message.reply_text(
        f"🥊 {user.first_name}, {target_name} kişisine düello çağrısı gönderdi!\n"
        f"Hedef kişi /kabulet yazarak kabul edebilir."
    )


async def kabulet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    duel = get_duel_for_target(chat.id, user.id)

    if not duel:
        await update.message.reply_text("Sana gelen aktif düello yok.")
        return

    challenger_id, challenger_name, target_id, target_name = duel

    spin_msg = await update.message.reply_text("🥊 Düello başlıyor...")
    await asyncio.sleep(1.5)
    await spin_msg.edit_text("🔫 İki taraf da tetiğe uzandı...")
    await asyncio.sleep(1.5)

    challenger_survives = spin_chamber(0.5)

    if challenger_survives:
        winner_id = challenger_id
        loser_id = user.id
        winner_name = challenger_name
        loser_name = user.first_name
    else:
        winner_id = user.id
        loser_id = challenger_id
        winner_name = user.first_name
        loser_name = challenger_name

    add_duel_result(chat.id, winner_id, loser_id)
    delete_duel(chat.id, challenger_id, user.id)

    try:
        await context.bot.ban_chat_member(chat.id, loser_id)
        await context.bot.unban_chat_member(chat.id, loser_id, only_if_banned=True)
    except Exception:
        pass

    await spin_msg.edit_text(
        f"💥 Düello bitti!\n\n"
        f"🏆 Kazanan: {winner_name}\n"
        f"☠️ Kaybeden: {loser_name}"
    )


async def ac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update.effective_chat.type):
        await update.message.reply_text("Bu komut sadece grupta çalışır.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("Sadece admin kullanabilir.")
        return
    set_group_enabled(update.effective_chat.id, True)
    await update.message.reply_text("✅ Oyun açıldı.")


async def kapat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update.effective_chat.type):
        await update.message.reply_text("Bu komut sadece grupta çalışır.")
        return
    if not await is_admin(update, context):
        await update.message.reply_text("Sadece admin kullanabilir.")
        return
    set_group_enabled(update.effective_chat.id, False)
    await update.message.reply_text("🚫 Oyun kapatıldı.")


async def cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update.effective_chat.type):
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

    set_group_cooldown(update.effective_chat.id, seconds)
    await update.message.reply_text(f"⏳ Cooldown {seconds} saniye oldu.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat

    await query.answer()

    if query.data == "open_panel":
        await query.message.reply_text("🎮 Oyun Paneli", reply_markup=panel_menu())
        return

    if not is_group(chat.type):
        await query.message.reply_text("Bu butonlar grup içinde daha iyi çalışır.")
        return

    if query.data == "play_rr":
        await do_russian_roulette(query.message, user, chat, context.bot)
        return

    if query.data == "my_stats":
        stats = get_user_stats(chat.id, user.id)
        await query.message.reply_text(
            f"📊 {user.first_name} istatistikleri:\n\n"
            f"🎮 Oyun: {stats['plays']}\n"
            f"✅ Hayatta kalma: {stats['survives']}\n"
            f"☠️ Ölüm: {stats['losses']}\n"
            f"🔥 Güncel seri: {stats['streak']}\n"
            f"🏅 En iyi seri: {stats['best_streak']}\n"
            f"⚔️ İntikam kazancı: {stats['revenge_wins']}\n"
            f"🥊 Düello galibiyet: {stats['duel_wins']}\n"
            f"💀 Düello mağlubiyet: {stats['duel_losses']}"
        )
        return

    if query.data == "leaderboard":
        rows = get_leaderboard(chat.id)
        if not rows:
            await query.message.reply_text("Henüz veri yok.")
            return
        text = "🏆 Liderlik Tablosu\n\n"
        for i, row in enumerate(rows, start=1):
            first_name, username, survives, losses, plays, best_streak = row
            display = first_name
            if username:
                display += f" (@{username})"
            text += f"{i}. {display}\n   ✅ {survives} | ☠️ {losses} | 🎮 {plays} | 🔥 {best_streak}\n"
        await query.message.reply_text(text)
        return

    if query.data == "streaks":
        rows = get_streak_leaderboard(chat.id)
        if not rows:
            await query.message.reply_text("Henüz veri yok.")
            return
        text = "🔥 Seri Yaşayanlar\n\n"
        for i, row in enumerate(rows, start=1):
            first_name, username, best_streak = row
            display = first_name
            if username:
                display += f" (@{username})"
            text += f"{i}. {display} - 🔥 {best_streak}\n"
        await query.message.reply_text(text)
        return

    if query.data == "deaths":
        rows = get_death_leaderboard(chat.id)
        if not rows:
            await query.message.reply_text("Henüz veri yok.")
            return
        text = "☠️ Ölüm Sayısı Liderliği\n\n"
        for i, row in enumerate(rows, start=1):
            first_name, username, losses = row
            display = first_name
            if username:
                display += f" (@{username})"
            text += f"{i}. {display} - ☠️ {losses}\n"
        await query.message.reply_text(text)
        return


def main():
    try:
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN bulunamadı.")

        init_db()

        app = Application.builder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("panel", panel))
        app.add_handler(CommandHandler("oyna", oyna))
        app.add_handler(CommandHandler("rusruleti", rusruleti))
        app.add_handler(CommandHandler("rurulet", rusruleti))
        app.add_handler(CommandHandler("istatistik", istatistik))
        app.add_handler(CommandHandler("liderlik", liderlik))
        app.add_handler(CommandHandler("seriler", seriler))
        app.add_handler(CommandHandler("olumsayisi", olumsayisi))
        app.add_handler(CommandHandler("intikam", intikam))
        app.add_handler(CommandHandler("duello", duello))
        app.add_handler(CommandHandler("kabulet", kabulet))
        app.add_handler(CommandHandler("ac", ac))
        app.add_handler(CommandHandler("kapat", kapat))
        app.add_handler(CommandHandler("cooldown", cooldown))
        app.add_handler(CallbackQueryHandler(button_handler))

        print("Bot çalışıyor...")
        app.run_polling(drop_pending_updates=True)

    except Exception as e:
        print(f"BOT KRİTİK HATA: {e}")
        raise


if __name__ == "__main__":
    main()
