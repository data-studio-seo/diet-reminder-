"""
🥗 Diet Reminder Bot per Telegram
- Invia reminder dei pasti programmati
- Traccia peso e circonferenze settimanalmente
- Salva tutto in un database SQLite locale
"""

import os
import json
import logging
from datetime import datetime, time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import sqlite3

# ── Configurazione ──────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "IL_TUO_TOKEN_QUI")
DB_PATH = "diet_bot.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Stati per ConversationHandler
(
    MEAL_DAY, MEAL_NAME, MEAL_TIME, MEAL_RECIPE, MEAL_REMINDER_HOURS,
    PROGRESS_WEIGHT, PROGRESS_WAIST, PROGRESS_HIPS, PROGRESS_CHEST, PROGRESS_CONFIRM,
) = range(10)

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


# ── Database ────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,  -- 0=Lunedì ... 6=Domenica
            meal_name TEXT NOT NULL,        -- es. "Pranzo", "Cena"
            meal_time TEXT NOT NULL,        -- es. "13:00"
            recipe TEXT NOT NULL,           -- descrizione piatto
            reminder_hours_before REAL DEFAULT 2  -- ore prima per il reminder
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight REAL,
            waist REAL,
            hips REAL,
            chest REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            weekly_checkin_day INTEGER DEFAULT 0,  -- 0=Lunedì
            weekly_checkin_time TEXT DEFAULT '09:00'
        )
    """)
    conn.commit()
    conn.close()


def get_db():
    return sqlite3.connect(DB_PATH)


# ── Comandi base ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🥗 Ciao! Sono il tuo Diet Reminder Bot!\n\n"
        "Ecco cosa posso fare per te:\n\n"
        "📋 Gestione Pasti\n"
        "/aggiungi_pasto — Programma un pasto\n"
        "/pasti — Vedi i pasti della settimana\n"
        "/elimina_pasto — Rimuovi un pasto\n\n"
        "📊 Tracking Progressi\n"
        "/progresso — Registra peso e misure\n"
        "/storico — Vedi i tuoi progressi\n"
        "/impostazioni — Configura giorno/ora check-in\n\n"
        "💡 Tip: Aggiungi i tuoi pasti e riceverai un "
        "reminder automatico qualche ora prima!",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Comandi disponibili:*\n\n"
        "/start — Messaggio di benvenuto\n"
        "/aggiungi_pasto — Aggiungi un pasto al piano\n"
        "/pasti — Vedi piano settimanale\n"
        "/elimina_pasto — Elimina un pasto\n"
        "/progresso — Registra peso e misure\n"
        "/storico — Storico dei progressi\n"
        "/impostazioni — Imposta giorno check-in\n"
        "/help — Questo messaggio",
        parse_mode="Markdown",
    )


# ── Aggiungi Pasto (ConversationHandler) ───────────────────────
async def aggiungi_pasto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[g] for g in GIORNI]
    await update.message.reply_text(
        "📅 *Che giorno della settimana?*",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown",
    )
    return MEAL_DAY


async def meal_day_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.message.text.strip()
    if day not in GIORNI:
        await update.message.reply_text("Per favore scegli un giorno dalla lista.")
        return MEAL_DAY
    context.user_data["meal_day"] = GIORNI.index(day)
    context.user_data["meal_day_name"] = day

    keyboard = [["Colazione", "Spuntino mattina"], ["Pranzo", "Spuntino pomeriggio"], ["Cena"]]
    await update.message.reply_text(
        "🍽 *Che pasto è?*\n(Puoi anche scrivere un nome personalizzato)",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown",
    )
    return MEAL_NAME


async def meal_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["meal_name"] = update.message.text.strip()
    await update.message.reply_text(
        "⏰ *A che ora mangi?*\n(Formato HH:MM, es. 13:00)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return MEAL_TIME


async def meal_time_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text("❌ Formato non valido. Scrivi l'ora come HH:MM (es. 13:00)")
        return MEAL_TIME
    context.user_data["meal_time"] = text
    await update.message.reply_text(
        "🥘 *Cosa devi preparare?*\n"
        "Scrivi il piatto e/o la ricetta breve.\n\n"
        "_Esempio: Petto di pollo alla griglia con insalata mista e riso basmati (150g pollo, 80g riso)_",
        parse_mode="Markdown",
    )
    return MEAL_RECIPE


async def meal_recipe_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["meal_recipe"] = update.message.text.strip()
    keyboard = [["1 ora prima", "2 ore prima"], ["3 ore prima", "La mattina stessa"]]
    await update.message.reply_text(
        "🔔 *Quanto prima vuoi il reminder?*",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown",
    )
    return MEAL_REMINDER_HOURS


async def meal_reminder_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    hours_map = {
        "1 ora prima": 1,
        "2 ore prima": 2,
        "3 ore prima": 3,
        "la mattina stessa": -1,  # flag speciale: reminder alle 8:00
    }
    hours = hours_map.get(text, 2)
    context.user_data["meal_reminder_hours"] = hours

    # Salva nel DB
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO meals (user_id, day_of_week, meal_name, meal_time, recipe, reminder_hours_before) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            update.effective_user.id,
            context.user_data["meal_day"],
            context.user_data["meal_name"],
            context.user_data["meal_time"],
            context.user_data["meal_recipe"],
            hours,
        ),
    )
    conn.commit()
    conn.close()

    reminder_text = "alle 8:00 del giorno stesso" if hours == -1 else f"{int(hours)} ore prima"

    await update.message.reply_text(
        f"✅ *Pasto aggiunto!*\n\n"
        f"📅 {context.user_data['meal_day_name']}\n"
        f"🍽 {context.user_data['meal_name']} alle {context.user_data['meal_time']}\n"
        f"🥘 {context.user_data['meal_recipe']}\n"
        f"🔔 Reminder: {reminder_text}",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── Vedi Pasti ──────────────────────────────────────────────────
async def vedi_pasti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT day_of_week, meal_name, meal_time, recipe FROM meals "
        "WHERE user_id = ? ORDER BY day_of_week, meal_time",
        (update.effective_user.id,),
    )
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "📋 Non hai ancora pasti programmati.\nUsa /aggiungi_pasto per iniziare!"
        )
        return

    text = "📋 *Il tuo piano settimanale:*\n\n"
    current_day = -1
    for day, name, meal_time, recipe in rows:
        if day != current_day:
            current_day = day
            text += f"*{GIORNI[day]}*\n"
        text += f"  🕐 {meal_time} — *{name}*\n  └ {recipe}\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── Elimina Pasto ───────────────────────────────────────────────
async def elimina_pasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, day_of_week, meal_name, meal_time, recipe FROM meals "
        "WHERE user_id = ? ORDER BY day_of_week, meal_time",
        (update.effective_user.id,),
    )
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Non hai pasti da eliminare.")
        return

    buttons = []
    for meal_id, day, name, meal_time, recipe in rows:
        label = f"❌ {GIORNI[day]} {meal_time} - {name}: {recipe[:30]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"del_meal_{meal_id}")])

    await update.message.reply_text(
        "🗑 *Quale pasto vuoi eliminare?*",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def elimina_pasto_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    meal_id = int(query.data.replace("del_meal_", ""))

    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM meals WHERE id = ? AND user_id = ?", (meal_id, query.from_user.id))
    conn.commit()
    conn.close()

    await query.edit_message_text("✅ Pasto eliminato!")


# ── Registra Progressi (ConversationHandler) ───────────────────
async def progresso_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *Registriamo i tuoi progressi!*\n\n"
        "⚖️ Quanto pesi oggi? (in kg, es. 75.5)\n\n"
        "_Scrivi /salta per saltare una misurazione_",
        parse_mode="Markdown",
    )
    return PROGRESS_WEIGHT


async def progress_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/salta":
        context.user_data["progress_weight"] = None
    else:
        try:
            context.user_data["progress_weight"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido (es. 75.5)")
            return PROGRESS_WEIGHT

    await update.message.reply_text(
        "📏 *Circonferenza vita* (in cm)?\n_/salta per saltare_",
        parse_mode="Markdown",
    )
    return PROGRESS_WAIST


async def progress_waist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/salta":
        context.user_data["progress_waist"] = None
    else:
        try:
            context.user_data["progress_waist"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido (es. 85)")
            return PROGRESS_WAIST

    await update.message.reply_text(
        "📏 *Circonferenza fianchi* (in cm)?\n_/salta per saltare_",
        parse_mode="Markdown",
    )
    return PROGRESS_HIPS


async def progress_hips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/salta":
        context.user_data["progress_hips"] = None
    else:
        try:
            context.user_data["progress_hips"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido (es. 95)")
            return PROGRESS_HIPS

    await update.message.reply_text(
        "📏 *Circonferenza petto/torace* (in cm)?\n_/salta per saltare_",
        parse_mode="Markdown",
    )
    return PROGRESS_CHEST


async def progress_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/salta":
        context.user_data["progress_chest"] = None
    else:
        try:
            context.user_data["progress_chest"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido (es. 100)")
            return PROGRESS_CHEST

    # Salva
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO progress (user_id, date, weight, waist, hips, chest) VALUES (?, ?, ?, ?, ?, ?)",
        (
            update.effective_user.id,
            datetime.now().strftime("%Y-%m-%d"),
            context.user_data.get("progress_weight"),
            context.user_data.get("progress_waist"),
            context.user_data.get("progress_hips"),
            context.user_data.get("progress_chest"),
        ),
    )
    conn.commit()
    conn.close()

    # Riepilogo
    parts = ["✅ *Progressi registrati!*\n"]
    w = context.user_data.get("progress_weight")
    if w:
        parts.append(f"⚖️ Peso: {w} kg")
    waist = context.user_data.get("progress_waist")
    if waist:
        parts.append(f"📏 Vita: {waist} cm")
    hips = context.user_data.get("progress_hips")
    if hips:
        parts.append(f"📏 Fianchi: {hips} cm")
    chest = context.user_data.get("progress_chest")
    if chest:
        parts.append(f"📏 Petto: {chest} cm")

    # Confronto con ultima rilevazione
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT weight, waist, hips, chest FROM progress "
        "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 1 OFFSET 1",
        (update.effective_user.id,),
    )
    prev = c.fetchone()
    conn.close()

    if prev and w and prev[0]:
        diff = w - prev[0]
        emoji = "📉" if diff < 0 else "📈" if diff > 0 else "➡️"
        parts.append(f"\n{emoji} Variazione peso: {diff:+.1f} kg rispetto all'ultima volta")

    await update.message.reply_text("\n".join(parts), parse_mode="Markdown")
    return ConversationHandler.END


# ── Storico ─────────────────────────────────────────────────────
async def storico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT date, weight, waist, hips, chest FROM progress "
        "WHERE user_id = ? ORDER BY date DESC LIMIT 12",
        (update.effective_user.id,),
    )
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "📊 Nessun dato registrato ancora.\nUsa /progresso per iniziare!"
        )
        return

    text = "📊 *Storico progressi (ultime 12 rilevazioni):*\n\n"
    text += "```\n"
    text += f"{'Data':<12} {'Peso':>6} {'Vita':>6} {'Fian.':>6} {'Petto':>6}\n"
    text += "─" * 42 + "\n"
    for date, weight, waist, hips, chest in rows:
        w = f"{weight:.1f}" if weight else "  -  "
        wa = f"{waist:.0f}" if waist else "  -  "
        h = f"{hips:.0f}" if hips else "  -  "
        ch = f"{chest:.0f}" if chest else "  -  "
        text += f"{date:<12} {w:>6} {wa:>6} {h:>6} {ch:>6}\n"
    text += "```"

    await update.message.reply_text(text, parse_mode="Markdown")


# ── Impostazioni check-in settimanale ───────────────────────────
async def impostazioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[g] for g in GIORNI]
    await update.message.reply_text(
        "⚙️ *Impostazioni check-in settimanale*\n\n"
        "In quale giorno vuoi che ti chieda peso e misure?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown",
    )
    return "SETTINGS_DAY"


async def settings_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.message.text.strip()
    if day not in GIORNI:
        await update.message.reply_text("Scegli un giorno dalla lista.")
        return "SETTINGS_DAY"

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO user_settings (user_id, weekly_checkin_day) VALUES (?, ?)",
        (update.effective_user.id, GIORNI.index(day)),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Check-in settimanale impostato per ogni *{day}* alle 09:00!\n\n"
        "Riceverai un messaggio automatico per registrare i tuoi progressi.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ── Job schedulati ──────────────────────────────────────────────
async def send_meal_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Eseguito ogni 30 minuti. Controlla se c'è un pasto da ricordare."""
    now = datetime.now()
    current_day = now.weekday()  # 0=Lunedì

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT user_id, meal_name, meal_time, recipe, reminder_hours_before "
        "FROM meals WHERE day_of_week = ?",
        (current_day,),
    )
    meals = c.fetchall()
    conn.close()

    for user_id, meal_name, meal_time, recipe, reminder_hours in meals:
        meal_dt = datetime.strptime(meal_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )

        if reminder_hours == -1:
            # Reminder la mattina: manda alle 8:00
            reminder_dt = meal_dt.replace(hour=8, minute=0)
        else:
            from datetime import timedelta
            reminder_dt = meal_dt - timedelta(hours=reminder_hours)

        # Controlla se siamo nella finestra di 30 minuti del reminder
        diff_minutes = (now - reminder_dt).total_seconds() / 60
        if 0 <= diff_minutes < 30:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🔔 *Reminder: {meal_name} alle {meal_time}!*\n\n"
                        f"🥘 Devi preparare:\n{recipe}\n\n"
                        f"💪 Forza, segui il piano!"
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Errore invio reminder a {user_id}: {e}")


