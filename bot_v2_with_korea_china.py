import logging
from aiogram import Bot, Dispatcher, executor, types
import aiohttp
import math
import os
from datetime import datetime

API_TOKEN = os.getenv("API_TOKEN")
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_data = {}

# Таблицы ставок для авто 3–5 лет (евро за см3)
def get_customs_rate(volume):
    if volume <= 1000:
        return 1.5
    elif volume <= 1500:
        return 1.7
    elif volume <= 1800:
        return 2.5
    elif volume <= 2400:
        return 2.7
    elif volume <= 3000:
        return 3.0
    else:
        return 0

# Получение курса валюты
async def get_currency_rate(code):
    url = "https://www.cbr-xml-daily.ru/daily_json.js"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return data["Valute"].get(code.upper(), {}).get("Value", 0)

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user_data[message.from_user.id] = {}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🇯🇵 Япония", "🇰🇷 Южная Корея", "🇨🇳 Китай")
    await message.answer("Привет! Выбери страну происхождения автомобиля:", reply_markup=markup)

@dp.message_handler(lambda m: m.text in ["🇯🇵 Япония", "🇰🇷 Южная Корея", "🇨🇳 Китай"])
async def set_country(message: types.Message):
    user_data[message.from_user.id]["country"] = message.text
    await message.answer("Введи примерную стоимость автомобиля (в валюте страны):", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(lambda m: message.from_user.id in user_data and "price" not in user_data[message.from_user.id])
async def set_price(message: types.Message):
    try:
        price = float(message.text.replace(" ", "").replace(",", "."))
        user_data[message.from_user.id]["price"] = price
        await message.answer("Укажи марку и модель автомобиля:")
    except:
        await message.answer("Некорректная сумма. Введи только число.")

@dp.message_handler(lambda m: message.from_user.id in user_data and "model" not in user_data[message.from_user.id])
async def set_model(message: types.Message):
    user_data[message.from_user.id]["model"] = message.text
    await message.answer("Укажи год выпуска автомобиля:")

@dp.message_handler(lambda m: message.from_user.id in user_data and "year" not in user_data[message.from_user.id])
async def set_year(message: types.Message):
    try:
        year = int(message.text)
        user_data[message.from_user.id]["year"] = year
        await message.answer("Укажи объём двигателя (в литрах):")
    except:
        await message.answer("Некорректный год. Введи, например, 2020")

@dp.message_handler(lambda m: message.from_user.id in user_data and "volume" not in user_data[message.from_user.id])
async def set_volume(message: types.Message):
    try:
        volume = float(message.text.replace(",", "."))
        uid = message.from_user.id
        data = user_data[uid]
        data["volume"] = volume

        volume_cm3 = int(volume * 1000)
        age = datetime.now().year - data["year"]

        if age < 3 or volume_cm3 > 3000:
            await message.answer("⚠️ Мы рассчитываем только авто от 3 до 5 лет и объёмом до 3.0 л")
            return

        customs_rate = get_customs_rate(volume_cm3)
        customs_fee_eur = volume_cm3 * customs_rate
        eur_rate = await get_currency_rate("EUR")
        customs_rub = customs_fee_eur * eur_rate + 5200 + 2200

        country = data["country"]
        model = data["model"]
        year = data["year"]
        price = data["price"]

        if country == "🇯🇵 Япония":
            jpy_rate = await get_currency_rate("JPY")
            full_yen = price + 164500
            total_rub = full_yen * jpy_rate + 30000 + 45000 + 55000 + customs_rub
            vlad_details = "(временная регистрация, экспертиза, таможенное оформление, перегон, услуги таможенного брокера)"
            response = f"🚗 {model}, {year} г., {volume} л\nСтрана: Япония\nЦена: ¥{int(price):,} | Курс ¥: {jpy_rate:.2f} ₽\n\n" \
                       f"💴 Расходы по Японии:\n- Расходы по Японии: ¥50 000\n- Фрахт: ¥50 000\n- ПРР, лаборатория: ¥64 500\n\n" \
                       f"🛃 Таможенная пошлина и оформление: {int(customs_rub):,} ₽\n\n" \
                       f"📦 Расходы по Владивостоку\n{vlad_details}:\n- 45 000 ₽\n\n💼 Комиссия JPCARS: 55 000 ₽\n\n✅ ИТОГО: {math.ceil(total_rub / 1000) * 1000:,} ₽"

        elif country == "🇰🇷 Южная Корея":
            krw_rate = await get_currency_rate("KRW")
            total_won = price + 1_640_000
            total_rub = total_won * krw_rate + 50000 + 100000 + 65000 + customs_rub
            vlad_details = "(экспертиза, временная регистрация, таможенное оформление, лаборатория, погрузочно-разгрузочные работы, ЭПТС, СБКТС, услуги таможенного брокера, перегон)"
            response = f"🚗 {model}, {year} г., {volume} л\nСтрана: Южная Корея\nЦена: ₩{int(price):,} | Курс ₩: {krw_rate:.3f} ₽\n\n" \
                       f"💴 Расходы по Корее и доставка: ₩1 640 000\n\n" \
                       f"🛃 Таможенная пошлина и оформление: {int(customs_rub):,} ₽\n\n" \
                       f"📦 Расходы по Владивостоку\n{vlad_details}:\n- 100 000 ₽\n\n💼 Комиссия JPCARS: 65 000 ₽\n\n✅ ИТОГО: {math.ceil(total_rub / 1000) * 1000:,} ₽"

        elif country == "🇨🇳 Китай":
            cny_rate = await get_currency_rate("CNY")
            total_cny = price + 20000
            total_rub = total_cny * cny_rate + 50000 + 110000 + 65000 + customs_rub
            vlad_details = "(экспертиза, временная регистрация, таможенное оформление, лаборатория, погрузочно-разгрузочные работы, ЭПТС, СБКТС, услуги таможенного брокера, перегон)"
            response = f"🚗 {model}, {year} г., {volume} л\nСтрана: Китай\nЦена: ¥{int(price):,} | Курс ¥: {cny_rate:.2f} ₽\n\n" \
                       f"💴 Расходы по Китаю и доставка до Уссурийска: ¥20 000\n\n" \
                       f"🛃 Таможенная пошлина и оформление: {int(customs_rub):,} ₽\n\n" \
                       f"📦 Расходы по Владивостоку\n{vlad_details}:\n- 110 000 ₽\n\n💼 Комиссия JPCARS: 65 000 ₽\n\n✅ ИТОГО: {math.ceil(total_rub / 1000) * 1000:,} ₽"

        else:
            response = "❌ Неизвестная страна."

        await message.answer(response.replace(",", " "))
    except:
        await message.answer("Некорректный объём. Введи в формате 1.5, 2.0 и т.д.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
