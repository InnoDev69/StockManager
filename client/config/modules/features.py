from ..manager import ConfigManager

ConfigManager.register_defaults("features", {
    "RECALCULATE_CREDIT_ON_SALE_EDIT": False,
    })

# RECALCULATE_CREDIT_ON_SALE_EDIT: Si RECALCULATE_CREDIT_ON_SALE_EDIT es False (default),
# no se toca account_movements: el pendiente fiado original
# queda fijo aunque los productos/precios hayan cambiado.