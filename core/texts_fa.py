"""همه متن‌های فارسی قابل مشاهده برای کاربران (قالب HTML تلگرام).

هر مقدار متنیِ آمده از کاربر (نام، دلیل، عنوان گروه) باید با `escape` وارد متن شود.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from core.textnorm import fa_digits
from domain.dto import REQUIRED_BOT_PERMISSIONS

PERMISSION_LABELS: dict[str, str] = {
    "is_admin": "مدیر بودن ربات در گروه",
    "can_delete_messages": "حذف پیام‌ها",
    "can_restrict_members": "محدود کردن کاربران",
}

BOT_COMMANDS: tuple[tuple[str, str], ...] = (
    ("start", "شروع و معرفی ربات"),
    ("help", "راهنمای ربات"),
    ("panel", "پنل کاربری"),
)

GROUP_COMMANDS: tuple[tuple[str, str], ...] = BOT_COMMANDS + (
    ("ban", "مسدود کردن کاربر"),
    ("unban", "رفع مسدودی"),
    ("mute", "بی‌صدا کردن کاربر"),
    ("unmute", "رفع سکوت"),
    ("kick", "اخراج کاربر"),
    ("warn", "ثبت اخطار"),
    ("unwarn", "حذف آخرین اخطار"),
    ("info", "اطلاعات کاربر"),
    ("warnings", "اخطارهای کاربر"),
    ("stats", "آمار پیام‌های امروز"),
    ("dailystats", "روشن/خاموش کردن گزارش شبانه"),
    ("xo", "بازی دوز"),
    ("spy", "بازی اسپای (جاسوس)"),
    ("mafia", "بازی مافیا"),
    ("stopgame", "پایان دادن به بازی فعال"),
)

BTN_CONFIRM = "✅ تأیید"
BTN_CANCEL = "❌ لغو"

DURATION_HELP = "مدت: <code>30s</code> ثانیه، <code>10m</code> دقیقه، <code>2h</code> ساعت، <code>1d</code> روز، <code>1w</code> هفته (یا «۱۰ دقیقه»، «دائمی»)"


# ----- ابزارهای قالب‌بندی --------------------------------------------------------


def fa_number(value: int) -> str:
    """عدد با ارقام فارسی و جداکننده هزارگان؛ مثل «۱٬۲۳۴»."""
    return fa_digits(f"{value:,}").replace(",", "٬")


def user_link(external_id: int, name: str) -> str:
    return f'<a href="tg://user?id={external_id}">{escape(name)}</a>'


def display_name(
    first_name: str | None, last_name: str | None, username: str | None, external_id: int
) -> str:
    name = " ".join(part for part in (first_name, last_name) if part).strip()
    if name:
        return name
    return f"@{username}" if username else str(external_id)


def _join(*lines: str | None) -> str:
    return "\n".join(line for line in lines if line)


def _reason_line(reason: str | None) -> str | None:
    return f"📝 دلیل: {escape(reason)}" if reason else None


def _duration_line(duration: str | None, until: str | None) -> str:
    if duration is None:
        return "⏱ مدت: دائمی"
    return f"⏱ مدت: {duration}" + (f" (تا {until})" if until else "")


# ----- عمومی ---------------------------------------------------------------------


def start_private() -> str:
    return (
        "سلام! 👋 من <b>حلی بات</b> هستم، ربات مدیریت و امنیت گروه.\n\n"
        "مرا به گروه اضافه کنید و در آن «مدیر» کنید تا بتوانم کمک کنم.\n\n"
        "<b>از این‌جا شروع کنید</b>\n"
        "▫️ <code>/help</code> — راهنمای کامل\n"
        "▫️ <code>/panel</code> — پنل گروه‌هایی که مدیرشان هستید"
    )


def start_group() -> str:
    return (
        "سلام! من <b>حلی بات</b> هستم و در این گروه فعالم.\n"
        "راهنما: <code>/help</code> • پنل: <code>/panel</code>"
    )


# ----- راهنما ---------------------------------------------------------------------
#
# راهنما به چند بخش کوتاه شکسته شده است؛ هر بخش از دکمه‌های شیشه‌ای باز می‌شود تا
# کاربر با یک دیوار متن روبه‌رو نشود. دستورها داخل <code> هستند تا مونواسپیس
# دیده شوند و با یک نگاه از متن جدا شوند.

HELP_SECTIONS: tuple[tuple[str, str], ...] = (
    ("users", "👮 مدیریت کاربران"),
    ("stats", "📊 آمار و گزارش"),
    ("panel", "🎛 پنل کاربری"),
    ("games", "🎮 بازی‌ها"),
    ("duration", "⏱ مدت‌زمان"),
)


def help_text() -> str:
    return (
        "🛡 <b>حلی بات</b>\n"
        "<i>ربات مدیریت، امنیت و بازی گروه‌های تلگرام</i>\n\n"
        "<b>شروع سریع</b>\n"
        "▫️ <code>/start</code> — معرفی ربات\n"
        "▫️ <code>/help</code> — همین راهنما\n"
        "▫️ <code>/panel</code> — پنل کاربری دکمه‌ای\n\n"
        "<b>پرتکرارترین دستورها</b>\n"
        "▫️ <code>/ban 1d تبلیغات</code> — مسدود کردن\n"
        "▫️ <code>/mute 10m</code> — بی‌صدا کردن\n"
        "▫️ <code>/stats</code> — آمار پیام‌های امروز\n"
        "▫️ <code>/mafia</code> — شروع بازی مافیا\n\n"
        "<blockquote>دستورهای مدیریتی فقط برای مدیران گروه است. روی پیام کاربر "
        "<b>Reply</b> کنید، یا شناسه عددی / @نام‌کاربری بدهید.</blockquote>\n\n"
        "برای جزئیات، یک بخش را انتخاب کنید 👇"
    )


def help_users() -> str:
    return (
        "👮 <b>مدیریت کاربران</b>\n"
        "<blockquote>فقط مدیران گروه. روی پیام کاربر <b>Reply</b> کنید، یا شناسه عددی "
        "/ @نام‌کاربری بدهید.</blockquote>\n\n"
        "<b>مسدود کردن</b>\n"
        "▫️ <code>/ban [مدت] [دلیل]</code> — بدون مدت: مسدودی موقت (پیش‌فرض ۵ ساعت)\n"
        "▫️ <code>/ban دائمی</code> — مسدودی همیشگی؛ کاربر هرگز برنمی‌گردد\n"
        "▫️ <code>/unban</code> — رفع مسدودی\n\n"
        "<b>بی‌صدا کردن</b>\n"
        "▫️ <code>/mute [مدت] [دلیل]</code> — بدون مدت = دائمی\n"
        "▫️ <code>/unmute</code> — رفع سکوت\n\n"
        "<b>اخراج و اخطار</b>\n"
        "▫️ <code>/kick [دلیل]</code> — اخراج (می‌تواند دوباره عضو شود)\n"
        "▫️ <code>/warn [دلیل]</code> — ثبت اخطار\n"
        "▫️ <code>/unwarn</code> — لغو آخرین اخطار فعال\n\n"
        "<b>اطلاعات کاربر</b>\n"
        "▫️ <code>/info</code> — بدون هدف: اطلاعات خودتان\n"
        "▫️ <code>/warnings</code> — فهرست اخطارها\n\n"
        "<b>قواعد</b>\n"
        "▫️ مسدودی موقت پس از پایان مدت خودکار برداشته می‌شود و کاربر می‌تواند برگردد.\n"
        "▫️ مسدودی دائمی هرگز خودبه‌خود برداشته نمی‌شود؛ فقط <code>/unban</code> آن را لغو می‌کند.\n"
        "▫️ با رسیدن اخطارها به سقف، کاربر موقتاً بی‌صدا و شمارنده صفر می‌شود.\n"
        "▫️ روی مدیران گروه، خود ربات و خودتان اجرا نمی‌شود.\n"
        "▫️ همه اقدامات در سابقه ثبت می‌شوند.\n\n"
        "<i>معادل فارسی بدون اسلش: «مسدود»، «سکوت»، «اخراج»، «اخطار»، «اطلاعات»</i>"
    )


def help_stats() -> str:
    return (
        "📊 <b>آمار و گزارش</b>\n\n"
        "▫️ <code>/stats</code> — آمار پیام‌های امروز تا این لحظه\n"
        "▫️ <code>/dailystats on</code> — روشن کردن گزارش شبانه\n"
        "▫️ <code>/dailystats off</code> — خاموش کردن گزارش شبانه\n\n"
        "<blockquote>🌙 هر شب ساعت <b>۲۳:۵۹</b> به وقت تهران، ده نفر فعال‌ترین گروه "
        "اعلام می‌شوند.</blockquote>\n\n"
        "<b>نکته‌ها</b>\n"
        "▫️ فقط تعداد پیام‌ها ذخیره می‌شود، نه متن آن‌ها.\n"
        "▫️ پیام‌های خدماتی و پیام‌های ربات‌ها شمرده نمی‌شوند.\n"
        "▫️ شمارش‌ها ۹۰ روز نگه داشته می‌شوند."
    )


def help_panel() -> str:
    return (
        "🎛 <b>پنل کاربری</b>\n"
        "<blockquote>در گروه: تنظیمات همان گروه • در گفتگوی خصوصی: فهرست گروه‌هایی که "
        "مدیرشان هستید</blockquote>\n\n"
        "<b>دکمه‌های پنل</b>\n"
        "▫️ 📊 آمار امروز — ده نفر فعال‌ترین\n"
        "▫️ 👤 اطلاعات من — نقش، اخطار، محدودیت و مجموع پیام\n"
        "▫️ ⚙️ تنظیمات — پنج تنظیم گروه\n"
        "▫️ 🔄 به‌روزرسانی و ❌ بستن\n\n"
        "<b>تنظیمات قابل تغییر</b>\n"
        "▫️ 🌙 گزارش شبانه — روشن / خاموش\n"
        "▫️ ⚠️ سقف اخطار — ۳ ← ۵ ← ۱۰ ← بدون سقف\n"
        "▫️ 🔇 سکوت خودکار — ۱ ساعت ← ۶ ساعت ← ۲۴ ساعت ← ۷ روز\n"
        "▫️ ⏱ مسدودی موقت — ۱ ساعت ← ۵ ساعت ← ۱۲ ساعت ← ۱ روز ← ۳ روز\n"
        "▫️ 🛡 تأیید مسدودی دائمی — روشن / خاموش\n\n"
        "شروع: <code>/panel</code>"
    )


def help_games() -> str:
    return (
        "🎮 <b>بازی‌های گروهی</b>\n"
        "<blockquote>هر گروه هم‌زمان فقط یک بازی فعال دارد. بازی با دکمه‌های شیشه‌ای "
        "پیش می‌رود و سازنده بازی، مراحل را جلو می‌برد.</blockquote>\n\n"
        "<b>دوز (XO)</b>\n"
        "▫️ <code>/xo</code> — بازی با ربات\n"
        "▫️ <code>/xo</code> + Reply روی پیام حریف — دعوت دونفره\n\n"
        "<b>اسپای (جاسوس)</b>\n"
        "▫️ <code>/spy</code> — ۳ تا ۱۰ نفر؛ همه یک مکان می‌گیرند جز جاسوس\n"
        "▫️ رأی‌گیری برای پیدا کردن جاسوس؛ جاسوس می‌تواند مکان را حدس بزند\n\n"
        "<b>مافیا</b>\n"
        "▫️ <code>/mafia</code> — ۴ تا ۱۲ نفر؛ مافیا، دکتر، کارآگاه و شهروند\n"
        "▫️ شب: مافیا می‌کشد، دکتر نجات می‌دهد، کارآگاه استعلام می‌گیرد\n"
        "▫️ روز: بحث و رأی‌گیری برای اخراج یک نفر\n\n"
        "<b>نکته‌ها</b>\n"
        "▫️ نقش‌ها در <b>پیام خصوصی</b> فرستاده می‌شوند؛ هر بازیکن باید اول ربات را "
        "در خصوصی <code>/start</code> کند.\n"
        "▫️ پایان بازی فعال: <code>/stopgame</code> (سازنده یا مدیر گروه).\n"
        "▫️ معادل فارسی: «دوز»، «اسپای»، «مافیا»، «پایان بازی»"
    )


def help_duration() -> str:
    return (
        "⏱ <b>مدت‌زمان</b>\n"
        "<blockquote>در <code>/ban</code> و <code>/mute</code> استفاده می‌شود. "
        "اگر مدت ننویسید، دائمی است.</blockquote>\n\n"
        "▫️ <code>30s</code> — ثانیه\n"
        "▫️ <code>10m</code> — دقیقه\n"
        "▫️ <code>2h</code> — ساعت\n"
        "▫️ <code>1d</code> — روز\n"
        "▫️ <code>1w</code> — هفته\n"
        "▫️ <code>دائمی</code> — بدون پایان (کاربر هرگز برنمی‌گردد)\n\n"
        "فارسی هم قبول است: <code>۱۰ دقیقه</code>، <code>۲ ساعت</code>، <code>۵ روز</code>\n\n"
        "<b>بدون مدت چه می‌شود؟</b>\n"
        "مسدودی موقت با مدت پیش‌فرض گروه اعمال می‌شود (پیش‌فرض <b>۵ ساعت</b>)؛ پس از آن\n"
        "کاربر خودکار آزاد می‌شود و می‌تواند برگردد. برای مسدودی همیشگی «دائمی» بنویسید.\n"
        "تغییر مدت پیش‌فرض: پنل ← تنظیمات ← «⏱ مسدودی موقت».\n\n"
        "<b>محدوده مجاز</b>\n"
        "حداقل ۳۰ ثانیه و حداکثر ۳۶۶ روز؛ خارج از این بازه، تلگرام آن را «دائمی» حساب می‌کند."
    )


def help_section(name: str) -> str:
    """متن یک بخش راهنما؛ نام ناشناخته → صفحه اصلی."""
    return {
        "users": help_users,
        "stats": help_stats,
        "panel": help_panel,
        "games": help_games,
        "duration": help_duration,
    }.get(name, help_text)()


def group_registered(title: str | None, missing: Sequence[str]) -> str:
    name = f"«{escape(title)}»" if title else "شما"
    text = f"سلام! 👋 من <b>حلی بات</b> هستم. گروه {name} با موفقیت ثبت شد."
    if not missing:
        return text + "\n\n✅ دسترسی‌های موردنیاز ربات کامل است. راهنما: <code>/help</code>"
    needed = REQUIRED_BOT_PERMISSIONS if "is_admin" in missing else tuple(missing)
    lines = "\n".join(f"▫️ {PERMISSION_LABELS.get(key, key)}" for key in needed)
    if "is_admin" in missing:
        lines = f"▫️ {PERMISSION_LABELS['is_admin']}\n" + lines
    return (
        text
        + "\n\n⚠️ برای عملکرد کامل، ربات را مدیر کنید و این دسترسی‌ها را فعال کنید:\n"
        + lines
    )


# ----- خطاها و مجوزها --------------------------------------------------------------


def only_in_groups() -> str:
    return "این دستور فقط در گروه کار می‌کند."


def anonymous_admin() -> str:
    return (
        "⚠️ شما به‌صورت «مدیر ناشناس» (Anonymous) پیام داده‌اید و نمی‌توانم هویتتان را "
        "تشخیص بدهم. حالت ناشناس را در تنظیمات مدیران گروه خاموش کنید."
    )


def not_authorized() -> str:
    return "⛔ فقط مدیران گروه می‌توانند از این دستور استفاده کنند."


def no_permission() -> str:
    return "⛔ نقش شما اجازه استفاده از این دستور را ندارد."


def missing_platform_permission() -> str:
    return "⛔ شما در گروه دسترسی «محدود کردن کاربران» را ندارید."


def bot_needs_rights() -> str:
    return (
        "⚠️ ربات برای این کار دسترسی ندارد. ربات را مدیر کنید و دسترسی "
        "«محدود کردن کاربران» را به آن بدهید."
    )


def internal_error() -> str:
    return "❌ خطای داخلی رخ داد و کار انجام نشد. کمی بعد دوباره تلاش کنید."


def platform_error(kind: str) -> str:
    return {
        "no_rights": bot_needs_rights(),
        "target_is_admin": "⛔ این کار روی مدیران گروه ممکن نیست.",
        "not_found": "⚠️ این کاربر در گروه پیدا نشد (شاید عضو نیست یا شناسه اشتباه است).",
        "not_supergroup": "⚠️ این کار فقط در سوپرگروه ممکن است. گروه را به سوپرگروه تبدیل کنید.",
        "rate_limited": "⏳ تلگرام موقتاً درخواست‌ها را محدود کرده است. چند ثانیه بعد دوباره تلاش کنید.",
        "network": "🌐 ارتباط با سرور تلگرام برقرار نشد. چند لحظه بعد دوباره تلاش کنید.",
    }.get(kind, "❌ انجام نشد؛ تلگرام خطا برگرداند. کمی بعد دوباره تلاش کنید.")


def target_unresolvable() -> str:
    return "⚠️ این کاربر قابل تشخیص نیست (پیام از طرف کانال یا مدیر ناشناس است)."


def username_unknown(username: str) -> str:
    return (
        f"⚠️ کاربری با نام @{escape(username)} را نمی‌شناسم (هنوز در این ربات پیامی نداده). "
        "روی پیام او Reply کنید یا شناسه عددی‌اش را بدهید."
    )


def cannot_target_self() -> str:
    return "⛔ این کار را نمی‌توانید روی خودتان انجام دهید."


def cannot_target_bot() -> str:
    return "⛔ این کار روی خود ربات ممکن نیست."


def cannot_target_admin() -> str:
    return "⛔ این کار روی مدیران گروه ممکن نیست."


def duration_too_short() -> str:
    return "⚠️ مدت خیلی کوتاه است؛ حداقل ۳۰ ثانیه. (تلگرام کمتر از آن را «دائمی» حساب می‌کند.)"


def duration_too_long() -> str:
    return "⚠️ مدت خیلی طولانی است؛ حداکثر ۳۶۶ روز. برای نامحدود، «دائمی» بنویسید."


USAGE: dict[str, str] = {
    "ban": (
        "🚫 <b>مسدود کردن</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/ban [مدت] [دلیل]</code></blockquote>\n\n"
        "▫️ با شناسه: <code>/ban 123456789 1d تبلیغات</code>\n"
        "▫️ بدون مدت: مسدودی موقت (پیش‌فرض ۵ ساعت) و بعد بازگشت آزاد است.\n"
        "▫️ برای مسدودی همیشگی: <code>/ban دائمی</code> (با دکمه تأیید).\n"
        "▫️ معادل فارسی: «مسدود»"
    ),
    "unban": (
        "♻️ <b>رفع مسدودی</b>\n"
        "<blockquote>روی یکی از پیام‌های کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/unban</code></blockquote>\n\n"
        "▫️ با شناسه: <code>/unban 123456789</code>\n"
        "▫️ معادل فارسی: «رفع مسدودیت»"
    ),
    "mute": (
        "🔇 <b>بی‌صدا کردن</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/mute [مدت] [دلیل]</code></blockquote>\n\n"
        "▫️ مثال: <code>/mute 10m</code>\n"
        "▫️ بدون مدت، سکوت دائمی است.\n"
        "▫️ معادل فارسی: «سکوت»"
    ),
    "unmute": (
        "🔊 <b>رفع سکوت</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/unmute</code></blockquote>\n\n"
        "▫️ با شناسه هم می‌شود: <code>/unmute 123456789</code>\n"
        "▫️ معادل فارسی: «رفع سکوت»"
    ),
    "kick": (
        "👢 <b>اخراج</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/kick [دلیل]</code></blockquote>\n\n"
        "▫️ کاربر می‌تواند دوباره عضو شود.\n"
        "▫️ معادل فارسی: «اخراج»"
    ),
    "warn": (
        "⚠️ <b>اخطار</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/warn [دلیل]</code></blockquote>\n\n"
        "▫️ با رسیدن اخطارها به سقف، کاربر موقتاً بی‌صدا می‌شود.\n"
        "▫️ معادل فارسی: «اخطار»"
    ),
    "unwarn": (
        "✅ <b>حذف اخطار</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/unwarn</code></blockquote>\n\n"
        "▫️ آخرین اخطار فعال لغو می‌شود.\n"
        "▫️ معادل فارسی: «حذف اخطار»"
    ),
    "info": (
        "👤 <b>اطلاعات کاربر</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/info</code></blockquote>\n\n"
        "▫️ با شناسه: <code>/info 123456789</code>\n"
        "▫️ بدون هدف، اطلاعات خودتان را نشان می‌دهد."
    ),
    "warnings": (
        "⚠️ <b>اخطارهای کاربر</b>\n"
        "<blockquote>روی پیام کاربر <b>Reply</b> کنید و بنویسید:\n"
        "<code>/warnings</code></blockquote>\n\n"
        "▫️ با شناسه هم می‌شود: <code>/warnings 123456789</code>"
    ),
}


def usage(action: str) -> str:
    text = USAGE.get(action, help_text())
    return text + "\n\n" + DURATION_HELP if action in ("ban", "mute") else text


def moderation_error(kind: str, *, name: str | None = None) -> str:
    """پیام مناسب برای خطاهای `ModerationError` و `TargetError`."""
    if kind == "not_authorized":
        return not_authorized()
    if kind == "no_permission":
        return no_permission()
    if kind == "missing_platform_permission":
        return missing_platform_permission()
    if kind == "cannot_target_self":
        return cannot_target_self()
    if kind == "cannot_target_bot":
        return cannot_target_bot()
    if kind == "cannot_target_admin":
        return cannot_target_admin()
    if kind == "no_active_warning":
        return no_active_warning(name or "این کاربر")
    if kind == "username_unknown":
        return username_unknown(name or "")
    if kind == "target_unresolvable":
        return target_unresolvable()
    return platform_error(kind)


# ----- نتیجه اقدامات ----------------------------------------------------------------


def banned(user: str, duration: str | None, until: str | None, reason: str | None) -> str:
    if duration is None:
        note = "🔒 این مسدودی <b>دائمی</b> است و کاربر دیگر نمی‌تواند به گروه برگردد."
    else:
        note = f"🔓 پس از {duration} مسدودی برداشته می‌شود و کاربر می‌تواند دوباره عضو شود."
    return _join(
        f"🚫 {user} از گروه مسدود شد.",
        _duration_line(duration, until),
        _reason_line(reason),
        note,
    )


def ban_released(user: str) -> str:
    return f"🔓 مدت مسدودی {user} تمام شد؛ اگر بخواهد می‌تواند دوباره عضو شود."


def permanent_ban_blocked(user: str) -> str:
    return f"🚫 {user} مسدودی <b>دائمی</b> دارد و اجازه بازگشت به گروه را ندارد."


def unbanned(user: str) -> str:
    return f"♻️ مسدودی {user} برداشته شد. (برای بازگشت باید دوباره دعوت شود.)"


def not_banned(user: str) -> str:
    return f"ℹ️ {user} مسدود نیست."


def muted(user: str, duration: str | None, until: str | None, reason: str | None) -> str:
    return _join(f"🔇 {user} بی‌صدا شد.", _duration_line(duration, until), _reason_line(reason))


def unmuted(user: str) -> str:
    return f"🔊 سکوت {user} برداشته شد."


def not_muted(user: str) -> str:
    return f"ℹ️ {user} بی‌صدا نیست."


def kicked(user: str, reason: str | None) -> str:
    return _join(f"👢 {user} از گروه اخراج شد (می‌تواند دوباره عضو شود).", _reason_line(reason))


def warned(
    user: str,
    count: int,
    limit: int,
    reason: str | None,
    *,
    auto_mute: str | None = None,
    auto_mute_until: str | None = None,
    auto_mute_failed: bool = False,
) -> str:
    progress = f"{fa_number(count)} از {fa_number(limit)}" if limit > 0 else fa_number(count)
    lines = [f"⚠️ به {user} اخطار داده شد.", f"📊 اخطارهای فعال: {progress}", _reason_line(reason)]
    if auto_mute is not None:
        until = f" (تا {auto_mute_until})" if auto_mute_until else ""
        lines.append(
            f"🔇 چون اخطارها به سقف رسید، {user} به مدت {auto_mute} بی‌صدا شد{until} "
            "و شمارنده اخطارها صفر شد."
        )
    elif auto_mute_failed:
        lines.append(
            "⚠️ اخطارها به سقف رسید ولی بی‌صدا کردن انجام نشد (دسترسی ربات را بررسی کنید)."
        )
    return _join(*lines)


def unwarned(user: str, remaining: int) -> str:
    return f"✅ آخرین اخطار {user} حذف شد. اخطارهای فعال باقی‌مانده: {fa_number(remaining)}"


def no_active_warning(user: str) -> str:
    return f"ℹ️ {user} اخطار فعالی ندارد."


# ----- تأییدیه ------------------------------------------------------------------------


def confirm_ban(user: str, reason: str | None) -> str:
    return _join(
        f"⚠️ آیا از <b>مسدود کردن دائمی</b> {user} مطمئن هستید؟",
        _reason_line(reason),
        "🔒 مسدودی دائمی خودبه‌خود برداشته نمی‌شود و کاربر <b>هرگز</b> نمی‌تواند برگردد.",
        "این درخواست تا ۲ دقیقه معتبر است.",
    )


def confirm_cancelled() -> str:
    return "❌ لغو شد."


def confirm_expired() -> str:
    return "⌛ این درخواست منقضی شده است. دستور را دوباره بفرستید."


def confirm_not_yours() -> str:
    return "این درخواست را کس دیگری داده است."


# ----- اطلاعات کاربر و اخطارها ---------------------------------------------------------

_MEMBER_STATUS_LABELS = {"member": "عضو گروه", "left": "خارج‌شده از گروه", "banned": "مسدود"}
_ROLE_LABELS = {
    "creator": "سازنده گروه",
    "owner": "سازنده گروه",
    "admin": "مدیر گروه",
    "moderator": "ناظر حلی بات",
    "member": "عضو عادی",
}


def info_card(
    *,
    name_link: str,
    external_id: int,
    username: str | None,
    role_key: str,
    member_status: str | None,
    warning_count: int,
    warn_limit: int,
    restriction_lines: Sequence[str],
    first_seen: str | None,
    joined_at: str | None,
    last_active: str | None,
    total_messages: int | None = None,
) -> str:
    warns = f"{fa_number(warning_count)} از {fa_number(warn_limit)}" if warn_limit > 0 else fa_number(warning_count)
    restrictions = "\n".join(restriction_lines) if restriction_lines else "ندارد"
    return _join(
        "👤 <b>اطلاعات کاربر</b>",
        f"نام: {name_link}",
        f"شناسه: <code>{external_id}</code>",
        f"نام کاربری: @{escape(username)}" if username else "نام کاربری: —",
        f"نقش: {_ROLE_LABELS.get(role_key, role_key)}",
        f"وضعیت در گروه: {_MEMBER_STATUS_LABELS.get(member_status or '', 'نامشخص')}",
        f"اخطارهای فعال: {warns}",
        f"محدودیت‌های فعال: {restrictions}",
        f"مجموع پیام‌ها: {fa_number(total_messages)}" if total_messages is not None else None,
        f"اولین مشاهده: {first_seen}" if first_seen else None,
        f"آخرین ورود ثبت‌شده: {joined_at}" if joined_at else None,
        f"آخرین فعالیت: {last_active}" if last_active else None,
    )


def restriction_line(kind: str, until: str | None) -> str:
    label = "🚫 مسدود" if kind == "ban" else "🔇 بی‌صدا"
    return f"{label} ({'تا ' + until if until else 'دائمی'})"


def warnings_list(
    name_link: str, active: int, limit: int, entries: Sequence[tuple[str, str | None, str, bool]]
) -> str:
    """entries: (تاریخ، دلیل، نام صادرکننده، فعال‌بودن)"""
    head = f"⚠️ <b>اخطارهای {name_link}</b>\nفعال: {fa_number(active)}" + (
        f" از {fa_number(limit)}" if limit > 0 else ""
    )
    if not entries:
        return head + "\n\nهیچ اخطاری ثبت نشده است."
    lines = []
    for date, reason, issuer, is_active in entries:
        mark = "🔸" if is_active else "▫️ (لغوشده)"
        lines.append(f"{mark} {date} — توسط {escape(issuer)}" + (f"\n    دلیل: {escape(reason)}" if reason else ""))
    return head + "\n\n" + "\n".join(lines)


# ----- آمار پیام‌ها --------------------------------------------------------------------

_MEDALS = ("🥇", "🥈", "🥉")


def _ranking(rows: Sequence[tuple[str, int]]) -> str:
    lines = []
    for index, (name, count) in enumerate(rows):
        rank = _MEDALS[index] if index < len(_MEDALS) else f"{fa_number(index + 1)}."
        lines.append(f"{rank} {escape(name)} — {fa_number(count)} پیام")
    return "\n".join(lines)


def daily_report(day_label: str, total: int, people: int, rows: Sequence[tuple[str, int]]) -> str:
    return _join(
        f"🌙 <b>آمار پیام‌های امروز</b> — {day_label}",
        f"مجموع: {fa_number(total)} پیام از {fa_number(people)} نفر",
        "",
        "<b>فعال‌ترین‌ها</b>",
        _ranking(rows),
    )


def stats_today(day_label: str, total: int, people: int, rows: Sequence[tuple[str, int]]) -> str:
    if total == 0:
        return f"📊 آمار امروز ({day_label}): هنوز پیامی شمرده نشده است."
    return _join(
        f"📊 <b>آمار پیام‌های امروز تا این لحظه</b> — {day_label}",
        f"مجموع: {fa_number(total)} پیام از {fa_number(people)} نفر",
        "",
        "<b>فعال‌ترین‌ها</b>",
        _ranking(rows),
    )


def dailystats_status(enabled: bool) -> str:
    state = "روشن ✅" if enabled else "خاموش ❌"
    return (
        f"گزارش شبانه آمار پیام‌ها: <b>{state}</b>\n"
        "هر شب ساعت ۲۳:۵۹ (به وقت تهران) ده نفر فعال‌ترین گروه اعلام می‌شود.\n"
        "تغییر: <code>/dailystats on</code> یا <code>/dailystats off</code> "
        "(فارسی: «آمار شبانه روشن / خاموش»)"
    )


def dailystats_changed(enabled: bool) -> str:
    return (
        "✅ گزارش شبانه روشن شد. هر شب ساعت ۲۳:۵۹ آمار پیام‌ها اعلام می‌شود."
        if enabled
        else "✅ گزارش شبانه خاموش شد."
    )


# ----- پنل کاربری ---------------------------------------------------------------------

BTN_PANEL_STATS = "📊 آمار امروز"
BTN_PANEL_ME = "👤 اطلاعات من"
BTN_PANEL_SETTINGS = "⚙️ تنظیمات"
BTN_PANEL_HELP = "📖 راهنما"
BTN_PANEL_REFRESH = "🔄 به‌روزرسانی"
BTN_PANEL_CLOSE = "❌ بستن"
BTN_PANEL_BACK = "↩️ بازگشت"
BTN_PANEL_MY_GROUPS = "📋 گروه‌های من"
BTN_SETTING_DAILY = "🌙 گزارش شبانه"
BTN_SETTING_WARN_LIMIT = "⚠️ سقف اخطار"
BTN_SETTING_WARN_MUTE = "🔇 سکوت خودکار"
BTN_SETTING_CONFIRM = "🛡 تأیید مسدودی دائمی"
BTN_SETTING_BAN_RETURN = "⏱ مسدودی موقت"

ON_OFF = {True: "روشن ✅", False: "خاموش ❌"}


def role_label(key: str) -> str:
    return _ROLE_LABELS.get(key, key)


def panel_group(
    *,
    title: str | None,
    role_key: str,
    member_count: int | None,
    today_total: int,
    today_people: int,
    warn_limit: int,
) -> str:
    name = f"«{escape(title)}»" if title else "این گروه"
    members = fa_number(member_count) if member_count is not None else "—"
    return _join(
        "🎛 <b>پنل مدیریت حلی بات</b>",
        f"گروه: {name}",
        f"نقش شما: {role_label(role_key)}",
        f"اعضا: {members}",
        f"امروز: {fa_number(today_total)} پیام از {fa_number(today_people)} نفر",
        f"سقف اخطار: {fa_number(warn_limit) if warn_limit else 'بدون سقف'}",
        "",
        "یکی از گزینه‌های زیر را انتخاب کنید.",
    )


def panel_private(*, name: str, group_count: int, today_total: int, today_people: int) -> str:
    return _join(
        "🎛 <b>پنل کاربری حلی بات</b>",
        f"سلام {escape(name)}! 👋",
        f"گروه‌های تحت مدیریت شما: <b>{fa_number(group_count)}</b>",
        (
            f"امروز در آن‌ها: {fa_number(today_total)} پیام از {fa_number(today_people)} نفر"
            if group_count
            else "هنوز در هیچ گروهی مدیر نیستید."
        ),
        "",
        "برای دیدن آمار و تنظیمات هر گروه، «گروه‌های من» را بزنید."
        if group_count
        else "ربات را به گروه اضافه و در آن مدیر کنید تا پنل فعال شود.",
    )


def panel_groups_list(*, total: int, page: int, pages: int) -> str:
    if total == 0:
        return (
            "📋 <b>گروه‌های من</b>\n\n"
            "در هیچ گروهی مدیر نیستید. ربات را به گروه اضافه و در آن مدیر کنید."
        )
    footer = f"\n\nصفحه {fa_number(page)} از {fa_number(pages)}" if pages > 1 else ""
    return _join("📋 <b>گروه‌های من</b>", "", "یکی از گروه‌ها را انتخاب کنید.") + footer


def panel_group_button(title: str | None, external_id: int) -> str:
    """برچسب دکمه گروه در فهرست (طول تلگرام محدود است)."""
    label = title or str(external_id)
    return f"👥 {label}"[:60]


def panel_settings(
    *,
    title: str | None,
    daily_report: bool,
    warn_limit: int,
    warn_mute_label: str | None,
    confirm_sensitive: bool,
    ban_return_label: str | None = None,
) -> str:
    name = f"«{escape(title)}»" if title else "این گروه"
    return _join(
        "⚙️ <b>تنظیمات گروه</b>",
        f"گروه: {name}",
        "",
        f"گزارش شبانه: {ON_OFF[daily_report]}",
        f"سقف اخطار: {fa_number(warn_limit) if warn_limit else 'بدون سقف'}",
        f"سکوت خودکار پس از سقف: {warn_mute_label or 'دائمی'}",
        f"مسدودی موقت (بازگشت خودکار): {ban_return_label or '—'}",
        f"تأیید مسدودی دائمی: {ON_OFF[confirm_sensitive]}",
        "",
        "با زدن هر دکمه، مقدار آن تغییر می‌کند.",
    )


def panel_saved() -> str:
    return "✅ ذخیره شد."


def panel_closed() -> str:
    return "پنل بسته شد. هر وقت خواستید /panel را بفرستید."


def help_closed() -> str:
    return "راهنما بسته شد. هر وقت خواستید <code>/help</code> را بفرستید."


def panel_not_admin() -> str:
    return "⛔ شما در این گروه مدیر نیستید و به پنل دسترسی ندارید."


def panel_group_unavailable() -> str:
    return "⚠️ این گروه دیگر در دسترس نیست (ربات از آن خارج شده است)."


def panel_self_only() -> str:
    return "ℹ️ در گفتگوی خصوصی، آمار و تنظیمات از طریق «گروه‌های من» در دسترس است."
