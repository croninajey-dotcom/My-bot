import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from database import Session, User, Like

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN ကို Environment Variable အနေနဲ့ သတ်မှတ်ပေးပါ။")

logging.basicConfig(level=logging.INFO)

# ----- Keyboard Buttons -----
MAIN_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📝 မှတ်ပုံတင်ရန်", callback_data="register")],
    [InlineKeyboardButton("🔍 ဖော်ရှာရန်", callback_data="find")],
    [InlineKeyboardButton("👤 ကိုယ်ရေးအကျဉ်း", callback_data="profile")],
    [InlineKeyboardButton("❤️ ကြိုက်ထားတဲ့သူများ", callback_data="my_likes")]
])

GENDER_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("👨 ကျား (Male)", callback_data="gender_male")],
    [InlineKeyboardButton("👩 မ (Female)", callback_data="gender_female")],
    [InlineKeyboardButton("🌈 အခြား", callback_data="gender_other")]
])

LOOKING_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("👨 ကျားကို ရှာမယ်", callback_data="looking_male")],
    [InlineKeyboardButton("👩 မကို ရှာမယ်", callback_data="looking_female")],
    [InlineKeyboardButton("👫 အားလုံးကို ရှာမယ်", callback_data="looking_both")]
])

REG_STATE = {}

# --------------------- START ---------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💘 **ရည်းစားရှာပေးတဲ့ Bot** မှ ကြိုဆိုပါတယ်!\n\n"
        "အောက်ပါ ခလုတ်တွေထဲက ရွေးချယ်ပါ။",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="Markdown"
    )

