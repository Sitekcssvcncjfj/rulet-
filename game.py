import random

def spin_chamber(loss_chance: float) -> bool:
    """
    True = hayatta kaldı
    False = kaybetti
    """
    return random.random() >= loss_chance