async def send_weekly_checkin(context: ContextTypes.DEFAULT_TYPE):
    """Eseguito ogni giorno alle 9:00. Manda check-in a chi lo ha impostato."""
    now = datetime.now()
    current_day = now.weekday()

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT user_id FROM user_settings WHERE weekly_checkin_day = ?",
        (current_day,),
    )
    users = c.fetchall()
    conn.close()

    for (user_id,) in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    "📊 *È il giorno del check-in settimanale!*\n\n"
                    "Come stanno andando i progressi? 💪\n"
                    "Usa /progresso per registrare peso e misure di oggi!"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Errore invio check-in a {user_id}: {e}")


# ── Main ────────────────────────────────────────────────────────
def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation: Aggiungi Pasto
    meal_conv = ConversationHandler(
        entry_points=[CommandHandler("aggiungi_pasto", aggiungi_pasto_start)],
        states={
            MEAL_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_day_received)],
            MEAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_name_received)],
            MEAL_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_time_received)],
            MEAL_RECIPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_recipe_received)],
            MEAL_REMINDER_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_reminder_received)],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )

    # Conversation: Progressi
    progress_conv = ConversationHandler(
        entry_points=[CommandHandler("progresso", progresso_start)],
        states={
            PROGRESS_WEIGHT: [MessageHandler(filters.TEXT, progress_weight)],
            PROGRESS_WAIST: [MessageHandler(filters.TEXT, progress_waist)],
            PROGRESS_HIPS: [MessageHandler(filters.TEXT, progress_hips)],
            PROGRESS_CHEST: [MessageHandler(filters.TEXT, progress_chest)],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )

    # Conversation: Impostazioni
    settings_conv = ConversationHandler(
        entry_points=[CommandHandler("impostazioni", impostazioni)],
        states={
            "SETTINGS_DAY": [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_day)],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(meal_conv)
    app.add_handler(progress_conv)
    app.add_handler(settings_conv)
    app.add_handler(CommandHandler("pasti", vedi_pasti))
    app.add_handler(CommandHandler("elimina_pasto", elimina_pasto))
    app.add_handler(CallbackQueryHandler(elimina_pasto_callback, pattern=r"^del_meal_"))
    app.add_handler(CommandHandler("storico", storico))

    # Job schedulati
    job_queue = app.job_queue
    # Controlla reminder pasti ogni 30 minuti
    job_queue.run_repeating(send_meal_reminders, interval=1800, first=10)
    # Controlla check-in giornaliero alle 9:00
    job_queue.run_daily(send_weekly_checkin, time=time(hour=9, minute=0))

    logger.info("🥗 Diet Bot avviato!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