# --------------------- CALLBACK HANDLER ---------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # ---- မှတ်ပုံတင်ခြင်း ----
    if data == "register":
        session = Session()
        existing = session.query(User).filter_by(telegram_id=user_id).first()
        if existing and existing.is_registered:
            await query.edit_message_text("✅ သင်ပြီးသား မှတ်ပုံတင်ထားပြီးပါပြီ။", reply_markup=MAIN_KEYBOARD)
            session.close()
            return
        session.close()
        REG_STATE[user_id] = {'step': 0}
        await query.edit_message_text("သင့်နာမည် ဘယ်လိုခေါ်လဲ?", reply_markup=None)

    # ---- Gender ရွေးချယ်ခြင်း ----
    elif data.startswith("gender_"):
        gender = data.split("_")[1]
        session = Session()
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id)
            session.add(user)
        user.gender = gender
        session.commit()
        session.close()
        REG_STATE[user_id]['step'] = 3
        await query.edit_message_text("ဘယ်သူ့ကို ရှာနေတာလဲ?", reply_markup=LOOKING_KEYBOARD)

    # ---- Looking For ရွေးချယ်ခြင်း ----
    elif data.startswith("looking_"):
        looking = data.split("_")[1]
        session = Session()
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if user:
            user.looking_for = looking
            user.is_registered = True
            session.commit()
        session.close()
        if user_id in REG_STATE:
            del REG_STATE[user_id]
        await query.edit_message_text(
            "✅ **မှတ်ပုံတင်ခြင်း ပြီးပါပြီ!**\n\n"
            "ဓာတ်ပုံတစ်ပုံ ပို့ပေးပါ။ (Photo ကို ဒီမှာပဲ ပို့ပါ)",
            parse_mode="Markdown"
        )

    # ---- ကိုယ်ရေးအကျဉ်း ----
    elif data == "profile":
        session = Session()
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if user and user.is_registered:
            text = (
                f"👤 **အမည်:** {user.name}\n"
                f"🎂 **အသက်:** {user.age}\n"
                f"📝 **အကြောင်း:** {user.bio}\n"
                f"⚧️ **လိင်:** {user.gender}\n"
                f"🎯 **ရှာနေတာ:** {user.looking_for}"
            )
            if user.photo_file_id:
                await query.edit_message_text("သင့်ဓာတ်ပုံနဲ့ အချက်အလက်များ 👇")
                await context.bot.send_photo(chat_id=user_id, photo=user.photo_file_id, caption=text, parse_mode="Markdown")
            else:
                await query.edit_message_text(text + "\n\n⚠️ ဓာတ်ပုံ မရှိသေးပါ။ ဓာတ်ပုံတစ်ပုံ ပို့ပေးပါ။", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ ကျေးဇူးပြု၍ အရင်မှတ်ပုံတင်ပါ။", reply_markup=MAIN_KEYBOARD)
        session.close()

    # ---- ဖော်ရှာခြင်း ----
    elif data == "find":
        session = Session()
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user or not user.is_registered:
            await query.edit_message_text("❌ ကျေးဇူးပြု၍ အရင်မှတ်ပုံတင်ပါ။", reply_markup=MAIN_KEYBOARD)
            session.close()
            return

        # မကြိုက်ရသေးတဲ့သူကို ရှာမယ်
        liked_users = [l.to_user for l in session.query(Like).filter_by(from_user=user_id).all()]
        
        # Gender filter
        gender_filter = user.looking_for
        if gender_filter == "both":
            gender_filter = None
        
        query_builder = session.query(User).filter(
            User.telegram_id != user_id,
            User.is_registered == True,
            ~User.telegram_id.in_(liked_users) if liked_users else True
        )
        
        if gender_filter:
            query_builder = query_builder.filter(User.gender == gender_filter)
        
        # အသက် +/- ၅ နှစ်
        query_builder = query_builder.filter(User.age.between(user.age - 5, user.age + 5))
        
        match = query_builder.first()

        if match:
            context.user_data['current_match'] = match.telegram_id
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👍 Like", callback_data=f"like_{match.telegram_id}"),
                 InlineKeyboardButton("👎 Dislike", callback_data="dislike")],
                [InlineKeyboardButton("🏠 ပင်မစာမျက်နှာ", callback_data="home")]
            ])
            caption = f"👤 {match.name}, {match.age}\n📝 {match.bio}"
            await query.edit_message_text("🔍 အောက်ပါသူနဲ့ လိုက်ဖက်ပါတယ်:")
            await context.bot.send_photo(
                chat_id=user_id,
                photo=match.photo_file_id,
                caption=caption,
                reply_markup=keyboard
            )
        else:
            await query.edit_message_text("😔 လောလောဆယ် လိုက်ဖက်သူ မရှိသေးပါ။ နောက်မှ ထပ်ကြည့်ပါ။", reply_markup=MAIN_KEYBOARD)
        session.close()

    # ---- Like နှိပ်ခြင်း ----
    elif data.startswith("like_"):
        matched_id = int(data.split("_")[1])
        session = Session()
        
        # Like သိမ်းမယ်
        existing = session.query(Like).filter_by(from_user=user_id, to_user=matched_id).first()
        if not existing:
            new_like = Like(from_user=user_id, to_user=matched_id)
            session.add(new_like)
            session.commit()
        
        # အပြန်အလှန် Like စစ်မယ်
        mutual = session.query(Like).filter_by(from_user=matched_id, to_user=user_id, is_matched=False).first()
        if mutual:
            mutual.is_matched = True
            # ဒီ Like ကိုလည်း update လုပ်မယ်
            current_like = session.query(Like).filter_by(from_user=user_id, to_user=matched_id).first()
            if current_like:
                current_like.is_matched = True
            session.commit()
            
            # နှစ်ဦးစလုံးကို အကြောင်းကြားမယ်
            for uid in [user_id, matched_id]:
                other_id = matched_id if uid == user_id else user_id
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"💞 **ယူးဟူး! နှစ်ဦးသဘောတူသွားပါပြီ!**\n\n"
                         f"သူနဲ့ စကားပြောချင်ရင် ဒီ [လင့်ခ်](tg://user?id={other_id}) ကိုနှိပ်ပါ။",
                    parse_mode="Markdown"
                )
            await query.edit_message_text("🎉 သင်နှစ်သက်ကြောင်း ပေးပို့ထားပါပြီ! တစ်ဖက်သူလည်း နှစ်သက်သွားရင် အကြောင်းကြားမယ်။")
        else:
            await query.edit_message_text("👍 Like လုပ်ထားပါပြီ! တစ်ဖက်သူလည်း Like လုပ်ရင် အကြောင်းကြားမယ်။")
        session.close()

    # ---- Dislike နှိပ်ခြင်း ----
    elif data == "dislike":
        await query.edit_message_text("⏭️ ကျော်လိုက်ပါပြီ။ ဆက်ရှာချင်ရင် /find ကိုနှိပ်ပါ။", reply_markup=MAIN_KEYBOARD)

    # ---- ကိုယ်ကြိုက်ထားတဲ့သူများ ----
    elif data == "my_likes":
        session = Session()
        likes = session.query(Like).filter_by(from_user=user_id).all()
        if likes:
            text = "❤️ **သင်ကြိုက်ထားတဲ့သူများ:**\n\n"
            for like in likes:
                other = session.query(User).filter_by(telegram_id=like.to_user).first()
                if other:
                    status = "💞 နှစ်ဦးသဘောတူ" if like.is_matched else "⏳ စောင့်ဆိုင်နေဆဲ"
                    text += f"• {other.name} ({other.age}) - {status}\n"
            await query.edit_message_text(text, parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ သင်ဘယ်သူကိုမှ ကြိုက်ထားခြင်း မရှိသေးပါ။", reply_markup=MAIN_KEYBOARD)
        session.close()

    # ---- ပင်မစာမျက်နှာ ----
    elif data == "home":
        await query.edit_message_text("🏠 ပင်မစာမျက်နှာ", reply_markup=MAIN_KEYBOARD)

# --------------------- TEXT MESSAGE HANDLER ---------------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = REG_STATE.get(user_id)

    if not state:
        await update.message.reply_text("ကျေးဇူးပြု၍ အောက်က ခလုတ်တွေသုံးပါ။", reply_markup=MAIN_KEYBOARD)
        return

    session = Session()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if not user:
        user = User(telegram_id=user_id)
        session.add(user)

    if state['step'] == 0:
        user.name = text
        state['step'] = 1
        await update.message.reply_text("အသက် ဘယ်လောက်လဲ? (ဂဏန်းသက်သက်သာ)")
    elif state['step'] == 1:
        try:
            user.age = int(text)
            state['step'] = 2
            await update.message.reply_text("ကိုယ့်အကြောင်း အတိုချုံး ပြောပြပါ။ (ဥပမာ - စာအုပ်ဖတ်ရတာကြိုက်တယ်၊ ခရီးသွားရတာဝါသနာပါ)"
)
        except:
            await update.message.reply_text("❌ ကျေးဇူးပြု၍ ဂဏန်းသက်သက်သာ ရိုက်ပါ။")
            session.close()
            return
    elif state['step'] == 2:
        user.bio = text
        state['step'] = 3
        session.commit()
        session.close()
        await update.message.reply_text("သင့်လိင် ဘာလဲ?", reply_markup=GENDER_KEYBOARD)
        return

    session.commit()
    session.close()

# --------------------- PHOTO HANDLER ---------------------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1].file_id
    session = Session()
    user = session.query(User).filter_by(telegram_id=user_id).first()
    if user:
        user.photo_file_id = photo
        session.commit()
        await update.message.reply_text("✅ ဓာတ်ပုံ သိမ်းဆည်းပြီးပါပြီ!\n\n/start နှိပ်ပြီး စတင်သုံးနိုင်ပါပြီ။", reply_markup=MAIN_KEYBOARD)
    else:
        await update.message.reply_text("❌ ကျေးဇူးပြု၍ /start နှိပ်ပြီး အရင်မှတ်ပုံတင်ပါ။")
    session.close()

# --------------------- MAIN ---------------------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
