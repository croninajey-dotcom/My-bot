import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ===== Tokens & IDs =====
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    MONGODB_URI = os.getenv('MONGODB_URI')
    OWNER_ID = int(os.getenv('OWNER_ID', 7771663458))
    
    # ===== Links =====
    CHANNEL_LINK = os.getenv('CHANNEL_LINK', 'https://t.me/BOTUAPTE')
    BOT_LINK = os.getenv('BOT_LINK', 'https://t.me/Cupi677')
    
    # ===== Port =====
    PORT = int(os.getenv('PORT', 10000))
    
    # ===== Welcome Text =====
    WELCOME_TEXT = """နွေကို ချစ်ရင် ပူရတယ်
မိုးခြိမ်းရင် ကြောက်တက်တယ်
အရင်ကဆို ခုတော့သူထားသွားမှာပဲ
ကြောက်မိနေပီ
ဆောင်းကျပြန်တော့ သူရဲ့စကားချိုချိုလေးတွေ သတိရမိတယ်

🚨-------လူသစ်အချက်အလက်များ--------🚨

Name🍃- {name}
Id🍂 - {user_id}
@user🎋- {username}
Bio🌾 - {bio}

🌷Mya ရှိတဲ့နေရာလေးကနေ ကြိုဆိုပါတယ်ရှင့် 🌷
🌸လူလေးထည့်ပေးခဲ့ပါအုန်းရှင့်🌸"""

    # ===== Leave Text =====
    LEAVE_TEXT = """အချစ်ခံချင်ရုံပါ🥀🥀
အပစ်ခံရမယ်လို🥺
ဘယ်သူကထင်မှာလဲ😔
ချိုသာစွာလဲညာခဲ့ဖူးတယ်
ပြန်လာဖို့လဲမှာခဲ့ဖူးတယ်
ဒီလောက်ဆိုတော်ပီလေ
မုသားတွေလဲမချိုတော့ဘူး
လူကြားထဲလဲမငိုချင်တော့ဘူး😔💔
နာကျင်ပါများလာရင်ကျင့်သားရသွားပါလိမ့်မယ်🥀
တစ်ချို့နာကျင်မှုတွေကမျက်ရည်ကျပြရတာထက်မျက်ရည်မကျအောင်ထိန်းပြီးပြုံးပြရတာမျိုး💔🥀🥀🥀🥀

🧸အဆင်ပြေရင်ပြန်လာခဲ့ပါ🧸

👤 {name}
🆔 {user_id}
@ {username}"""

    # ===== Start Text =====
    START_TEXT = """---🧸/မဂ်လာပါရှင့်-သုံးစွဲသူ\🧸---
🧧အချက်အလက်များဧ

Name🍃- {name}
Id🍂 - {user_id}
@user🎋- {username}
Bio🌾 - {bio}

ကြောညာအတွက်🔒
📪owner - @Tear808🧸🧸"""

    # ===== Help Mya Text =====
    HELP_MYA_TEXT = """🧸 အသုံးပြုပုံလမ်းညွှန် 🧸

👤 Mya officle Bot
🌷🌷🌷
━━━━━━━━━━━━━━━━━━━━━━

📌 အမြန်အသုံးပြုနည်း
• /start - Bot ကိုစတင်ရန်
• /help - လမ်းညွှန်ကြည့်ရန်
• /report - Admin ကိုအကြောင်းကြားရန်

💡 အောက်ပါခလုပ်များကိုနှိပ်ပြီး လေ့လာပါ။"""

    # ===== Validation =====
    @classmethod
    def validate(cls):
        required = ['TELEGRAM_BOT_TOKEN', 'MONGODB_URI']
        for key in required:
            if not getattr(cls, key):
                raise ValueError(f"{key} မပါပါဘူး!")
