import random

SURVIVE_MESSAGES = [
    "😎 Şans bu sefer senden yana. Kurşun pas geçti.",
    "🍀 Ölüm seni teğet geçti.",
    "🫀 Kalbin hâlâ atıyor, mucize gibi.",
    "🎩 Kader seni bugün sevdi.",
    "🔥 Tetik çekildi ama sen dimdik ayaktasın.",
]

LOSE_MESSAGES = [
    "💥 Boom! Şansın bitti.",
    "☠️ Tambur seni seçti.",
    "🪦 Bugün mezarlıkta yer ayrıldı.",
    "💀 Son mermi seni buldu.",
    "🚪 Kapı dışarı edildin, geçmiş olsun.",
]

SPIN_MESSAGES = [
    "🔫 Tambur çevriliyor...",
    "🎰 Şans hesaplanıyor...",
    "🌀 Mermi yer değiştiriyor...",
    "⚙️ Silah hazırlanıyor...",
    "🫣 Herkes nefesini tuttu...",
]


def spin_chamber(loss_chance: float) -> bool:
    return random.random() >= loss_chance


def random_survive_message():
    return random.choice(SURVIVE_MESSAGES)


def random_lose_message():
    return random.choice(LOSE_MESSAGES)


def random_spin_message():
    return random.choice(SPIN_MESSAGES)
