"""
🥗 Diet Reminder Bot v2 per Telegram
- Reminder pasti con minuti personalizzabili
- Reminder spesa il giorno prima
- Copia pasti su piu' giorni
- Comando /oggi
- Modifica pasti
- Messaggi motivazionali random
"""

import os
import random
import logging
from datetime import datetime, time, timedelta
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

# Stati ConversationHandler
(
    MEAL_DAYS, MEAL_NAME, MEAL_TIME, MEAL_RECIPE, MEAL_REMINDER,
    MEAL_REMINDER_CUSTOM,
    PROGRESS_WEIGHT, PROGRESS_WAIST, PROGRESS_HIPS, PROGRESS_CHEST,
    SETTINGS_DAY, SETTINGS_GROCERY_TIME,
    EDIT_SELECT, EDIT_FIELD, EDIT_VALUE,
) = range(15)

GIORNI = ["Lunedi", "Martedi", "Mercoledi", "Giovedi", "Venerdi", "Sabato", "Domenica"]
GIORNI_SHORT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

FRASI_MOTIVAZIONALI = [
    "💪 Ogni pasto sano e' un passo verso il tuo obiettivo!",
    "🌟 Non contare i giorni, fai che i giorni contino!",
    "🔥 La disciplina e' il ponte tra i tuoi obiettivi e i risultati!",
    "🏆 Non mollare! I risultati arrivano a chi e' costante!",
    "💚 Il tuo corpo ti ringraziera' per le scelte di oggi!",
    "⭐ Sei piu' forte di qualsiasi scusa!",
    "🎯 Piccoli passi ogni giorno portano a grandi cambiamenti!",
    "💎 Investire nella tua salute e' il miglior investimento!",
    "🚀 Oggi e' un altro giorno per essere la versione migliore di te!",
    "🌈 La costanza batte il talento quando il talento non e' costante!",
    "💪 Chi si arrende non vincera' mai. Chi vince non si arrende mai!",
    "🍏 Mangiare bene non e' una punizione, e' un atto d'amore verso te stesso!",
    "⚡ L'energia che metti nel tuo corpo determina l'energia della tua giornata!",
    "🎉 Complimenti per essere ancora qui, giorno dopo giorno!",
    "🌻 Non serve essere perfetti, basta essere costanti!",
]


