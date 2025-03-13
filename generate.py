#!/usr/bin/env python3
"""
Скрипт для генерации изображений с использованием Yandex Cloud ML.
Принимает текстовый запрос и сохраняет результат в указанный файл.
"""

import argparse
import os
import sys
import logging
import pathlib
from yandex_cloud_ml_sdk import YCloudML

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Генерация изображений с помощью Yandex Cloud ML")
    parser.add_argument("--prompt", type=str, required=True, help="Текстовый запрос для генерации")
    parser.add_argument("--output", type=str, required=True, help="Путь для сохранения результата")
    parser.add_argument("--width", type=int, default=512, help="Ширина изображения")
    parser.add_argument("--height", type=int, default=512, help="Высота изображения")
    parser.add_argument("--style", type=str, default="default", help="Стиль изображения")
    parser.add_argument("--guidance", type=str, default="7", help="Интенсивность соответствия запросу")
    parser.add_argument("--seed", type=int, help="Сид для воспроизводимости результатов")
    return parser.parse_args()


def get_width_height_ratio(width, height):
    """Преобразует абсолютные размеры в соотношение сторон для API Yandex"""
    if width > height:
        return width / height, 1
    elif height > width:
        return 1, height / width
    else:
        return 1, 1


def get_style_prompt(style, prompt):
    """Добавляет модификатор стиля к промпту"""
    style_modifiers = {
        "default": "",
        "anime": ", anime style, manga, japanese animation",
        "realistic": ", photorealistic, detailed, 8k, high definition, lifelike",
        "painting": ", oil painting, artistic, detailed brushstrokes, canvas texture",
        "3d": ", 3D render, octane render, blender, cinema 4d, unreal engine",
        "sketch": ", pencil sketch, hand-drawn, black and white, detailed drawing"
    }

    return prompt + style_modifiers.get(style, "")


def main():
    args = parse_args()

    output_path = pathlib.Path(args.output)
    output_dir = output_path.parent

    # Создаем директорию для сохранения, если она не существует
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    logger.info(f"Начинаю генерацию изображения по запросу: {args.prompt}")

    try:
        # Настраиваем SDK для Yandex Cloud ML
        sdk = YCloudML(
            folder_id="b1g3dg8oan85f3j1vgrm",
            auth="AQVN3dwYKCPHEuaXcoN47dkY3l_5uiKo3aNmuVXA",
        )

        # Получаем модель генерации изображений
        model = sdk.models.image_generation("yandex-art")

        # Вычисляем соотношение сторон
        width_ratio, height_ratio = get_width_height_ratio(args.width, args.height)

        # Модифицируем промпт в соответствии с выбранным стилем
        styled_prompt = get_style_prompt(args.style, args.prompt)

        # Настраиваем модель
        model_config = {
            "width_ratio": width_ratio,
            "height_ratio": height_ratio
        }

        # Добавляем seed, если он указан
        if args.seed:
            model_config["seed"] = args.seed

        model = model.configure(**model_config)

        # Запускаем генерацию
        logger.info(f"Запускаю генерацию с промптом: {styled_prompt}")
        logger.info(f"Параметры: width_ratio={width_ratio}, height_ratio={height_ratio}, style={args.style}")

        operation = model.run_deferred(styled_prompt)
        result = operation.wait()

        # Сохраняем результат
        output_path.write_bytes(result.image_bytes)

        logger.info(f"Изображение успешно сгенерировано и сохранено в {args.output}")
        return 0

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())