import enum

from client.config import config
from miscellaneous import ROLES
from miscellaneous.permissions import PERMS

class PermissionsService:
    @staticmethod
    def get_permissions(role: str) -> set:
        if role == ROLES.ROOT:
            return {"*"}  # root siempre tiene todo, no depende de config
            
        # Extraemos todos los valores reales de la clase PERMS en una lista
        todas_las_perms = [valor for nombre, valor in vars(PERMS).items() if not nombre.startswith("__")]

        for perm in todas_las_perms:
            # Si el permiso no está definido en la config, lo agregamos con valor False
            entry = config.get(f"roles.{role}.{perm}", default=None)
            if entry is None:
                config.set(f"roles.{role}.{perm}", False)
                
        return {perm for perm in todas_las_perms if config.get(f"roles.{role}.{perm}", default=False)}

    @staticmethod
    def has_permission(role: str, permission: str) -> bool:
        perms = PermissionsService.get_permissions(role)
        return "*" in perms or permission in perms

has_permission = PermissionsService.has_permission