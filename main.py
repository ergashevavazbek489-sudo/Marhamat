import asyncio
import logging
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ========================================================
# SOZLAMALAR — bu yerga o‘zingizning qiymatlaringizni yozing
# (Renderda Environment Variables orqali ham berishingiz mumkin)
# ========================================================
TELEGRAM_TOKEN = os.getenv("8527782970:AAF8k4DIZzS21VeimBk_MyvYs0cHX2WNQSk", "8527782970:AAF8k4DIZzS21VeimBk_MyvYs0cHX2WNQSk")
OPENROUTER_API_KEY = os.getenv("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", "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")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1903466700"))

# Bepul modellar (birinchi ishlamasa keyingisini sinaydi)
MODELS = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
]

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class MurojaatState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_problem = State()

HOKIMLIK_PROMPT = """
Siz Andijon viloyati Marhamat tumani hokimligining rasmiy virtual yordamchisiz.
Har doim "Hurmatli fuqaro" deb murojaat qiling.
Javoblaringiz rasmiy, xushmuomala, aniq va foydali bo‘lsin.
Agar fuqaro shikoyat yoki ariza yozsa, uni diqqat bilan tinglang.
"""

async def ask_ai(messages: list) -> str | None:
    """OpenRouter orqali AI javob olish. Modellarni ketma-ket sinaydi."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/marhamat_bot",
        "X-Title": "Marhamat Hokimligi Bot",
    }

    for model in MODELS:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1000,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=35) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    logging.error(f"Model {model} xato {resp.status}: {text[:300]}")
        except Exception as e:
            logging.error(f"Model {model} ulanish xatosi: {e}")
    return None


# ---------- /start ----------
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply(
        f"Assalomu alaykum, hurmatli {message.from_user.full_name}!\n\n"
        "Marhamat tumani hokimligining rasmiy virtual yordamchisi.\n\n"
        "• Savol bersangiz — javob beraman\n"
        "• Shikoyat/ariza uchun — /murojaat buyrug‘ini bosing"
    )


# ---------- /murojaat ----------
@dp.message(Command("murojaat"))
async def murojaat_start(message: types.Message, state: FSMContext):
    await state.set_state(MurojaatState.waiting_for_name)
    await message.reply(
        "Hurmatli fuqaro, murojaatni qabul qilish uchun ma'lumot kerak.\n\n"
        "1️⃣ To‘liq ismingizni (F.I.Sh) yozing:"
    )


@dp.message(MurojaatState.waiting_for_name)
async def murojaat_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(MurojaatState.waiting_for_phone)
    await message.reply("2️⃣ Telefon raqamingizni yozing (masalan: +99890 123 45 67):")


@dp.message(MurojaatState.waiting_for_phone)
async def murojaat_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(MurojaatState.waiting_for_problem)
    await message.reply("3️⃣ Murojaatingiz mazmunini batafsil yozing:")


@dp.message(MurojaatState.waiting_for_problem)
async def murojaat_problem(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    name = data.get("name", "-")
    phone = data.get("phone", "-")
    problem = message.text
    user = message.from_user

    await bot.send_chat_action(message.chat.id, "typing")

    classify_prompt = (
        "Siz hokimlik murojaatlarini saralovchisiz. Faqat shu formatda javob bering:\n"
        "Kategoriya: [bitta]\n"
        "Qisqacha: [1-2 gap]\n\n"
        "Kategoriyalar: Kommunal xizmatlar, Yo‘llar va transport, Qurilish va yer, "
        "Ijtimoiy yordam, Tadbirkorlik, Ta’lim, Sog‘liqni saqlash, Xavfsizlik, Boshqa\n\n"
        f"Murojaat:\n{problem}"
    )

    kategoriya, qisqacha = "Aniqlanmagan", (problem[:120] + "..." if len(problem) > 120 else problem)
    ai = await ask_ai([{"role": "user", "content": classify_prompt}])
    if ai:
        for line in ai.splitlines():
            low = line.lower()
            if low.startswith("kategoriya:"):
                kategoriya = line.split(":", 1)[1].strip()
            elif low.startswith("qisqacha:"):
                qisqacha = line.split(":", 1)[1].strip()

    admin_text = (
        f"📥 <b>Yangi rasmiy murojaat</b>\n\n"
        f"📂 <b>Kategoriya:</b> {kategoriya}\n"
        f"🔍 <b>Muammo:</b> {qisqacha}\n\n"
        f"👤 <b>F.I.Sh:</b> {name}\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"👤 @{user.username or 'yo‘q'}\n\n"
        f"📝 <b>To‘liq matn:</b>\n{problem}"
    )

    try:
        await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
        await message.reply(
            "Hurmatli fuqaro, murojaatingiz qabul qilindi va tegishli bo‘limga yo‘naltirildi.\n\nRahmat!"
        )
    except Exception as e:
        logging.error(f"Admin ga yuborish xatosi: {e}")
        await message.reply("Hurmatli fuqaro, murojaatingiz qabul qilindi.")


# ---------- Oddiy suhbat ----------
@dp.message(F.text)
async def chat_handler(message: types.Message, state: FSMContext):
    if await state.get_state() is not None:
        return

    await bot.send_chat_action(message.chat.id, "typing")

    ai = await ask_ai([
        {"role": "system", "content": HOKIMLIK_PROMPT},
        {"role": "user", "content": message.text},
    ])

    if ai:
        await message.reply(ai)
    else:
        await message.reply(
            "Hurmatli fuqaro, tizimda vaqtincha uzilish bor. Keyinroq urinib ko‘ring."
        )

    # Shikoyatga o‘xshasa admin ga ham yuborish
    low = message.text.lower()
    sozlar = ["shikoyat", "ariza", "muammo", "ishlamayapti", "buzilgan", "yordam kerak", "murojaat"]
    if any(s in low for s in sozlar) and len(message.text) > 25:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🔔 <b>Avtomatik murojaat</b>\n\n"
                f"👤 {message.from_user.full_name}\n"
                f"🆔 <code>{message.from_user.id}</code>\n"
                f"📝 {message.text}",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ---------- Render uchun web server ----------
async def ping(request):
    return web.Response(text="Bot ishlayapti")


async def web_server():
    app = web.Application()
    app.router.add_get("/", ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info(f"Web server {port}-portda")


async def main():
    logging.info("Bot ishga tushmoqda...")
    await asyncio.gather(web_server(), dp.start_polling(bot))


if __name__ == "__main__":
    asyncio.run(main())
