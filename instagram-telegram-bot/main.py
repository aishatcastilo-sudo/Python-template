import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from instagrapi import Client
from flask import Flask
from threading import Thread

# Flask app for uptime monitoring
app = Flask('')

@app.route('/')
def home():
    return "🤖 Instagram Login Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Get credentials from Replit Secrets
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store login sessions
user_sessions = {}

class InstagramBot:
    def __init__(self):
        self.client = None
        self.is_logged_in = False
        self.username = None
    
    def login(self, username, password):
        """Login to Instagram"""
        try:
            self.client = Client()
            self.client.login(username, password)
            self.is_logged_in = True
            self.username = username
            return True, f"✅ Successfully logged in as @{username}!"
        except Exception as e:
            logger.error(f"Login failed for {username}: {e}")
            return False, f"❌ Login failed: {str(e)}"
    
    def check_login(self):
        """Check if still logged in"""
        return self.is_logged_in
    
    def logout(self):
        """Logout from Instagram"""
        if self.client:
            try:
                self.client.logout()
            except:
                pass
        self.is_logged_in = False
        self.username = None
        self.client = None

def get_user_bot(user_id):
    """Get or create bot instance for user"""
    if user_id not in user_sessions:
        user_sessions[user_id] = InstagramBot()
    return user_sessions[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - show login options"""
    user = update.effective_user
    user_id = user.id
    bot = get_user_bot(user_id)
    
    # Check if already logged in
    if bot.check_login():
        keyboard = [
            [InlineKeyboardButton("🚪 Logout", callback_data='logout')],
            [InlineKeyboardButton("🔄 Check Status", callback_data='status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"👋 Hello {user.first_name}!\n"
            f"✅ You are already logged in as @{bot.username}\n\n"
            f"What would you like to do?",
            reply_markup=reply_markup
        )
    else:
        keyboard = [
            [InlineKeyboardButton("🔐 Login to Instagram", callback_data='login')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"👋 Hello {user.first_name}!\n\n"
            f"🔐 Click the button below to login to Instagram:\n\n"
            f"⚠️ Your credentials are used only for this session",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    bot = get_user_bot(user_id)
    
    if query.data == 'login':
        await query.edit_message_text(
            "🔐 **Enter your Instagram credentials**\n\n"
            "Send your username and password in this format:\n"
            "`username:password`\n\n"
            "⚠️ Your credentials will NOT be stored permanently\n"
            "⚠️ They are used only for this session",
            parse_mode='Markdown'
        )
        context.user_data['action'] = 'login'
    
    elif query.data == 'status':
        if bot.check_login():
            await query.edit_message_text(
                f"✅ **You are logged in**\n\n"
                f"👤 Username: @{bot.username}\n"
                f"🔐 Session: Active\n\n"
                f"Use /start to see options"
            )
        else:
            await query.edit_message_text(
                "❌ **You are not logged in**\n\n"
                "Use /start to login"
            )
    
    elif query.data == 'logout':
        bot.logout()
        keyboard = [[InlineKeyboardButton("🔐 Login Again", callback_data='login')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🚪 **Successfully logged out!**\n\n"
            "Your session has been ended.",
            reply_markup=reply_markup
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages (for login credentials)"""
    user_id = update.effective_user.id
    bot = get_user_bot(user_id)
    
    # Check if we're expecting login credentials
    if context.user_data.get('action') == 'login':
        try:
            # Split username and password
            text = update.message.text
            if ':' not in text:
                await update.message.reply_text(
                    "❌ **Invalid format!**\n\n"
                    "Please use:\n"
                    "`username:password`\n\n"
                    "Example: `john_doe:MyPass123`",
                    parse_mode='Markdown'
                )
                return
            
            username, password = text.split(':', 1)
            username = username.strip()
            password = password.strip()
            
            if not username or not password:
                await update.message.reply_text(
                    "❌ **Username or password cannot be empty!**\n\n"
                    "Please send again in format:\n"
                    "`username:password`",
                    parse_mode='Markdown'
                )
                return
            
            # Try to login
            await update.message.reply_text("⏳ Logging in to Instagram...")
            success, message = bot.login(username, password)
            
            if success:
                # Show success with logout option
                keyboard = [
                    [InlineKeyboardButton("🚪 Logout", callback_data='logout')],
                    [InlineKeyboardButton("🔄 Check Status", callback_data='status')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"{message}\n\n"
                    f"What would you like to do next?",
                    reply_markup=reply_markup
                )
            else:
                # Show failure with retry option
                keyboard = [[InlineKeyboardButton("🔐 Try Again", callback_data='login')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"{message}\n\n"
                    f"Would you like to try again?",
                    reply_markup=reply_markup
                )
            
            # Clear the action
            context.user_data.pop('action', None)
            
        except Exception as e:
            logger.error(f"Error in login: {e}")
            await update.message.reply_text(
                f"❌ **An error occurred:** {str(e)}\n\n"
                "Please try again with /start"
            )
            context.user_data.pop('action', None)
    
    else:
        # Not expecting any message
        await update.message.reply_text(
            "🤖 I only handle Instagram login.\n\n"
            "Use /start to begin."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    await update.message.reply_text(
        "🤖 **Instagram Login Bot**\n\n"
        "This bot only handles Instagram login.\n\n"
        "Commands:\n"
        "/start - Start the bot and login\n"
        "/help - Show this help message\n\n"
        "⚠️ Your credentials are NOT stored permanently",
        parse_mode='Markdown'
    )

def main():
    """Start the bot"""
    # Check if token exists
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN not found in environment variables!")
        print("Please add it to Replit Secrets.")
        return
    
    # Create Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("🤖 Instagram Login Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    keep_alive()  # Keep bot alive on Replit
    main()
