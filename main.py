import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ========================================================
# ⚙️ SOZLAMALAR (Faqat shu yerni o‘zgartiring)
# ========================================================
TELEGRAM_TOKEN = "8908621766:AAECM8wqrAdqJ3eBGQvmXJJ3vj8kkzftOw4"
OPENROUTER_API_KEY = "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"
ADMIN_ID = 1903466700

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class MurojaatState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_problem = State()

HOKIMLIK_PROMPT = """
Siz Andijon viloyati Marhamat tumani hokimligining rasmiy virtual yordamchisiz.
Har doim "Hurmatli fuqaro" deb murojaat qiling.
Javoblaringiz rasmiy, xushmuomala, aniq va foydali bo‘lsin.
Agar fuqaro shikoyat yoki ariza yozsa, uni diqqat bilan tinglang va yordam berishga harakat qiling.
"""

# ---------- /start ----------
@dp.message(CommandStart())
async def start_command(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply(
        f"Assalomu alaykum, hurmatli {message.from_user.full_name}!\n\n"
        "Marhamat tumani hokimligining rasmiy virtual yordamchisi.\n\n"
        "Sizga qanday yordam bera olaman?\n"
        "• Savol bersangiz — javob beraman\n"
        "• Shikoyat yoki ariza yozmoqchi bo‘lsangiz — /murojaat buyrug‘ini bosing"
    )

# ---------- /murojaat ----------
@dp.message(Command("murojaat"))
async def start_murojaat(message: types.Message, state: FSMContext):
    await state.set_state(MurojaatState.waiting_for_name)
    await message.reply(
        "Hurmatli fuqaro, murojaatingizni rasmiy qabul qilish uchun kerakli ma'lumotlarni kiriting.\n\n"
        "1️⃣ To‘liq ismingizni (F.I.Sh) yozing:"
    )

@dp.message(MurojaatState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(MurojaatState.waiting_for_phone)
    await message.reply("2️⃣ Telefon raqamingizni yozing (masalan: +99890 123 45 67):")

@dp.message(MurojaatState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(MurojaatState.waiting_for_problem)
    await message.reply("3️⃣ Endi murojaatingiz mazmunini batafsil yozing:")

@dp.message(MurojaatState.waiting_for_problem)
async def process_problem(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    name = data.get("name")
    phone = data.get("phone")
    problem = message.text
    user = message.from_user

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # AI orqali kategoriya va qisqacha tahlil
    classify_prompt = f"""
Siz hokimlik murojaatlarini saralovchi mutaxassissiz.
Faqat quyidagi formatda javob bering:

Kategoriya: [bitta kategoriya]
Qisqacha: [muammoni 1-2 gapda aniq yozing]

Mumkin bo‘lgan kategoriyalar:
- Kommunal xizmatlar
- Yo‘llar va transport
- Qurilish va yer masalalari
- Ijtimoiy yordam
- Tadbirkorlik
- Ta’lim
- Sog‘liqni saqlash
- Xavfsizlik
- Boshqa

Murojaat:
{problem}
"""

    kategoriya = "Aniqlanmagan"
    qisqacha = problem[:120] + "..." if len(problem) > 120 else problem

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "nvidia/nemotron-3-super-120b-a12b:free",
                    "messages": [{"role": "user", "content": classify_prompt}],
                    "temperature": 0.2
                },
                timeout=25
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_text = result["choices"][0]["message"]["content"]
                    for line in ai_text.split("\n"):
                        if "kategoriya:" in line.lower():
                            kategoriya = line.split(":", 1)[1].strip()
                        elif "qisqacha:" in line.lower():
                            qisqacha = line.split(":", 1)[1].strip()
    except Exception as e:
        logging.error(f"Saralash xatosi: {e}")

    # Admin ga yuborish
    admin_text = (
        f"📥 <b>Yangi rasmiy murojaat</b>\n\n"
        f"📂 <b>Kategoriya:</b> {kategoriya}\n"
        f"🔍 <b>Muammo:</b> {qisqacha}\n\n"
        f"👤 <b>F.I.Sh:</b> {name}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"👤 Username: @{user.username if user.username else 'yo‘q'}\n\n"
        f"📝 <b>To‘liq matn:</b>\n{problem}"
    )

    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
        await message.reply(
            "Hurmatli fuqaro, murojaatingiz muvaffaqiyatli qabul qilindi va tegishli bo‘limga yo‘naltirildi.\n\n"
            "Rahmat!"
        )
    except Exception as e:
        logging.error(f"Admin ga yuborish xatosi: {e}")
        await message.reply("Hurmatli fuqaro, murojaatingiz qabul qilindi.")

# ---------- ODDIY SUHBAT ----------
@dp.message(F.text)
async def handle_ai_chat(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Fuqaroga AI javob
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "nvidia/nemotron-3-super-120b-a12b:free",
                    "messages": [
                        {"role": "system", "content": HOKIMLIK_PROMPT},
                        {"role": "user", "content": message.text}
                    ],
                    "temperature": 0.4
                },
                timeout=30
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_javob = result["choices"][0]["message"]["content"]
                    await message.reply(ai_javob)
                else:
                    await message.reply("Hurmatli fuqaro, tizimda vaqtincha uzilish bor. Keyinroq urinib ko‘ring.")
    except Exception as e:
        logging.error(f"AI javob xatosi: {e}")
        await message.reply("Hurmatli fuqaro, texnik xatolik yuz berdi.")

    # Agar shikoyatga o‘xshasa — admin ga ham yuborish
    lower_text = message.text.lower()
    shikoyat_sozlar = ["shikoyat", "ariza", "muammo", "ishlamayapti", "buzilgan", "yordam kerak", "murojaat"]
    
    if any(soz in lower_text for soz in shikoyat_sozlar) and len(message.text) > 25:
        try:
            admin_text = (
                f"🔔 <b>Avtomatik aniqlangan murojaat</b>\n\n"
                f"👤 {message.from_user.full_name}\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📝 Matn:\n{message.text}"
            )
            await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
        except:
            pass

async def main():
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
