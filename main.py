import asyncio
import logging
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, BotCommand
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError

logging.basicConfig(level=logging.WARNING)

TOKEN = '8716192417:AAFNSB_OpMtWBycD3jCyo0092aHEvH9De_g'
API_ID = 39472464
API_HASH = 'a4e5f8bdb9da185818b406de020d757c'
DEVELOPER_CHAT_ID = 8253782818
DEVELOPER_USERNAME = "ZOR0_SAN"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DB_FILE = "users_accounts_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except:
            return {}
    return {}

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users_accounts_db, f, ensure_ascii=False, indent=4)

# هيكل البيانات: {user_id: [ {id: 1, phone: "...", session_string: "...", auto_reply_text: "...", auto_reply_active: 0, is_offline_mode: 0}, ... ]}
users_accounts_db = load_db()
active_clients = {}
temp_login_data = {} 
temp_post_data = {}

class AccountState(StatesGroup):
    waiting_for_session = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()

class PostState(StatesGroup):
    waiting_for_chats = State()
    waiting_for_caption = State()
    waiting_for_delay = State()
    waiting_for_media = State()

class AutoReplyState(StatesGroup):
    waiting_for_autoreply_text = State()

def get_main_keyboard(user_id):
    accounts = users_accounts_db.get(user_id, [])
    has_accounts = len(accounts) > 0
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 إدارة حساباتي (الحد 5)", callback_data="manage_accounts"),
                InlineKeyboardButton(text="🛑 إيقاف العمليات", callback_data="reset_bot")
            ],
            [
                InlineKeyboardButton(text="⚙️ بدء النشر التلقائي", callback_data="start_posting" if has_accounts else "no_account_alert"),
                InlineKeyboardButton(text="💬 ضبط الرد التلقائي", callback_data="setup_autoreply" if has_accounts else "no_account_alert")
            ],
            [
                InlineKeyboardButton(text="📊 تواصل مع المطور", url=f"https://t.me/{DEVELOPER_USERNAME}")
            ]
        ]
    )

def get_cancel_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ إلغاء العملية", callback_data="reset_bot")]
        ]
    )

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="تشغيل البوت والقائمة الرئيسية"),
        BotCommand(command="help", description="تواصل مع المطور والدعم الفني")
    ]
    await bot.set_my_commands(commands)

@dp.message(Command("start"))
async def send_welcome(message: Message):
    user_id = message.from_user.id
    welcome_text = (
        "أهلاً بك عزيزي في بوت Zoro AutoPoster المتطور لإدارة الحسابات والنشر التلقائي 🚀\n\n"
        "يمكنك إضافة وإدارة **حتى 5 حسابات** بكل سهولة. اختر من الأزرار أدناه:"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")

@dp.message(Command("help"))
async def send_help(message: Message):
    help_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 تواصل مع المطور مباشرة", url=f"https://t.me/{DEVELOPER_USERNAME}")],
            [InlineKeyboardButton(text="🔙 العودة للقائمة الرئيسية", callback_data="reset_bot")]
        ]
    )
    help_text = (
        "🛠️ **قسم المساعدة والدعم الفني:**\n\n"
        f"إذا واجهتك أي مشكلة أو رغبت في الاستفسار، يمكنك مراسلة المطور الأساسي مباشرة:\n"
        f"👤 المطور: @{DEVELOPER_USERNAME}"
    )
    await message.answer(help_text, reply_markup=help_kb, parse_mode="Markdown")

@dp.callback_query(F.data == "manage_accounts")
async def manage_accounts_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    accounts = users_accounts_db.get(user_id, [])
    
    keyboard_buttons = []
    
    if len(accounts) < 5:
        keyboard_buttons.append([InlineKeyboardButton(text="➕ إضافة حساب جديد", callback_data="choose_add_method")])
    
    for idx, acc in enumerate(accounts):
        phone = acc.get("phone", f"حساب {idx+1}")
        status = "🛌 أوفلاين" if acc.get("is_offline_mode") else "🟢 أونلاين"
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"📱 {phone} ({status})", callback_data=f"view_acc_{idx}"),
            InlineKeyboardButton(text="🗑️ حذف", callback_data=f"del_acc_{idx}")
        ])
        
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="reset_bot")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(
        f"👥 **إدارة حساباتك المضافة ({len(accounts)}/5):**\n"
        "يمكنك إضافة حتى 5 حسابات والتحكم بها بشكل منفصل:",
        reply_markup=kb, parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "choose_add_method")
