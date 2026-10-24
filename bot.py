import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path

from PIL import Image
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

# ═══════════════════════════════════════
# 🔑 ВСТАВЬ ТОКЕН СЮДА
BOT_TOKEN = "8701720120:AAErq7jaDIbPJbC74ZPC4LbNCtgskUGBXkI"
# ═══════════════════════════════════════

APK, NAME, ICON = range(3)

BG = "━━━━━━━━━━━━━━━━━━"


def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️  РЕДАКТИРОВАТЬ APK", callback_data="edit")],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="profile"),
            InlineKeyboardButton("📖 Помощь", callback_data="help")
        ],
        [InlineKeyboardButton("⚙️ О боте", callback_data="about")]
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    text = (
        "✦ <b>APK EDITOR</b>\n"
        f"<code>{BG}</code>\n\n"
        "🟣 <b>Редактор Android-приложений</b>\n\n"
        "Измени название и иконку своего APK "
        "в несколько простых шагов.\n\n"
        "✦ Отправь APK-файл\n"
        "✦ Укажи новое название\n"
        "✦ Загрузи новую иконку\n"
        "✦ Получи собранный APK\n\n"
        f"<code>{BG}</code>\n"
        "⚡ <i>Минимализм. Скорость. Удобство.</i>"
    )

    await update.message.reply_text(
        text, reply_markup=menu(), parse_mode="HTML"
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "edit":
        await q.message.reply_text(
            "✦ <b>НОВЫЙ ПРОЕКТ</b>\n\n"
            "📦 Отправь APK-файл документом.\n"
            "Размер файла должен укладываться в лимиты Telegram.",
            parse_mode="HTML"
        )
        return await begin_edit(q, context)

    if q.data == "profile":
        user = q.from_user
        await q.message.reply_text(
            "👤 <b>ТВОЙ ПРОФИЛЬ</b>\n"
            f"{BG}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"✦ Имя: {user.first_name}\n"
            "🛠 Редактор: APK Editor",
            parse_mode="HTML",
            reply_markup=menu()
        )

    elif q.data == "help":
        await q.message.reply_text(
            "📖 <b>КАК ПОЛЬЗОВАТЬСЯ</b>\n\n"
            "1. Нажми «Редактировать APK».\n"
            "2. Отправь APK документом.\n"
            "3. Напиши новое название приложения.\n"
            "4. Отправь новую иконку PNG или JPG.\n"
            "5. Дождись результата сборки.",
            parse_mode="HTML",
            reply_markup=menu()
        )

    elif q.data == "about":
        await q.message.reply_text(
            "⚙️ <b>APK EDITOR</b>\n\n"
            "Бот для изменения названия и иконки APK.\n"
            "Для сборки на сервере необходимы "
            "Java, apktool и Android Build Tools.",
            parse_mode="HTML",
            reply_markup=menu()
        )


async def begin_edit(q, context):
    context.user_data.clear()
    return APK


async def get_apk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document

    if not doc or not doc.file_name.lower().endswith(".apk"):
        await update.message.reply_text("❌ Отправь APK именно как документ.")
        return APK

    if doc.file_size and doc.file_size > 45 * 1024 * 1024:
        await update.message.reply_text("❌ Файл слишком большой для этого бота.")
        return APK

    context.user_data["apk_name"] = doc.file_name
    f = await doc.get_file()
    path = os.path.join(tempfile.gettempdir(), f"input_{update.effective_user.id}.apk")
    await f.download_to_drive(path)
    context.user_data["apk_path"] = path

    await update.message.reply_text(
        "✅ <b>APK загружен!</b>\n\n"
        "✏️ Теперь напиши новое название приложения.",
        parse_mode="HTML"
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()

    if not name or len(name) > 60:
        await update.message.reply_text("❌ Название должно быть от 1 до 60 символов.")
        return NAME

    context.user_data["new_name"] = name

    await update.message.reply_text(
        "🎨 <b>Название сохранено!</b>\n\n"
        "Теперь отправь новую иконку картинкой или файлом.\n"
        "Лучше использовать квадратное изображение PNG.",
        parse_mode="HTML"
    )
    return ICON


async def get_icon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1] if update.message.photo else None
    doc = update.message.document

    if not photo and not (
        doc and (doc.mime_type or "").startswith("image/")
    ):
        await update.message.reply_text("❌ Отправь изображение PNG или JPG.")
        return ICON

    file_obj = await (photo.get_file() if photo else doc.get_file())
    icon_path = os.path.join(tempfile.gettempdir(), f"icon_{update.effective_user.id}.png")
    await file_obj.download_to_drive(icon_path)
    context.user_data["icon_path"] = icon_path

    await update.message.reply_text(
        "⏳ <b>Проект принят!</b>\n\n"
        "Собираю приложение. Это может занять некоторое время.",
        parse_mode="HTML"
    )

    try:
        output = await build_apk(context.user_data)
        with open(output, "rb") as apk_file:
            await update.message.reply_document(
                document=apk_file,
                filename="edited_app.apk",
                caption="✅ APK собран!\n\n✦ APK Editor"
            )
    except Exception as e:
        await update.message.reply_text(
            "❌ Не удалось собрать APK.\n\n"
            "Проверь, установлены ли на сервере Java, apktool, "
            "zipalign и apksigner.\n\n"
            f"Техническая ошибка: <code>{str(e)[:700]}</code>",
            parse_mode="HTML"
        )
    finally:
        for key in ("apk_path", "icon_path"):
            p = context.user_data.get(key)
            if p and os.path.exists(p):
                os.remove(p)
        context.user_data.clear()

    await update.message.reply_text(
        "Главное меню:",
        reply_markup=menu()
    )
    return ConversationHandler.END


async def build_apk(data):
    work = tempfile.mkdtemp(prefix="apkeditor_")
    try:
        decoded = os.path.join(work, "decoded")
        unsigned = os.path.join(work, "unsigned.apk")
        aligned = os.path.join(work, "aligned.apk")
        output = os.path.join(work, "edited_app.apk")

        subprocess.run(
            ["apktool", "d", data["apk_path"], "-o", decoded, "-f"],
            check=True, capture_output=True, text=True
        )

        manifest = Path(decoded) / "AndroidManifest.xml"
        content = manifest.read_text(encoding="utf-8")

        # Обновляем label, если он указан прямо в Manifest.
        content = re.sub(
            r'android:label="[^"]*"',
            'android:label="{}"'.format(
                data["new_name"].replace("&", "&amp;").replace('"', '\\"')
            ),
            content,
            count=1
        )
        manifest.write_text(content, encoding="utf-8")

        # Обновляем строковый ресурс app_name, если он существует.
        values = Path(decoded) / "res" / "values"
        if values.exists():
            for strings in values.glob("strings.xml"):
                text = strings.read_text(encoding="utf-8")
                text = re.sub(
                    r'(<string name="app_name"[^>]*>).*?(</string>)',
                    lambda m: m.group(1) + data["new_name"] + m.group(2),
                    text,
                    count=1,
                    flags=re.S
                )
                strings.write_text(text, encoding="utf-8")

        # Заменяем существующие PNG-иконки с подходящими именами.
        icon = Image.open(data["icon_path"]).convert("RGBA")
        for folder in (Path(decoded) / "res").glob("*"):
            if folder.is_dir() and (
                folder.name.startswith("mipmap") or
                folder.name.startswith("drawable")
            ):
                for p in folder.iterdir():
                    if p.is_file() and p.suffix.lower() == ".png" and (
                        "ic_launcher" in p.name or "launcher_icon" in p.name
                    ):
                        with Image.open(p) as old:
                            size = old.size
                        icon.resize(size).save(p, "PNG")

        subprocess.run(
            ["apktool", "b", decoded, "-o", unsigned],
            check=True, capture_output=True, text=True
        )

        keystore = os.environ.get("KEYSTORE_PATH", "editor.keystore")
        password = os.environ.get("KEYSTORE_PASSWORD", "")
        alias = os.environ.get("KEY_ALIAS", "apkeditor")

        subprocess.run(
            ["zipalign", "-f", "4", unsigned, aligned],
            check=True, capture_output=True, text=True
        )
        subprocess.run(
            [
                "apksigner", "sign",
                "--ks", keystore,
                "--ks-key-alias", alias,
                "--ks-pass", "pass:" + password,
                "--out", output,
                aligned
            ],
            check=True, capture_output=True, text=True
        )

        # Переносим результат в постоянный временный файл до очистки папки.
        final = os.path.join(tempfile.gettempdir(), f"result_{os.getpid()}.apk")
        shutil.copy2(output, final)
        return final
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❎ Редактирование отменено.", reply_markup=menu())
    return ConversationHandler.END


def main():
    if BOT_TOKEN == "ВСТАВЬ_ТОКЕН_СЮДА":
        raise RuntimeError("Вставь токен бота в строку BOT_TOKEN в начале файла.")

    app = Application.builder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(buttons, pattern="^edit$")],
        states={
            APK: [MessageHandler(filters.Document.ALL, get_apk)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ICON: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, get_icon)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conversation)
    app.add_handler(CallbackQueryHandler(buttons))

    print("APK Editor запущен.")
    app.run_polling()


if __name__ == "__main__":
    main()