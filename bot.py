import requests
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

# FMCSA DATASETS
INSPECTION_URL = "https://data.transportation.gov/resource/rbkj-cgst.json"
CARRIER_URL = "https://data.transportation.gov/resource/az4n-8mr2.json"


# 🔥 Parse FMCSA date
def parse_date(date_str):
    months = {
        "JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,
        "JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12
    }
    try:
        d, m, y = date_str.split("-")
        return (2000 + int(y), months[m], int(d))
    except:
        return (0, 0, 0)


# 🔍 Build query
def build_query(mode, text):
    text = text.upper().strip()
    parts = text.split()

    if mode == "VIN":
        return f"?$where=vin='{text}' OR vin2='{text}'&$limit=10"

    if mode == "PLATE_STATE":
        if len(parts) != 2:
            return None
        plate, state = parts
        return (
            f"?$where="
            f"(unit_license LIKE '%{plate}%' AND unit_license_state='{state}') OR "
            f"(unit_license2 LIKE '%{plate}%' AND unit_license_state2='{state}')"
            f"&$limit=10"
        )

    if mode == "PLATE":
        return (
            f"?$where="
            f"unit_license LIKE '%{text}%' OR unit_license2 LIKE '%{text}%'"
            f"&$limit=10"
        )


# 🔎 Get inspection data
def get_inspections(query):
    try:
        url = INSPECTION_URL + query
        res = requests.get(url, timeout=10)
        data = res.json()

        if not data:
            return []

        data.sort(key=lambda x: parse_date(x.get("insp_date", "")), reverse=True)

        return data

    except Exception as e:
        print("Inspection ERROR:", e)
        return []


# 🏢 Get carrier info
def get_carrier(dot):
    try:
        url = f"{CARRIER_URL}?dot_number={dot}"
        res = requests.get(url, timeout=10)
        data = res.json()

        if not data:
            return None

        c = data[0]

        return {
            "name": c.get("legal_name"),
            "phone": c.get("phone") or c.get("cell_phone"),
            "address": f"{c.get('phy_street')}, {c.get('phy_city')}, {c.get('phy_state')} {c.get('phy_zip')}",
            "email": c.get("email_address"),
            "owner": c.get("company_officer_1")
        }

    except Exception as e:
        print("Carrier ERROR:", e)
        return None


# 👋 START MENU
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["🔎 VIN Search"],
        ["🚚 Plate Search"],
        ["📍 Plate + State"]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "👋 *FMCSA Accident Lookup Bot*\n\n"
        "Select search type:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


# 🤖 HANDLE USER INPUT
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Mode selection
    if text == "🔎 VIN Search":
        context.user_data["mode"] = "VIN"
        await update.message.reply_text("Enter VIN (17 digits):")
        return

    if text == "🚚 Plate Search":
        context.user_data["mode"] = "PLATE"
        await update.message.reply_text("Enter Plate (e.g. 40713P):")
        return

    if text == "📍 Plate + State":
        context.user_data["mode"] = "PLATE_STATE"
        await update.message.reply_text("Enter Plate + State (e.g. 40713P CA):")
        return

    mode = context.user_data.get("mode")

    if not mode:
        await update.message.reply_text("Please choose search type using /start")
        return

    query = build_query(mode, text)

    if not query:
        await update.message.reply_text("❌ Invalid format. Try again.")
        return

    inspections = get_inspections(query)

    if not inspections:
        await update.message.reply_text("❌ No inspection found")
        return

    # Get latest inspection
    latest = inspections[0]
    dot = latest.get("dot_number")

    carrier = get_carrier(dot)

    msg = "🚨 *ACCIDENT LOOKUP RESULT*\n\n"

    msg += f"""📅 Inspection: {latest.get('insp_date')} | {latest.get('report_state')}
🏢 DOT: {dot}

🚚 Truck: {latest.get('unit_license')} ({latest.get('unit_license_state')})
🔗 Trailer: {latest.get('unit_license2') or 'N/A'}

"""

    if carrier:
        msg += f"""🏢 *Company Info*

📛 Name: {carrier.get('name')}
👤 Owner: {carrier.get('owner') or 'N/A'}
📞 Phone: {carrier.get('phone') or 'N/A'}
📍 Address: {carrier.get('address')}
📧 Email: {carrier.get('email') or 'N/A'}
"""
    else:
        msg += "\n❌ Company info not found"

    await update.message.reply_text(msg, parse_mode="Markdown")


# 🚀 RUN BOT
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("Bot is running...")
app.run_polling()
