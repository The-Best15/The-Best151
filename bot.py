import os
import sqlite3
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# --- SERVEUR WEB (Indispensable pour Render) ---
# Render a besoin d'un port ouvert pour maintenir le service actif
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is Running!", 200

def run_flask():
    # Render définit automatiquement la variable d'environnement PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- CONFIGURATION GEMINI ---
# On récupère les clés depuis les variables d'environnement de Render
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

client = genai.Client(api_key=GEMINI_API_KEY)
logging.basicConfig(level=logging.INFO)

# --- MÉMOIRE DES CONVERSATIONS ---
user_context = {}

# --- FONCTIONS DU BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Bot Gemini 3 opérationnel sur Render !**\n\n"
        "Posez-moi vos questions ou envoyez-moi une photo."
    )

async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_context:
        user_context[user_id] = []
    
    user_context[user_id].append(f"User: {update.message.text}")
    history = "\n".join(user_context[user_id][-6:])

    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=history
        )
        user_context[user_id].append(f"AI: {response.text}")
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(e)
        await update.message.reply_text("⚠️ Erreur Gemini. Vérifiez vos quotas.")

async def vision_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("🔎 Analyse de l'image...")
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=["Analyse cette image précisément.", photo_bytes]
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text("❌ Erreur d'analyse d'image.")

# --- LANCEMENT ---
if __name__ == "__main__":
    # Démarrage de Flask dans un thread séparé
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Démarrage du bot Telegram
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(MessageHandler(filters.PHOTO, vision_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))
    
    print("🚀 Bot prêt !")
    app_bot.run_polling(drop_pending_updates=True)