async def choose_add_method(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    accounts = users_accounts_db.get(user_id, [])
    if len(accounts) >= 5:
        await callback.answer("⚠️ لقد وصلت للحد الأقصى (5 حسابات)!", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 تسجيل برقم الموبايل", callback_data="add_by_phone")],
            [InlineKeyboardButton(text="🔑 إضافة بكود الجلسة (Session)", callback_data="add_by_session")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="manage_accounts")]
        ]
    )
    await callback.message.edit_text(
        "🛠️ **اختر طريقة إضافة الحساب:**",
        reply_markup=kb, parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "add_by_session")
async def ask_for_session(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔑 أرسل الآن **كود الجلسة (Session String)** الخاص بالحساب:",
        reply_markup=get_cancel_keyboard(), parse_mode="Markdown"
    )
    await state.set_state(AccountState.waiting_for_session)
    await callback.answer()

@dp.message(AccountState.waiting_for_session)
async def save_user_session(message: Message, state: FSMContext):
    user = message.from_user
    session_string = message.text.strip()

    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await message.answer("❌ الجلسة غير صالحة أو منتهية. تأكد منها وأرسلها مجدداً.")
            return

        me = await client.get_me()
        phone = f"+{me.phone}" if me.phone else "حساب بدون رقم"
        
        user_accounts = users_accounts_db.setdefault(user.id, [])
        if len(user_accounts) >= 5:
            await message.answer("⚠️ لقد وصلت للحد الأقصى (5 حسابات).")
            await state.clear()
            return

        user_accounts.append({
            "phone": phone,
            "username": me.username or "No Username",
            "full_name": me.first_name,
            "session_string": session_string,
            "auto_reply_text": None,
            "auto_reply_active": 0,
            "is_offline_mode": 0
        })
        save_db()
        await client.disconnect()
        await state.clear()

        await message.answer("✅ تم ربط الحساب بنجاح وإضافته لقائمة حساباتك!", reply_markup=get_main_keyboard(user.id))
        start_background_listener(user.id, session_string)

    except Exception as e:
        await message.answer(f"❌ حدث خطأ أثناء التحقق من الجلسة: {e}")

@dp.callback_query(F.data == "add_by_phone")
async def ask_for_phone(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📱 **أدخل رقم هاتفك مع رمز الدولة:**\n(مثال: `+201012345678`)",
        reply_markup=get_cancel_keyboard(), parse_mode="Markdown"
    )
    await state.set_state(AccountState.waiting_for_phone)
    await callback.answer()

@dp.message(AccountState.waiting_for_phone)
async def process_phone_number(message: Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.text.strip()

    msg = await message.answer("⏳ جاري إرسال كود التحقق إلى تطبيق تيليجرام الخاص بك...")

    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        result = await client.send_code_request(phone)

        temp_login_data[user_id] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": result.phone_code_hash
        }

        await msg.edit_text(
            "📩 **تم إرسال كود التحقق (OTP) لحسابك.**\nأدخل الكود الآن:",
            reply_markup=get_cancel_keyboard(), parse_mode="Markdown"
        )
        await state.set_state(AccountState.waiting_for_code)
    except Exception as e:
        await msg.edit_text(f"❌ حدث خطأ أثناء إرسال الكود: {e}")
        await state.clear()

