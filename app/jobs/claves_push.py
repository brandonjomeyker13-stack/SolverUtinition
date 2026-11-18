"""Genera el par de claves VAPID una sola vez: `python -m app.jobs.claves_push`.

La pública va en VAPID_PUBLIC_KEY y la privada en VAPID_PRIVATE_KEY (Render y GitHub).
Si cambias el par, todas las suscripciones existentes dejan de servir.
"""
from base64 import urlsafe_b64encode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(datos: bytes) -> str:
    return urlsafe_b64encode(datos).rstrip(b"=").decode()


def main() -> None:
    privada = ec.generate_private_key(ec.SECP256R1())
    publica = privada.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print("VAPID_PUBLIC_KEY=" + _b64(publica))
    print("VAPID_PRIVATE_KEY=" + _b64(privada.private_numbers().private_value.to_bytes(32, "big")))


if __name__ == "__main__":
    main()