# ── Database ────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            meal_name TEXT NOT NULL,
            meal_time TEXT NOT NULL,
            recipe TEXT NOT NULL,
            reminder_minutes_before INTEGER DEFAULT 120
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
            weekly_checkin_day INTEGER DEFAULT 0,
            weekly_checkin_time TEXT DEFAULT '09:00',
            grocery_reminder_time TEXT DEFAULT '20:00'
        )
    """)
    # Migrazione: aggiungi colonna grocery_reminder_time se non esiste
    try:
        c.execute("ALTER TABLE user_settings ADD COLUMN grocery_reminder_time TEXT DEFAULT '20:00'")
    except sqlite3.OperationalError:
        pass
    # Migrazione: rinomina colonna reminder se necessario
    try:
        c.execute("ALTER TABLE meals ADD COLUMN reminder_minutes_before INTEGER DEFAULT 120")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def get_db():
    return sqlite3.connect(DB_PATH)


# ── Messaggi motivazionali ──────────────────────────────────────
def get_motivational():
    return random.choice(FRASI_MOTIVAZIONALI)


# ── Comandi base ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🥗 Ciao! Sono il tuo Diet Reminder Bot!\n\n"
        "Ecco cosa posso fare per te:\n\n"
        "📋 Gestione Pasti\n"
        "/aggiungi_pasto - Programma un pasto\n"
        "/pasti - Vedi piano settimanale\n"
        "/oggi - Pasti di oggi\n"
        "/modifica_pasto - Modifica un pasto\n"
        "/copia_pasto - Copia un pasto su altri giorni\n"
        "/elimina_pasto - Rimuovi un pasto\n\n"
        "📊 Tracking Progressi\n"
        "/progresso - Registra peso e misure\n"
        "/storico - Vedi i tuoi progressi\n\n"
        "⚙ Impostazioni\n"
        "/impostazioni - Configura check-in e reminder spesa\n\n"
        "💡 Tip: Riceverai reminder prima di ogni pasto "
        "e la sera prima la lista della spesa per il giorno dopo!"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Comandi disponibili:\n\n"
        "/start - Benvenuto\n"
        "/aggiungi_pasto - Aggiungi pasto\n"
        "/pasti - Piano settimanale\n"
        "/oggi - Pasti di oggi\n"
        "/modifica_pasto - Modifica un pasto\n"
        "/copia_pasto - Copia pasto su altri giorni\n"
        "/elimina_pasto - Elimina un pasto\n"
        "/progresso - Registra peso e misure\n"
        "/storico - Storico progressi\n"
        "/impostazioni - Impostazioni\n"
        "/motivami - Messaggio motivazionale\n"
        "/annulla - Annulla operazione\n"
        "/help - Questo messaggio"
    )


async def motivami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_motivational())


# ── Aggiungi Pasto ──────────────────────────────────────────────
async def aggiungi_pasto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[g] for g in GIORNI]
    keyboard.append(["Lun-Ven (feriali)", "Tutti i giorni"])
    await update.message.reply_text(
        "📅 Che giorno/i della settimana?\n"
        "Puoi scegliere un giorno singolo o una scorciatoia.",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return MEAL_DAYS


async def meal_days_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Lun-Ven (feriali)":
        context.user_data["meal_days"] = [0, 1, 2, 3, 4]
        context.user_data["meal_days_label"] = "Lun-Ven"
    elif text == "Tutti i giorni":
        context.user_data["meal_days"] = [0, 1, 2, 3, 4, 5, 6]
        context.user_data["meal_days_label"] = "Tutti i giorni"
    elif text in GIORNI:
        idx = GIORNI.index(text)
        context.user_data["meal_days"] = [idx]
        context.user_data["meal_days_label"] = text
    else:
        await update.message.reply_text("Per favore scegli dalla lista.")
        return MEAL_DAYS

    keyboard = [["Colazione", "Spuntino mattina"], ["Pranzo", "Spuntino pomeriggio"], ["Cena"]]
    await update.message.reply_text(
        "🍽 Che pasto e'?\n(Puoi anche scrivere un nome personalizzato)",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return MEAL_NAME


async def meal_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["meal_name"] = update.message.text.strip()
    await update.message.reply_text(
        "⏰ A che ora mangi? (Formato HH:MM, es. 13:00)",
        reply_markup=ReplyKeyboardRemove(),
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
        "🥘 Cosa devi preparare?\n"
        "Scrivi il piatto e/o la ricetta breve.\n\n"
        "Esempio: Petto di pollo alla griglia con insalata mista e riso basmati (150g pollo, 80g riso)"
    )
    return MEAL_RECIPE


async def meal_recipe_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["meal_recipe"] = update.message.text.strip()
    keyboard = [
        ["15 min prima", "30 min prima"],
        ["1 ora prima", "2 ore prima"],
        ["3 ore prima", "La mattina stessa"],
        ["Personalizzato"],
    ]
    await update.message.reply_text(
        "🔔 Quanto prima vuoi il reminder?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return MEAL_REMINDER


async def meal_reminder_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    minutes_map = {
        "15 min prima": 15,
        "30 min prima": 30,
        "1 ora prima": 60,
        "2 ore prima": 120,
        "3 ore prima": 180,
        "la mattina stessa": -1,
    }

    if text == "personalizzato":
        await update.message.reply_text(
            "⏱ Scrivi quanti minuti prima vuoi il reminder.\n"
            "Esempio: 45 (per 45 minuti prima)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return MEAL_REMINDER_CUSTOM

    minutes = minutes_map.get(text, 120)
    context.user_data["meal_reminder_minutes"] = minutes
    return await save_meal(update, context)


async def meal_reminder_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        minutes = int(text)
        if minutes < 1 or minutes > 1440:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Inserisci un numero tra 1 e 1440 (minuti).")
        return MEAL_REMINDER_CUSTOM

    context.user_data["meal_reminder_minutes"] = minutes
    return await save_meal(update, context)


async def save_meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = context.user_data["meal_days"]
    minutes = context.user_data["meal_reminder_minutes"]

    conn = get_db()
    c = conn.cursor()
    for day in days:
        c.execute(
            "INSERT INTO meals (user_id, day_of_week, meal_name, meal_time, recipe, reminder_minutes_before) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                update.effective_user.id,
                day,
                context.user_data["meal_name"],
                context.user_data["meal_time"],
                context.user_data["meal_recipe"],
                minutes,
            ),
        )
    conn.commit()
    conn.close()

    if minutes == -1:
        reminder_text = "alle 8:00 del giorno stesso"
    elif minutes >= 60:
        h = minutes // 60
        m = minutes % 60
        reminder_text = f"{h} ora/e" + (f" e {m} min" if m else "") + " prima"
    else:
        reminder_text = f"{minutes} minuti prima"

    await update.message.reply_text(
        f"✅ Pasto aggiunto!\n\n"
        f"📅 {context.user_data['meal_days_label']}\n"
        f"🍽 {context.user_data['meal_name']} alle {context.user_data['meal_time']}\n"
        f"🥘 {context.user_data['meal_recipe']}\n"
        f"🔔 Reminder: {reminder_text}\n\n"
        f"{get_motivational()}",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ── Vedi Pasti (settimana intera) ───────────────────────────────
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

    text = "📋 Il tuo piano settimanale:\n\n"
    current_day = -1
    for day, name, meal_time, recipe in rows:
        if day != current_day:
            current_day = day
            text += f"📅 {GIORNI[day]}\n"
        text += f"  🕐 {meal_time} - {name}\n  └ {recipe}\n\n"

    await update.message.reply_text(text)


# ── Pasti di oggi ───────────────────────────────────────────────
async def oggi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_day = datetime.now().weekday()

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT meal_name, meal_time, recipe FROM meals "
        "WHERE user_id = ? AND day_of_week = ? ORDER BY meal_time",
        (update.effective_user.id, current_day),
    )
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            f"📋 Nessun pasto programmato per oggi ({GIORNI[current_day]}).\n"
            "Usa /aggiungi_pasto per aggiungerne!"
        )
        return

    text = f"📋 Pasti di oggi ({GIORNI[current_day]}):\n\n"
    for name, meal_time, recipe in rows:
        text += f"🕐 {meal_time} - {name}\n└ {recipe}\n\n"

    text += f"\n{get_motivational()}"
    await update.message.reply_text(text)


# ── Copia Pasto ─────────────────────────────────────────────────
async def copia_pasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("Non hai pasti da copiare.")
        return

    buttons = []
    for meal_id, day, name, meal_time, recipe in rows:
        label = f"{GIORNI_SHORT[day]} {meal_time} - {name}: {recipe[:25]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"copy_meal_{meal_id}")])

    await update.message.reply_text(
        "📋 Quale pasto vuoi copiare?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def copia_pasto_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    meal_id = int(query.data.replace("copy_meal_", ""))
    context.user_data["copy_meal_id"] = meal_id

    # Mostra giorni come bottoni inline (multi-select simulato)
    buttons = []
    row = []
    for i, g in enumerate(GIORNI_SHORT):
        row.append(InlineKeyboardButton(g, callback_data=f"copyday_{i}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ Conferma", callback_data="copyday_done")])

    context.user_data["copy_days"] = []
    await query.edit_message_text(
        "📅 Su quali giorni vuoi copiarlo?\nClicca i giorni e poi Conferma.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def copia_pasto_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "copyday_done":
        days = context.user_data.get("copy_days", [])
        if not days:
            await query.edit_message_text("❌ Non hai selezionato nessun giorno.")
            return

        meal_id = context.user_data["copy_meal_id"]
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, meal_name, meal_time, recipe, reminder_minutes_before FROM meals WHERE id = ?", (meal_id,))
        meal = c.fetchone()
        if meal:
            for day in days:
                c.execute(
                    "INSERT INTO meals (user_id, day_of_week, meal_name, meal_time, recipe, reminder_minutes_before) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (meal[0], day, meal[1], meal[2], meal[3], meal[4]),
                )
            conn.commit()
        conn.close()

        giorni_label = ", ".join(GIORNI_SHORT[d] for d in sorted(days))
        await query.edit_message_text(f"✅ Pasto copiato su: {giorni_label}!")
        return

    day_idx = int(query.data.replace("copyday_", ""))
    copy_days = context.user_data.get("copy_days", [])
    if day_idx in copy_days:
        copy_days.remove(day_idx)
    else:
        copy_days.append(day_idx)
    context.user_data["copy_days"] = copy_days

    # Aggiorna bottoni con checkmark
    buttons = []
    row = []
    for i, g in enumerate(GIORNI_SHORT):
        check = "✓ " if i in copy_days else ""
        row.append(InlineKeyboardButton(f"{check}{g}", callback_data=f"copyday_{i}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ Conferma", callback_data="copyday_done")])

    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))


# ── Modifica Pasto ──────────────────────────────────────────────
async def modifica_pasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("Non hai pasti da modificare.")
        return ConversationHandler.END

    buttons = []
    for meal_id, day, name, meal_time, recipe in rows:
        label = f"{GIORNI_SHORT[day]} {meal_time} - {name}: {recipe[:25]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"edit_meal_{meal_id}")])

    await update.message.reply_text(
        "✏ Quale pasto vuoi modificare?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return EDIT_SELECT


async def edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    meal_id = int(query.data.replace("edit_meal_", ""))
    context.user_data["edit_meal_id"] = meal_id

    buttons = [
        [InlineKeyboardButton("🍽 Nome pasto", callback_data="editfield_meal_name")],
        [InlineKeyboardButton("⏰ Orario", callback_data="editfield_meal_time")],
        [InlineKeyboardButton("🥘 Ricetta/piatto", callback_data="editfield_recipe")],
        [InlineKeyboardButton("🔔 Reminder", callback_data="editfield_reminder")],
    ]

    await query.edit_message_text(
        "Cosa vuoi modificare?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return EDIT_FIELD


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    field = query.data.replace("editfield_", "")
    context.user_data["edit_field"] = field

    prompts = {
        "meal_name": "🍽 Scrivi il nuovo nome del pasto:",
        "meal_time": "⏰ Scrivi il nuovo orario (HH:MM):",
        "recipe": "🥘 Scrivi la nuova ricetta/piatto:",
        "reminder": "🔔 Scrivi i minuti di anticipo per il reminder (es. 30, 60, 120):",
    }

    await query.edit_message_text(prompts.get(field, "Scrivi il nuovo valore:"))
    return EDIT_VALUE


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    meal_id = context.user_data["edit_meal_id"]
    field = context.user_data["edit_field"]
    value = update.message.text.strip()

    # Validazione
    if field == "meal_time":
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            await update.message.reply_text("❌ Formato non valido. Scrivi come HH:MM (es. 13:00)")
            return EDIT_VALUE
    elif field == "reminder":
        try:
            value = int(value)
            if value < 1 or value > 1440:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero tra 1 e 1440.")
            return EDIT_VALUE

    # Mappa campo DB
    db_field_map = {
        "meal_name": "meal_name",
        "meal_time": "meal_time",
        "recipe": "recipe",
        "reminder": "reminder_minutes_before",
    }

    conn = get_db()
    c = conn.cursor()
    c.execute(
        f"UPDATE meals SET {db_field_map[field]} = ? WHERE id = ? AND user_id = ?",
        (value, meal_id, update.effective_user.id),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Pasto aggiornato!")
    return ConversationHandler.END


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
        label = f"❌ {GIORNI_SHORT[day]} {meal_time} - {name}: {recipe[:25]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"del_meal_{meal_id}")])

    await update.message.reply_text(
        "🗑 Quale pasto vuoi eliminare?",
        reply_markup=InlineKeyboardMarkup(buttons),
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


# ── Annulla ─────────────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# ── Registra Progressi ──────────────────────────────────────────
async def progresso_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Registriamo i tuoi progressi!\n\n"
        "⚖ Quanto pesi oggi? (in kg, es. 75.5)\n\n"
        "Scrivi /salta per saltare una misurazione"
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

    await update.message.reply_text("📏 Circonferenza vita (in cm)?\n/salta per saltare")
    return PROGRESS_WAIST


async def progress_waist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/salta":
        context.user_data["progress_waist"] = None
    else:
        try:
            context.user_data["progress_waist"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido")
            return PROGRESS_WAIST

    await update.message.reply_text("📏 Circonferenza fianchi (in cm)?\n/salta per saltare")
    return PROGRESS_HIPS


async def progress_hips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/salta":
        context.user_data["progress_hips"] = None
    else:
        try:
            context.user_data["progress_hips"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido")
            return PROGRESS_HIPS

    await update.message.reply_text("📏 Circonferenza petto/torace (in cm)?\n/salta per saltare")
    return PROGRESS_CHEST


async def progress_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/salta":
        context.user_data["progress_chest"] = None
    else:
        try:
            context.user_data["progress_chest"] = float(text.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Inserisci un numero valido")
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

    # Riepilogo
    parts = ["✅ Progressi registrati!\n"]
    w = context.user_data.get("progress_weight")
    if w:
        parts.append(f"⚖ Peso: {w} kg")
    waist = context.user_data.get("progress_waist")
    if waist:
        parts.append(f"📏 Vita: {waist} cm")
    hips = context.user_data.get("progress_hips")
    if hips:
        parts.append(f"📏 Fianchi: {hips} cm")
    chest = context.user_data.get("progress_chest")
    if chest:
        parts.append(f"📏 Petto: {chest} cm")

    # Confronto
    c.execute(
        "SELECT weight, waist, hips, chest FROM progress "
        "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 1 OFFSET 1",
        (update.effective_user.id,),
    )
    prev = c.fetchone()
    conn.close()

    if prev and w and prev[0]:
        diff = w - prev[0]
        emoji = "📉" if diff < 0 else "📈" if diff > 0 else "➡"
        parts.append(f"\n{emoji} Variazione peso: {diff:+.1f} kg rispetto all'ultima volta")

    parts.append(f"\n{get_motivational()}")
    await update.message.reply_text("\n".join(parts))
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

    text = "📊 Storico progressi (ultime 12):\n\n"
    for date, weight, waist, hips, chest in rows:
        text += f"📅 {date}\n"
        if weight:
            text += f"  ⚖ {weight:.1f} kg"
        if waist:
            text += f"  | Vita {waist:.0f}"
        if hips:
            text += f"  | Fianchi {hips:.0f}"
        if chest:
            text += f"  | Petto {chest:.0f}"
        text += "\n"

    # Mostra trend se almeno 2 rilevazioni con peso
    weights = [(r[0], r[1]) for r in rows if r[1]]
    if len(weights) >= 2:
        diff = weights[0][1] - weights[-1][1]
        emoji = "📉" if diff < 0 else "📈" if diff > 0 else "➡"
        text += f"\n{emoji} Trend: {diff:+.1f} kg dal {weights[-1][0]}"

    await update.message.reply_text(text)


# ── Impostazioni ────────────────────────────────────────────────
async def impostazioni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[g] for g in GIORNI]
    await update.message.reply_text(
        "⚙ Impostazioni\n\n"
        "In quale giorno vuoi il check-in settimanale (peso e misure)?",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return SETTINGS_DAY


async def settings_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = update.message.text.strip()
    if day not in GIORNI:
        await update.message.reply_text("Scegli un giorno dalla lista.")
        return SETTINGS_DAY

    context.user_data["settings_checkin_day"] = GIORNI.index(day)

    await update.message.reply_text(
        "🛒 A che ora vuoi ricevere il reminder della spesa per il giorno dopo?\n"
        "(Formato HH:MM, es. 20:00)\n\n"
        "Scrivi /salta per non riceverlo.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SETTINGS_GROCERY_TIME


async def settings_grocery_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    grocery_time = "20:00"
    if text.lower() == "/salta":
        grocery_time = None
    else:
        try:
            datetime.strptime(text, "%H:%M")
            grocery_time = text
        except ValueError:
            await update.message.reply_text("❌ Formato non valido. Scrivi come HH:MM (es. 20:00)")
            return SETTINGS_GROCERY_TIME

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO user_settings (user_id, weekly_checkin_day, grocery_reminder_time) VALUES (?, ?, ?)",
        (update.effective_user.id, context.user_data["settings_checkin_day"], grocery_time),
    )
    conn.commit()
    conn.close()

    day_name = GIORNI[context.user_data["settings_checkin_day"]]
    grocery_msg = f"🛒 Reminder spesa: ogni sera alle {grocery_time}" if grocery_time else "🛒 Reminder spesa: disattivato"

    await update.message.reply_text(
        f"✅ Impostazioni salvate!\n\n"
        f"📊 Check-in settimanale: ogni {day_name} alle 09:00\n"
        f"{grocery_msg}",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ── Job schedulati ──────────────────────────────────────────────
async def send_meal_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Eseguito ogni 5 minuti. Controlla reminder pasti."""
    now = datetime.now()
    current_day = now.weekday()

    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT user_id, meal_name, meal_time, recipe, reminder_minutes_before "
        "FROM meals WHERE day_of_week = ?",
        (current_day,),
    )
    meals = c.fetchall()
    conn.close()

    for user_id, meal_name, meal_time, recipe, reminder_minutes in meals:
        meal_dt = datetime.strptime(meal_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )

        if reminder_minutes == -1:
            reminder_dt = meal_dt.replace(hour=8, minute=0)
        else:
            reminder_dt = meal_dt - timedelta(minutes=reminder_minutes)

        diff_minutes = (now - reminder_dt).total_seconds() / 60
        if 0 <= diff_minutes < 5:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🔔 Reminder: {meal_name} alle {meal_time}!\n\n"
                        f"🥘 Devi preparare:\n{recipe}\n\n"
                        f"{get_motivational()}"
                    ),
                )
            except Exception as e:
                logger.error(f"Errore invio reminder a {user_id}: {e}")


