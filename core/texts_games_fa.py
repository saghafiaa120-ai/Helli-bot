"""متن‌های فارسی بازی‌ها: دوز (XO)، اسپای (Spyfall) و مافیا.

قالب متن‌ها HTML تلگرام است؛ هر مقدار آمده از کاربر (نام، مکان، دلیل) باید با
`escape` وارد متن شود. متن‌ها از منطق بازی جدا هستند تا تغییر جمله‌ها آسان باشد.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from core.textnorm import fa_digits

# ----- دکمه‌های مشترک ---------------------------------------------------------------

BTN_JOIN = "🙋 ورود به بازی"
BTN_LEAVE = "🚪 خروج"
BTN_START = "▶️ شروع بازی"
BTN_CANCEL = "❌ لغو"
BTN_NEW = "🔄 بازی جدید"
BTN_CLOSE = "❌ بستن"
BTN_ACCEPT = "✅ قبول"
BTN_DECLINE = "❌ رد"

XO_MARKS = {"X": "❌", "O": "⭕"}
EMPTY_CELL = "▫️"

MAFIA_ROLE_LABELS = {
    "mafia": "🕵️ مافیا",
    "doctor": "🩺 دکتر",
    "detective": "🔍 کارآگاه",
    "citizen": "👤 شهروند",
}


def role_label(role: str) -> str:
    return MAFIA_ROLE_LABELS.get(role, role)


def _names(names: Sequence[str]) -> str:
    return "، ".join(escape(name) for name in names) if names else "—"


# ----- عمومی ------------------------------------------------------------------------


def busy(game_name: str) -> str:
    return (
        f"🎮 در این گروه یک بازی ({game_name}) در جریان است.\n"
        "برای شروع بازی تازه، اول بازی فعلی را با «پایان بازی» تمام کنید."
    )


def game_gone() -> str:
    return "⌛ این بازی دیگر فعال نیست. با دستور بازی، بازی تازه‌ای بسازید."


def only_group() -> str:
    return "🎮 این بازی فقط در گروه اجرا می‌شود."


def only_host() -> str:
    return "⛔ فقط سازنده بازی می‌تواند این کار را انجام دهد."


def not_player() -> str:
    return "⛔ شما بازیکن این بازی نیستید."


def finished() -> str:
    return "⌛ این بازی تمام شده است."


def already_joined(name: str) -> str:
    return f"ℹ️ {escape(name)} قبلاً وارد بازی شده است."


def not_joined(name: str) -> str:
    return f"ℹ️ {escape(name)} در این بازی نیست."


def game_full(limit: int) -> str:
    return f"⚠️ ظرفیت بازی کامل است (حداکثر {fa_digits(str(limit))} نفر)."


def need_players(minimum: int) -> str:
    return f"⚠️ برای شروع بازی حداقل {fa_digits(str(minimum))} بازیکن لازم است."


def joined(name: str, count: int) -> str:
    return f"✅ {escape(name)} به بازی اضافه شد. ({fa_digits(str(count))} بازیکن)"


def left(name: str, count: int) -> str:
    return f"👋 {escape(name)} از بازی خارج شد. ({fa_digits(str(count))} بازیکن)"


def stopped() -> str:
    return "🛑 بازی لغو شد. برای شروع دوباره دستور بازی را بفرستید."


def dm_failed(names: Sequence[str]) -> str:
    return (
        "⚠️ بازی شروع نشد: نتوانستم نقش‌ها را در پیام خصوصی بفرستم به "
        f"{_names(names)}.\n"
        "هر بازیکن باید اول ربات را در پیام خصوصی <b>/start</b> کند تا نقش‌ها ارسال شود."
    )


ERROR_TEXTS: dict[str, str] = {
    "finished": "⌛ این بازی تمام شده است.",
    "not_started": "⏳ بازی هنوز شروع نشده است.",
    "not_player": "⛔ شما بازیکن این بازی نیستید.",
    "not_your_turn": "⏳ نوبت شما نیست.",
    "taken": "⚠️ این خانه پر است؛ خانه دیگری انتخاب کنید.",
    "bad_cell": "⚠️ خانه نامعتبر است.",
    "bad_target": "⚠️ انتخاب نامعتبر است.",
    "already_joined": "ℹ️ قبلاً وارد این بازی شده‌اید.",
    "full": "⚠️ ظرفیت بازی کامل است.",
    "need_players": "⚠️ تعداد بازیکنان برای شروع کافی نیست.",
    "started": "🔒 بازی شروع شده و امکان تغییر بازیکنان نیست.",
    "not_voting": "🗳 الان مرحله رأی‌گیری نیست.",
    "self_vote": "⛔ به خودتان نمی‌توانید رأی بدهید.",
    "not_your_role": "⛔ این کار مخصوص نقش شما نیست.",
    "not_spy": "⛔ فقط جاسوس می‌تواند مکان را حدس بزند.",
    "already_guessed": "ℹ️ یک بار بیشتر نمی‌توانید حدس بزنید.",
    "not_night": "🌙 الان شب نیست.",
    "dead": "💀 شما از بازی حذف شده‌اید.",
}


def error_text(kind: str) -> str:
    return ERROR_TEXTS.get(kind, "⚠️ این کار الان ممکن نیست.")


# ----- دوز (XO) ---------------------------------------------------------------------


def xo_invite(challenger: str, opponent: str) -> str:
    return (
        "🎮 <b>دعوت به دوز</b>\n"
        f"{escape(challenger)} از {escape(opponent)} دعوت کرد.\n\n"
        f"❌ شروع با {escape(challenger)} — ⭕ {escape(opponent)}\n"
        "برای شروع، دکمه «قبول» را بزنید."
    )


def xo_started(first: str, second: str, *, vs_bot: bool) -> str:
    second_label = "🤖 ربات" if vs_bot else escape(second)
    return (
        "🎮 <b>دوز شروع شد</b>\n"
        f"❌ {escape(first)} — ⭕ {second_label}\n"
        f"نوبت: {escape(first)}"
    )


def xo_board(*, first: str, second: str, turn: str, winner: str | None, vs_bot: bool) -> str:
    second_label = "🤖 ربات" if vs_bot else escape(second)
    head = f"🎮 <b>دوز</b> — ❌ {escape(first)} | ⭕ {second_label}"
    if winner == "draw":
        return head + "\n\n🤝 بازی مساوی شد."
    if winner:
        name = first if winner == "X" else second
        label = "🤖 ربات" if vs_bot and winner == "O" else escape(name)
        return head + f"\n\n🏆 برنده: {label} {XO_MARKS[winner]}"
    return head + f"\n\nنوبت: {escape(turn)}"


def xo_not_your_turn() -> str:
    return "⏳ نوبت شما نیست."


def xo_cell_taken() -> str:
    return "⚠️ این خانه پر است؛ خانه دیگری انتخاب کنید."


def xo_only_opponent() -> str:
    return "⛔ این دعوت برای شما نیست."


def xo_declined(name: str) -> str:
    return f"❌ {escape(name)} دعوت دوز را رد کرد."


def xo_no_opponent() -> str:
    return "ℹ️ حریف پیدا نشد؛ بازی با ربات شروع می‌شود."


# ----- اسپای (Spyfall) --------------------------------------------------------------


def spy_lobby(host: str, names: Sequence[str], minimum: int, maximum: int) -> str:
    return (
        "🕵️ <b>اسپای (جاسوس)</b>\n"
        "<blockquote>همه یک مکان مشترک را می‌بینند، جز یک نفر که جاسوس است و "
        "باید از سؤال‌ها مکان را حدس بزند.</blockquote>\n"
        f"سازنده: {escape(host)}\n"
        f"بازیکنان ({fa_digits(str(len(names)))}): {_names(names)}\n\n"
        f"حداقل {fa_digits(str(minimum))} و حداکثر {fa_digits(str(maximum))} نفر. "
        "با دکمه «ورود به بازی» اضافه شوید و سازنده «شروع بازی» را بزند."
    )


def spy_started(count: int) -> str:
    return (
        "🕵️ <b>اسپای شروع شد</b>\n"
        f"بازیکنان: {fa_digits(str(count))} نفر\n"
        "نقش هر نفر در پیام خصوصی فرستاده شد. در گروه از هم سؤال بپرسید تا جاسوس "
        "لو برود؛ جاسوس می‌تواند مکان را حدس بزند.\n"
        "برای پایان بحث، سازنده «🗳 رأی‌گیری» را بزند."
    )


def spy_locations(locations: Sequence[str]) -> str:
    lines = "\n".join(f"▫️ {escape(item)}" for item in locations)
    return "<b>مکان‌های ممکن</b>\n" + lines


def spy_role_citizen(location: str) -> str:
    return (
        "🕵️ <b>نقش شما: شهروند</b>\n"
        f"📍 مکان: <b>{escape(location)}</b>\n\n"
        "با سؤال‌های هوشمندانه بفهمید چه کسی مکان را نمی‌داند؛ همان جاسوس است. "
        "مراقب باشید سؤال‌هایتان مکان را لو ندهد."
    )


def spy_role_spy() -> str:
    return (
        "🕵️ <b>نقش شما: جاسوس</b>\n"
        "شما مکان را نمی‌دانید. از پاسخ‌ها و سؤال‌های دیگران حدس بزنید.\n\n"
        "با دکمه‌های زیر می‌توانید مکان را حدس بزنید؛ حدس درست = برد فوری جاسوس، "
        "حدس غلط = برد شهروندان."
    )


def spy_guess_prompt() -> str:
    return "📍 حدس شما از مکان کدام است؟"


def spy_vote_opened() -> str:
    return (
        "🗳 <b>رأی‌گیری اسپای</b>\n"
        "هر بازیکن یک نفر را به‌عنوان جاسوس انتخاب کند. سازنده با «پایان رأی‌گیری» "
        "نتیجه را اعلام می‌کند."
    )


def spy_voted(name: str) -> str:
    return f"🗳 رأی {escape(name)} ثبت شد."


def spy_result_caught(spy: str, location: str) -> str:
    return (
        "🎉 <b>شهروندان بردند!</b>\n"
        f"جاسوس: {escape(spy)}\n"
        f"📍 مکان واقعی: <b>{escape(location)}</b>"
    )


def spy_result_wrong(accused: str, spy: str, location: str) -> str:
    return (
        "🕵️ <b>جاسوس برد!</b>\n"
        f"{escape(accused)} جاسوس نبود.\n"
        f"جاسوس واقعی: {escape(spy)}\n"
        f"📍 مکان واقعی: <b>{escape(location)}</b>"
    )


def spy_tie() -> str:
    return "⚖️ رأی‌ها مساوی شد؛ کسی حذف نشد. بحث کنید و دوباره رأی بدهید."


def spy_guess_correct(spy: str, location: str) -> str:
    return (
        "🕵️ <b>جاسوس برد!</b>\n"
        f"{escape(spy)} مکان را درست حدس زد: <b>{escape(location)}</b>"
    )


def spy_guess_wrong(spy: str, location: str) -> str:
    return (
        "🎉 <b>شهروندان بردند!</b>\n"
        f"{escape(spy)} مکان را اشتباه حدس زد.\n"
        f"📍 مکان واقعی: <b>{escape(location)}</b>"
    )


def spy_reveal(spy: str, location: str) -> str:
    return (
        "🕵️ <b>پایان بازی</b>\n"
        f"جاسوس: {escape(spy)}\n"
        f"📍 مکان: <b>{escape(location)}</b>"
    )


# ----- مافیا ------------------------------------------------------------------------


def mafia_lobby(host: str, names: Sequence[str], minimum: int, maximum: int) -> str:
    return (
        "🎭 <b>مافیا</b>\n"
        "<blockquote>شب مافیا یک نفر را می‌کشد، دکتر نجات می‌دهد و کارآگاه "
        "استعلام می‌گیرد؛ روز با رأی گروه یک نفر حذف می‌شود.</blockquote>\n"
        f"سازنده: {escape(host)}\n"
        f"بازیکنان ({fa_digits(str(len(names)))}): {_names(names)}\n\n"
        f"حداقل {fa_digits(str(minimum))} و حداکثر {fa_digits(str(maximum))} نفر. "
        "با «ورود به بازی» اضافه شوید و سازنده «شروع بازی» را بزند."
    )


def mafia_started(count: int) -> str:
    return (
        "🎭 <b>مافیا شروع شد</b>\n"
        f"بازیکنان: {fa_digits(str(count))} نفر\n"
        "نقش‌ها در پیام خصوصی فرستاده شد. شب شروع می‌شود؛ هر نقش در پیام خصوصی "
        "انتخابش را می‌کند."
    )


def mafia_role_mafia(teammates: Sequence[str]) -> str:
    team = f"\nهم‌تیمی‌های شما: {_names(teammates)}" if teammates else "\nشما تنها مافیا هستید."
    return (
        "🕵️ <b>نقش شما: مافیا</b>\n"
        "هر شب با هم یک نفر را حذف می‌کنید و روز خودتان را شهروند جا می‌زنید."
        f"{team}"
    )


def mafia_role_doctor() -> str:
    return (
        "🩺 <b>نقش شما: دکتر</b>\n"
        "هر شب یک نفر را نجات می‌دهید؛ اگر مافیا همان شب او را انتخاب کند، زنده می‌ماند."
    )


def mafia_role_detective() -> str:
    return (
        "🔍 <b>نقش شما: کارآگاه</b>\n"
        "هر شب هویت یک نفر را استعلام می‌کنید؛ نتیجه فقط به خودتان نشان داده می‌شود."
    )


def mafia_role_citizen() -> str:
    return (
        "👤 <b>نقش شما: شهروند</b>\n"
        "قدرت ویژه‌ای ندارید؛ با بحث و رأی درست مافیا را پیدا کنید."
    )


def mafia_night(number: int) -> str:
    return (
        f"🌙 <b>شب {fa_digits(str(number))}</b>\n"
        "شهر در خواب است. مافیا، دکتر و کارآگاه در پیام خصوصی انتخاب می‌کنند.\n"
        "سازنده اگر همه انتخاب‌ها رسید، خودکار ادامه می‌یابد؛ وگرنه «🌅 پایان شب» را بزند."
    )


def mafia_night_mafia_prompt(names: Sequence[str]) -> str:
    return "🔪 هدف امشب را انتخاب کنید:\n" + _names(names)


def mafia_night_doctor_prompt(names: Sequence[str]) -> str:
    return "🩺 چه کسی را نجات می‌دهید؟\n" + _names(names)


def mafia_night_detective_prompt(names: Sequence[str]) -> str:
    return "🔍 هویت چه کسی را استعلام می‌کنید؟\n" + _names(names)


def mafia_detective_result(name: str, is_mafia: bool) -> str:
    verdict = "🕵️ <b>مافیا است!</b>" if is_mafia else "👤 مافیا نیست."
    return f"🔍 نتیجه استعلام {escape(name)}: {verdict}"


def mafia_day(number: int, killed: str | None, killed_role: str | None, saved: bool) -> str:
    lines = [f"☀️ <b>روز {fa_digits(str(number))}</b>"]
    if killed is None:
        lines.append("🤍 این شب کسی کشته نشد." + (" (دکتر نجات داد)" if saved else ""))
    else:
        lines.append(
            f"💀 {escape(killed)} کشته شد. نقش: {role_label(killed_role or 'citizen')}"
        )
    lines.append("")
    lines.append("درباره شب گذشته بحث کنید؛ سازنده با «🗳 رأی‌گیری» مرحله بعد را باز می‌کند.")
    return "\n".join(lines)


def mafia_vote_opened() -> str:
    return (
        "🗳 <b>رأی‌گیری اخراج</b>\n"
        "هر بازیکن زنده یک نفر را انتخاب کند. سازنده با «پایان رأی‌گیری» نتیجه را اعلام می‌کند."
    )


def mafia_voted(name: str) -> str:
    return f"🗳 رأی {escape(name)} ثبت شد."


def mafia_vote_result(name: str | None, role: str | None) -> str:
    if name is None:
        return "⚖️ رأی‌ها مساوی شد؛ این دور کسی اخراج نشد."
    return f"⚖️ {escape(name)} با بیشترین رأی اخراج شد. نقش: {role_label(role or 'citizen')}"


def mafia_end(winner: str, rows: Sequence[tuple[str, str]]) -> str:
    title = "🕵️ <b>مافیا برد!</b>" if winner == "mafia" else "🎉 <b>شهروندان بردند!</b>"
    reveal = "\n".join(f"▫️ {escape(name)} — {role_label(role)}" for name, role in rows)
    return f"{title}\n\n<b>نقش‌ها</b>\n{reveal}"
