import logging
import os
import json
import asyncio
import aiohttp
import subprocess
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher.filters import Command
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from dotenv import load_dotenv

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
API_TOKEN = os.getenv("8172795119:AAEpaBjmHHDwQ-7YdbB4StGs_3OKmlM6tO4")
CUSTOM_MODEL_PATH = os.getenv("CUSTOM_MODEL_PATH", "model/")  # Путь к моделям и скриптам нейросети

# Папка для хранения сгенерированных изображений
IMAGES_DIR = Path("generated_images")
IMAGES_DIR.mkdir(exist_ok=True)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())


# Кнопка для запуска WebApp
def get_webapp_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    webapp_button = InlineKeyboardButton(
        text="🎨 Создать изображение",
        web_app=types.WebAppInfo(url=os.getenv("WEBAPP_URL"))
    )
    keyboard.add(webapp_button)
    return keyboard


# Обработчик команды /start
@dp.message_handler(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет! Я бот для генерации изображений.\n"
        "Нажмите на кнопку ниже, чтобы открыть WebApp и создать изображение.",
        reply_markup=get_webapp_keyboard()
    )


# Функция для генерации изображения с помощью локальной нейросети
async def generate_image(prompt, user_id, settings=None):
    try:
        # Устанавливаем настройки по умолчанию, если они не переданы
        if settings is None:
            settings = {
                "imageSize": "512x512",
                "style": "default",
                "guidance": "7"
            }

        # Разбираем размер изображения
        try:
            width, height = settings["imageSize"].split("x")
        except (ValueError, KeyError):
            width, height = 512, 512

        # Создаем отдельную папку для пользователя, если её нет
        user_dir = IMAGES_DIR / str(user_id)
        user_dir.mkdir(exist_ok=True)

        # Имя файла для сохранения результата
        image_path = user_dir / "image.jpeg"

        # Логируем параметры генерации
        logging.info(f"Generating image for user {user_id} with prompt: {prompt}")
        logging.info(
            f"Settings: Size={width}x{height}, Style={settings.get('style', 'default')}, Guidance={settings.get('guidance', '7')}")

        # Запускаем скрипт генерации изображения
        cmd = [
            "python",
            f"{CUSTOM_MODEL_PATH}/generate.py",
            "--prompt", prompt,
            "--output", str(image_path),
            "--width", str(width),
            "--height", str(height),
            "--style", settings.get("style", "default"),
            "--guidance", str(settings.get("guidance", "7"))
        ]

        # Запускаем процесс и ждем его завершения
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode()
            logging.error(f"Error generating image: {error_msg}")
            return None, error_msg

        logging.info(f"Image generated successfully: {stdout.decode()}")

        # Проверяем, что файл создан
        if not image_path.exists():
            error_msg = "Image file was not created"
            logging.error(f"{error_msg} at {image_path}")
            return None, error_msg

        return image_path, None
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error generating image: {error_msg}")
        return None, error_msg


# Обработчик для данных, отправленных из WebApp
@dp.message_handler(content_types=types.ContentTypes.WEB_APP_DATA)
async def web_app_data_handler(message: types.Message):
    # Получаем данные из WebApp
    try:
        data = json.loads(message.web_app_data.data)
        prompt = data.get("prompt")
        settings = data.get("settings")
        image_generated = data.get("image_generated", False)  # Флаг, указывающий, было ли изображение уже сгенерировано

        user_id = message.from_user.id

        if not prompt:
            await message.answer("⚠️ Необходимо указать запрос для генерации изображения.")
            return

        # Формируем сообщение о настройках
        settings_info = ""
        if settings:
            size = settings.get("imageSize", "512x512")
            style = settings.get("style", "default")
            guidance = settings.get("guidance", "7")

            # Переводим название стиля на русский
            style_names = {
                "default": "Обычный",
                "anime": "Аниме",
                "realistic": "Фотореалистичный",
                "painting": "Живопись",
                "3d": "3D Рендер",
                "sketch": "Скетч"
            }

            style_name = style_names.get(style, style.capitalize())

            settings_info = f"\n🔧 Настройки: {size}, Стиль: {style_name}, Интенсивность: {guidance}"

        if not image_generated:
            # Если изображение не было сгенерировано ранее
            await message.answer("⏳ Генерирую изображение по вашему запросу...\n"
                                 f"Запрос: {prompt}{settings_info}")

            # Генерация изображения с помощью локальной нейросети
            image_path, error = await generate_image(prompt, user_id, settings)

            if not image_path or not os.path.exists(image_path):
                error_message = "😔 Не удалось сгенерировать изображение. "
                if error:
                    error_message += f"Ошибка: {error}"
                else:
                    error_message += "Пожалуйста, попробуйте другой запрос или измените настройки."
                await message.answer(error_message)
                return

            # Отправляем изображение пользователю
            with open(image_path, 'rb') as photo:
                await bot.send_photo(
                    message.chat.id,
                    photo=photo,
                    caption=f"🎨 Ваше изображение по запросу:\n{prompt}{settings_info}",
                    reply_markup=get_webapp_keyboard()
                )
        else:
            # Если пользователь нажал "Скачать" в WebApp, изображение уже должно быть сгенерировано
            user_dir = IMAGES_DIR / str(user_id)
            image_path = user_dir / "image.jpeg"

            if not os.path.exists(image_path):
                # Если изображение не найдено, предложим сгенерировать новое
                await message.answer("😔 Изображение не найдено. Генерирую новое изображение...")

                # Генерация изображения с помощью локальной нейросети
                image_path, error = await generate_image(prompt, user_id, settings)

                if not image_path or not os.path.exists(image_path):
                    error_message = "😔 Не удалось сгенерировать изображение. "
                    if error:
                        error_message += f"Ошибка: {error}"
                    else:
                        error_message += "Пожалуйста, попробуйте другой запрос или измените настройки."
                    await message.answer(error_message)
                    return

            # Отправляем изображение пользователю
            with open(image_path, 'rb') as photo:
                await bot.send_photo(
                    message.chat.id,
                    photo=photo,
                    caption=f"🎨 Ваше изображение по запросу:\n{prompt}{settings_info}",
                    reply_markup=get_webapp_keyboard()
                )
    except Exception as e:
        logging.error(f"Error processing WebApp data: {e}")
        await message.answer("😔 Произошла ошибка при обработке данных. Пожалуйста, попробуйте еще раз.")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)