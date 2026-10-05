class SkuNoExisteEnRocketfyError(Exception):
    """El SKU que se quiere monitorear no aparece en el catálogo de
    Rocketfy — probablemente un error de tipeo. Se valida al agregar para
    no vigilar en silencio un SKU que nunca va a disparar nada."""
