import logging
from functools import cache
from io import BytesIO
from os import environ
from importlib import resources

import PIL.Image
from PIL.Image import Image
from telegram import Message, PhotoSize, Update, User
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def get_profile_photo(user: User) -> Image | None:
    profile_photos = user.get_profile_photos(limit=1)
    if profile_photos is None or profile_photos.total_count == 0:
        return None

    most_recent = profile_photos.photos[0]
    return load_largest_photo(most_recent)


def load_largest_photo(sizes: list[PhotoSize]) -> Image:
    largest = max(sizes, key=lambda photo: photo.width)

    buffer = BytesIO()
    largest.get_file().download(out=buffer)
    return PIL.Image.open(buffer).convert("RGBA")


@cache
def get_overlay(size: tuple[int, int]) -> Image:
    overlay_path = resources.path(__package__, "lula.png")
    return PIL.Image.open(overlay_path).convert("RGBA").resize(size)


def apply_overlay(photo: Image) -> Image:
    overlay = get_overlay(photo.size)
    return PIL.Image.alpha_composite(photo, overlay)


def save_image(image: Image) -> BytesIO:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def start(update: Update, context: CallbackContext) -> None:
    assert (user := update.effective_user) is not None
    assert (msg := update.message) is not None

    photo = get_profile_photo(user)
    if photo is None:
        msg.reply_text("Você não tem foto de perfil. Me envie uma foto!")
        return

    reply_with_new_photo(msg, photo)
    msg.reply_text("Para aplicar em outras fotos, basta me enviar a qualquer momento!")


def handle_received_photo(update: Update, context: CallbackContext) -> None:
    assert (msg := update.message) is not None
    assert msg.photo is not None
    photo = load_largest_photo(msg.photo)
    reply_with_new_photo(msg, photo)


def reply_with_new_photo(msg: Message, photo: Image) -> None:
    msg.reply_text("Aguarde um instante...")
    new_photo = apply_overlay(photo)
    msg.reply_photo(save_image(new_photo))


def handle_error(update: Update, context: CallbackContext) -> None:
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    assert (msg := update.message) is not None
    msg.reply_text(
        "Opa! Ocorreu um erro inesperado. Tente novamente, ou tente algo diferente."
    )


def main() -> None:
    updater = Updater(environ["TOKEN"])
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start, run_async=True))
    dispatcher.add_handler(CommandHandler("aplicar", start, run_async=True))
    dispatcher.add_handler(
        MessageHandler(Filters.photo, handle_received_photo, run_async=True)
    )
    dispatcher.add_error_handler(handle_error)

    updater.start_polling()
