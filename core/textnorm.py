"""نرمال‌سازی متن و ارقام فارسی.

تلگرام متن را همان‌طور که کاربر تایپ کرده می‌فرستد؛ کاربر ایرانی ممکن است ارقام
فارسی/عربی یا حروف عربی (ي، ك) به کار ببرد. قبل از هر مقایسه یا تجزیه‌ای، متن را
از این‌جا عبور می‌دهیم تا «۱۰ دقیقه» و «10 دقیقه» یکی باشند.
"""

from __future__ import annotations

_ASCII_DIGITS = "0123456789"
_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def _zip_map(source: str, target: str) -> dict[str, str]:
    return {src: dst for src, dst in zip(source, target)}


_TO_ASCII = str.maketrans(
    {**_zip_map(_FA_DIGITS, _ASCII_DIGITS), **_zip_map(_AR_DIGITS, _ASCII_DIGITS)}
)
_TO_FA = str.maketrans(_zip_map(_ASCII_DIGITS, _FA_DIGITS))

# حروف عربی → فارسی، حذف کشیده و کاراکترهای جهت‌دهی.
_CHAR_MAP = str.maketrans(
    {
        "ي": "ی",
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "أ": "ا",
        "إ": "ا",
        "ـ": None,
        "\u200c": " ",  # نیم‌فاصله
        "\u200e": None,  # LRM
        "\u200f": None,  # RLM
    }
)


def en_digits(text: str) -> str:
    """ارقام فارسی/عربی را به لاتین تبدیل می‌کند («۱۲» ← «12»)."""
    return text.translate(_TO_ASCII)


def fa_digits(text: str) -> str:
    """ارقام لاتین را به فارسی تبدیل می‌کند («12» ← «۱۲»)."""
    return text.translate(_TO_FA)


def normalize(text: str) -> str:
    """حروف عربی را فارسی می‌کند و فاصله‌های اضافی/نیم‌فاصله را یکسان می‌سازد."""
    return " ".join(text.translate(_CHAR_MAP).split())