async def send_grocery_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Eseguito ogni 5 minuti. Manda lista spesa per domani."""
    now = datetime.now()
    tomorrow_day = (now.weekday() + 1) % 7

    conn = get_db()
    c = conn.cursor()

    # Trova utenti con grocery reminder attivo
    c.execute("SELECT user_id, grocery_reminder_time FROM user_settings WHERE grocery_reminder_time IS NOT NULL")
    users = c.fetchall()

    for user_id, grocery_time in users:
        if not grocery_time:
            continue
        try:
            reminder_dt = datetime.strptime(grocery_time, "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
        except ValueError:
            continue

        diff_minutes = (now - reminder_dt).total_seconds() / 60
        if 0 <= diff_minutes < 5:
            # Prendi i pasti di domani
            c.execute(
                "SELECT meal_name, meal_time, recipe FROM meals "
                "WHERE user_id = ? AND day_of_week = ? ORDER BY meal_time",
                (user_id, tomorrow_day),
            )
            meals = c.fetchall()

            if meals:
                text = f"🛒 Spesa per domani ({GIORNI[tomorrow_day]})!\n\n"
                text += "Ecco cosa devi preparare domani:\n\n"
                for name, meal_time, recipe in meals:
                    text += f"🕐 {meal_time} - {name}\n└ {recipe}\n\n"
                text += "Controlla di avere tutto! 💪"

                try:
                    await context.bot.send_message(chat_id=user_id, text=text)
                except Exception as e:
                    logger.error(f"Errore invio spesa a {user_id}: {e}")

    conn.close()


async def send_weekly_checkin(context: ContextTypes.DEFAULT_TYPE):
    """Eseguito ogni giorno alle 9:00."""
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
                    f"📊 E' il giorno del check-in settimanale!\n\n"
                    f"Come stanno andando i progressi?\n"
                    f"Usa /progresso per registrare peso e misure.\n\n"
                    f"{get_motivational()}"
                ),
            )
        except Exception as e:
            logger.error(f"Errore invio check-in a {user_id}: {e}")


async def send_random_motivation(context: ContextTypes.DEFAULT_TYPE):
    """Invia un messaggio motivazionale random 2 volte al giorno."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM meals")
    users = c.fetchall()
    conn.close()

    for (user_id,) in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✨ Messaggio del giorno:\n\n{get_motivational()}",
            )
        except Exception as e:
            logger.error(f"Errore invio motivazione a {user_id}: {e}")


