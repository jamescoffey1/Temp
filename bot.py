import requests
import random
import string
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === CONFIG ===
API_URL = "https://api.mail.tm"
BOT_TOKEN = "8289690460:AAGTlXn5RSpl0_-X8jX6NZQeqHTe2NJNTsA"   # <-- put your token here

# Storage (per Telegram user)
user_emails = {}

# Helper: random password
def random_password(length=10):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

# Command: start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Commands:\n"
        "• /new → Generate a new temp mail\n"
        "• /list → List all your saved emails\n"
        "• /inbox → Check latest email inbox\n"
        "• /inbox <num> → Check inbox of a specific saved email\n"
        "• /read <msg_id> → Read full body of a specific message\n"
    )

# Command: create new email
async def new_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    domain_resp = requests.get(f"{API_URL}/domains").json()
    domain = domain_resp["hydra:member"][0]["domain"]

    local_part = ''.join(random.choice(string.ascii_lowercase) for _ in range(8))
    email = f"{local_part}@{domain}"
    password = random_password()

    register_resp = requests.post(f"{API_URL}/accounts", json={
        "address": email,
        "password": password
    })

    if register_resp.status_code != 201:
        await update.message.reply_text("⚠️ Failed to generate email.")
        return

    if user_id not in user_emails:
        user_emails[user_id] = []
    user_emails[user_id].append({"email": email, "password": password})

    await update.message.reply_text(
        f"✅ New temp email created:\n\n📧 {email}\n\n"
        "Use /inbox to check messages or /list to see all your emails."
    )

# Command: list emails
async def list_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_emails or not user_emails[user_id]:
        await update.message.reply_text("❌ You don’t have any saved emails. Use /new first.")
        return

    lines = ["📋 Your saved emails:\n"]
    for i, acc in enumerate(user_emails[user_id], start=1):
        lines.append(f"{i}. {acc['email']}")
    await update.message.reply_text("\n".join(lines))

# Command: check inbox
async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_emails or not user_emails[user_id]:
        await update.message.reply_text("❌ You don’t have any saved emails.")
        return

    index = -1  # default last
    if context.args:
        try:
            num = int(context.args[0]) - 1
            if 0 <= num < len(user_emails[user_id]):
                index = num
            else:
                await update.message.reply_text("⚠️ Invalid number. Use /list to check your emails.")
                return
        except ValueError:
            await update.message.reply_text("⚠️ Usage: /inbox or /inbox <number>")
            return

    acc = user_emails[user_id][index]
    email, password = acc["email"], acc["password"]

    token_resp = requests.post(f"{API_URL}/token", json={"address": email, "password": password})
    if token_resp.status_code != 200:
        await update.message.reply_text(f"⚠️ Failed login for {email}.")
        return

    token = token_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    msg_resp = requests.get(f"{API_URL}/messages", headers=headers).json()

    if msg_resp["hydra:totalItems"] == 0:
        await update.message.reply_text(f"📭 Inbox for {email} is empty.")
    else:
        lines = [f"📨 Messages for {email}:\n"]
        for m in msg_resp["hydra:member"]:
            lines.append(f"ID: {m['id']}\nFrom: {m['from']['address']}\nSubject: {m['subject']}\n")
        await update.message.reply_text("\n".join(lines))

# Command: read message
async def read_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_emails or not user_emails[user_id]:
        await update.message.reply_text("❌ You don’t have any saved emails.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /read <msg_id>")
        return

    msg_id = context.args[0]

    # Always use the latest account (or you can pick with inbox <num>)
    acc = user_emails[user_id][-1]
    email, password = acc["email"], acc["password"]

    token_resp = requests.post(f"{API_URL}/token", json={"address": email, "password": password})
    if token_resp.status_code != 200:
        await update.message.reply_text(f"⚠️ Failed login for {email}.")
        return

    token = token_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    msg_resp = requests.get(f"{API_URL}/messages/{msg_id}", headers=headers)
    if msg_resp.status_code != 200:
        await update.message.reply_text("⚠️ Could not fetch message. Maybe wrong ID?")
        return

    msg = msg_resp.json()
    from_addr = msg["from"]["address"]
    subject = msg["subject"]
    body = msg.get("text", msg.get("intro", "(no body)"))

    await update.message.reply_text(
        f"📩 Message from {from_addr}\n"
        f"Subject: {subject}\n\n"
        f"{body}"
    )

# === MAIN ===
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_email))
    app.add_handler(CommandHandler("list", list_emails))
    app.add_handler(CommandHandler("inbox", inbox))
    app.add_handler(CommandHandler("read", read_message))
    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