@dp.message(AccountState.waiting_for_code)
async def process_login_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    code = message.text.strip().replace(" ", "")
    data = temp_login_data.get(user_id)

    if not data:
        await message.answer("⚠️ حدث خطأ في الجلسة، ابدأ من جديد.", reply_markup=get_main_keyboard(user_id))
        await state.clear()
        return

    client = data["client"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]

    msg = await message.answer("⏳ جاري التحقق من الكود...")

    try:
        await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        session_string = client.session.save()
        me = await client.get_me()

        user_accounts = users_accounts_db.setdefault(user_id, [])
        user_accounts.append({
            "phone": phone,
            "username": me.username or "No Username",
            "full_name": me.first_name,
            "session_string": session_string,
            "auto_reply_text": None,
            "auto_reply_active": 0,
            "is_offline_mode": 0
        })
        save_db()
        await client.disconnect()
        del temp_login_data[user_id]

        await state.clear()
        await msg.edit_text("✅ **تم تسجيل الدخول وإضافة الحساب بنجاح!**", reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        start_background_listener(user_id, session_string)

    except SessionPasswordNeededError:
        await msg.edit_text(
            "🔒 **الحساب محمي بكلمة مرور (التحقق بخطوتين 2FA).**\nأدخل كلمة المرور:",
            reply_markup=get_cancel_keyboard(), parse_mode="Markdown"
        )
        await state.set_state(AccountState.waiting_for_password)
    except Exception as e:
        await msg.edit_text(f"❌ خطأ في كود التحقق: {e}")
        await state.clear()

@dp.message(AccountState.waiting_for_password)
async def process_2fa_password(message: Message, state: FSMContext):
    user_id = message.from_user.id
    password = message.text.strip()
    data = temp_login_data.get(user_id)

    if not data:
        await message.answer("⚠️ حدث خطأ، ابدأ من جديد.", reply_markup=get_main_keyboard(user_id))
        await state.clear()
        return

    client = data["client"]
    phone = data["phone"]
    msg = await message.answer("⏳ جاري التحقق من كلمة المرور...")

    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        me = await client.get_me()

        user_accounts = users_accounts_db.setdefault(user_id, [])
        user_accounts.append({
            "phone": phone,
            "username": me.username or "No Username",
            "full_name": me.first_name,
            "session_string": session_string,
            "auto_reply_text": None,
            "auto_reply_active": 0,
            "is_offline_mode": 0
        })
        save_db()
        await client.disconnect()
        del temp_login_data[user_id]

        await state.clear()
        await msg.edit_text("✅ **تم تسجيل الدخول وتجاوز التحقق بخطوتين بنجاح!**", reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
        start_background_listener(user_id, session_string)

    except Exception as e:
        await msg.edit_text(f"❌ كلمة المرور غير صحيحة: {e}", reply_markup=get_main_keyboard(user_id))
        await state.clear()

@dp.callback_query(F.data.startswith("del_acc_"))
async def delete_specific_account(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    acc_idx = int(callback.data.split("_")[2])
    
    accounts = users_accounts_db.get(user_id, [])
    if 0 <= acc_idx < len(accounts):
        removed = accounts.pop(acc_idx)
        save_db()
        await callback.answer(f"🗑️ تم حذف الحساب {removed.get('phone')} بنجاح", show_alert=True)
    
    await manage_accounts_menu(callback)

@dp.callback_query(F.data == "reset_bot")
async def reset_bot_state(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await state.clear()
    if user_id in temp_login_data:
        del temp_login_data[user_id]
    text = "أهلاً بك عزيزي في بوت Zoro AutoPoster المتطور لإدارة الحسابات والنشر التلقائي 🚀\n\nيمكنك إضافة وإدارة **حتى 5 حسابات** بكل سهولة. اختر من الأزرار أدناه:"
    try:
        await callback.message.edit_text(text, reply_markup=get_main_keyboard(user_id))
    except:
        await callback.message.answer(text, reply_markup=get_main_keyboard(user_id))
    await callback.answer()

@dp.callback_query(F.data == "no_account_alert")
async def no_account_alert(callback: types.CallbackQuery):
    await callback.answer("⚠️ يرجى إضافة حساب واحد على الأقل أولاً!", show_alert=True)

@dp.callback_query(F.data == "setup_autoreply")
async def setup_autoreply_menu(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    accounts = users_accounts_db.get(user_id, [])
    if not accounts:
        await callback.answer("⚠️ يرجى إضافة حساب أولاً!", show_alert=True)
        return

    await callback.message.answer(
        "🤖 **اكتب نص الرد التلقائي:**\n"
        "• سيتم تطبيق هذا الرد على كافة حساباتك المضافة عند تفعيل وضع الأوفلاين:",
        reply_markup=get_cancel_keyboard(), parse_mode="Markdown"
    )
    await state.set_state(AutoReplyState.waiting_for_autoreply_text)
    await callback.answer()

@dp.message(AutoReplyState.waiting_for_autoreply_text)
async def save_autoreply_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    reply_text = message.text.strip()

    if user_id in users_accounts_db:
        for acc in users_accounts_db[user_id]:
            acc["auto_reply_text"] = reply_text
            acc["auto_reply_active"] = 1
            acc["is_offline_mode"] = 1
        save_db()

    await state.clear()
    await message.answer(
        f"✅ **تم حفظ وتفعيل الرد التلقائي لكل حساباتك بنجاح!**\nالنص:\n`{reply_text}`",
        reply_markup=get_main_keyboard(user_id), parse_mode="Markdown"
    )

def start_background_listener(user_id, session_string):
    async def run_client():
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.start()
            
            @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
            async def auto_reply_handler(event):
                user_accounts = users_accounts_db.get(user_id, [])
                for acc in user_accounts:
                    if acc.get("session_string") == session_string:
                        if acc.get("auto_reply_active") and acc.get("is_offline_mode") and acc.get("auto_reply_text"):
                            if not event.sender.bot:
                                await event.respond(acc["auto_reply_text"])

            await client.run_until_disconnected()
        except Exception as e:
            print(f"خطأ في عميل تليثون للحساب: {e}")

    asyncio.create_task(run_client())

@dp.callback_query(F.data == "start_posting")
async def start_posting_process(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    accounts = users_accounts_db.get(user_id, [])
    if not accounts:
        await callback.answer("⚠️ يرجى إضافة حساب أولاً!", show_alert=True)
        return

    await callback.message.answer(
        "🔗 أرسل الآن **روابط المجموعات أو المعرفات** (كل رابط في سطر منفصل):",
        reply_markup=get_cancel_keyboard(), parse_mode="Markdown"
    )
    await state.set_state(PostState.waiting_for_chats)
    await callback.answer()

@dp.message(PostState.waiting_for_chats)
async def get_chat_targets(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chats = [c.strip() for c in message.text.split("\n") if c.strip()]
    if not chats:
        return
    temp_post_data[user_id] = {"chats": chats}
    await message.answer("✍️ الآن أرسل **النص** المراد نشره:", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
    await state.set_state(PostState.waiting_for_caption)

@dp.message(PostState.waiting_for_caption)
async def get_post_caption(message: Message, state: FSMContext):
    user_id = message.from_user.id
    temp_post_data[user_id]["caption"] = message.text
    await message.answer("⏱️ **حدد الفاصل الزمني بالثواني (من 1 إلى 60):**", reply_markup=get_cancel_keyboard(), parse_mode="Markdown")
    await state.set_state(PostState.waiting_for_delay)

@dp.message(PostState.waiting_for_delay)
async def get_post_delay(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        delay = int(message.text.strip())
        delay = max(1, min(delay, 60))
    except ValueError:
        await message.answer("⚠️ يرجى إرسال رقم صحيح:")
        return

    temp_post_data[user_id]["delay"] = delay
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ تخطي الصورة ونشر النص فقط", callback_data="skip_media")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="reset_bot")]
        ]
    )
    await message.answer("🖼️ أرسل **صورة** أو اضغط تخطي:", reply_markup=keyboard, parse_mode="Markdown")
    await state.set_state(PostState.waiting_for_media)

@dp.message(PostState.waiting_for_media, F.photo)
async def get_post_media_and_send(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = temp_post_data.get(user_id, {})
    chats, caption_text, delay = data.get("chats", []), data.get("caption"), data.get("delay", 7)

    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    photo_path = f"temp_{user_id}.jpg"
    with open(photo_path, "wb") as f:
        f.write(downloaded_file.read())

    await state.clear()
    await execute_sending(message, user_id, chats, caption_text, photo_path, has_media=True, delay=delay)

@dp.callback_query(F.data == "skip_media")
async def skip_media_step(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = temp_post_data.get(user_id, {})
    chats, caption_text, delay = data.get("chats", []), data.get("caption"), data.get("delay", 7)

    await state.clear()
    await callback.message.answer(f"⏳ جاري بدء النشر باستخدام جميع حساباتك بفاصل {delay} ثانية...")
    await execute_sending(callback.message, user_id, chats, caption_text, None, has_media=False, delay=delay)
    await callback.answer()

async def execute_sending(message_obj, user_id, chats, caption_text, media_path, has_media, delay):
    success_count, fail_count = 0, 0
    status_msg = await message_obj.answer("🚀 جارِ تنفيذ الحملة بكل الحسابات المضافة...")
    accounts = users_accounts_db.get(user_id, [])

    for acc in accounts:
        session_string = acc.get("session_string")
        if not session_string:
            continue
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()

            for index, chat in enumerate(chats):
                try:
                    if has_media:
                        await client.send_file(chat, media_path, caption=caption_text)
                    else:
                        await client.send_message(chat, caption_text)
                    success_count += 1
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds)
                    if has_media:
                        await client.send_file(chat, media_path, caption=caption_text)
                    else:
                        await client.send_message(chat, caption_text)
                    success_count += 1
                except Exception:
                    fail_count += 1

                try:
                    await status_msg.edit_text(
                        f"📊 **حالة الحملة الآن:**\n"
                        f"📱 الحساب: `{acc.get('phone')}`\n"
                        f"✅ نجاح: {success_count} | ❌ فشل: {fail_count}\n"
                        f"⏳ جارٍ النشر في: `{chat}`",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

                if index < len(chats) - 1:
                    await asyncio.sleep(delay)

            await client.disconnect()
        except Exception as e:
            print(f"خطأ في الحساب أثناء النشر: {e}")

    if has_media and os.path.exists(media_path):
        os.remove(media_path)

    await message_obj.answer(
        f"🏁 **انتهت الحملة بنجاح عبر جميع حساباتك!**\n"
        f"✅ إجمالي النجاح: {success_count}\n"
        f"❌ إجمالي الفشل: {fail_count}",
        reply_markup=get_main_keyboard(user_id),
        parse_mode="Markdown"
    )

async def main():
    for uid, uaccounts in users_accounts_db.items():
        for acc in uaccounts:
            if acc.get("session_string"):
                start_background_listener(uid, acc["session_string"])

    await set_bot_commands(bot)
    print("البوت يعمل الآن بكامل طاقته ودعم الحسابات المتعددة...")
    await dp.start_polling(bot)

asyncio.run(main())