# ── Main ────────────────────────────────────────────────────────
def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation: Aggiungi Pasto
    meal_conv = ConversationHandler(
        entry_points=[CommandHandler("aggiungi_pasto", aggiungi_pasto_start)],
        states={
            MEAL_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_days_received)],
            MEAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_name_received)],
            MEAL_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_time_received)],
            MEAL_RECIPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_recipe_received)],
            MEAL_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_reminder_received)],
            MEAL_REMINDER_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, meal_reminder_custom)],
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
            SETTINGS_DAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_day)],
            SETTINGS_GROCERY_TIME: [MessageHandler(filters.TEXT, settings_grocery_time)],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )

    # Conversation: Modifica Pasto
    edit_conv = ConversationHandler(
        entry_points=[CommandHandler("modifica_pasto", modifica_pasto)],
        states={
            EDIT_SELECT: [CallbackQueryHandler(edit_select, pattern=r"^edit_meal_")],
            EDIT_FIELD: [CallbackQueryHandler(edit_field, pattern=r"^editfield_")],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[CommandHandler("annulla", cancel)],
    )

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("motivami", motivami))
    app.add_handler(CommandHandler("oggi", oggi))
    app.add_handler(meal_conv)
    app.add_handler(progress_conv)
    app.add_handler(settings_conv)
    app.add_handler(edit_conv)
    app.add_handler(CommandHandler("pasti", vedi_pasti))
    app.add_handler(CommandHandler("elimina_pasto", elimina_pasto))
    app.add_handler(CommandHandler("copia_pasto", copia_pasto))
    app.add_handler(CallbackQueryHandler(elimina_pasto_callback, pattern=r"^del_meal_"))
    app.add_handler(CallbackQueryHandler(copia_pasto_select, pattern=r"^copy_meal_"))
    app.add_handler(CallbackQueryHandler(copia_pasto_day, pattern=r"^copyday_"))
    app.add_handler(CommandHandler("storico", storico))

    # Job schedulati
    job_queue = app.job_queue
    # Reminder pasti ogni 5 minuti (piu' preciso)
    job_queue.run_repeating(send_meal_reminders, interval=300, first=10)
    # Reminder spesa ogni 5 minuti
    job_queue.run_repeating(send_grocery_reminder, interval=300, first=30)
    # Check-in settimanale alle 9:00
    job_queue.run_daily(send_weekly_checkin, time=time(hour=9, minute=0))
    # Messaggi motivazionali: alle 10:00 e alle 15:00
    job_queue.run_daily(send_random_motivation, time=time(hour=10, minute=0))
    job_queue.run_daily(send_random_motivation, time=time(hour=15, minute=0))

    logger.info("🥗 Diet Bot v2 avviato!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
