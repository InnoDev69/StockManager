from ..manager import ConfigManager
from miscellaneous.permissions import PERMS
from miscellaneous.security import encode_text

ConfigManager.register_defaults("roles", {
    "vendedor": {
        PERMS.SALES_CREATE:encode_text("True"),
        PERMS.PRODUCTS_VIEW:encode_text("True"),
        PERMS.SALES_EDIT:encode_text("False"),
        PERMS.SALES_VIEW_ALL:encode_text("False"),
        PERMS.PRODUCTS_MANAGE:encode_text("False"),
        PERMS.BARCODE_MANAGE:encode_text("False"),
        PERMS.USERS_MANAGE:encode_text("False"),
        PERMS.CREDIT_MANAGE:encode_text("False"),
        PERMS.SETTINGS_MANAGE:encode_text("False"),
        PERMS.DEBUG_PANEL:encode_text("False"),
    },
    "admin": {
        PERMS.SALES_CREATE:encode_text("True"),
        PERMS.SALES_EDIT:encode_text("True"),
        PERMS.SALES_VIEW_ALL:encode_text("True"),
        PERMS.PRODUCTS_MANAGE:encode_text("True"),
        PERMS.PRODUCTS_VIEW:encode_text("True"),
        PERMS.BARCODE_MANAGE:encode_text("True"),
        PERMS.USERS_MANAGE:encode_text("True"),
        PERMS.CREDIT_MANAGE:encode_text("True"),
        PERMS.SETTINGS_MANAGE:encode_text("True"),
        PERMS.DEBUG_PANEL:encode_text("True"),
    },
})