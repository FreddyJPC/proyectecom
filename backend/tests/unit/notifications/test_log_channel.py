from src.notifications import LoggingNotificationChannel, NotificationMessage, NotificationService


def test_log_channel_devuelve_true_y_no_lanza():
    canal = LoggingNotificationChannel()
    mensaje = NotificationMessage(to="0991234567", template_name="rocketfy_en_ruta")
    assert canal.send(mensaje) is True


def test_service_delega_al_canal():
    canal = LoggingNotificationChannel()
    servicio = NotificationService(canal)
    assert servicio.send(NotificationMessage(to="0991234567")) is True
