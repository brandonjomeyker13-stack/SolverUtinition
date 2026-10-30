from pydantic import BaseModel, EmailStr, Field

from app.schemas.usuario import PerfilOut


class RegistroRequest(BaseModel):
    nombre: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: PerfilOut


class GoogleAuthRequest(BaseModel):
    """`id_token` es el credential que entrega Google Identity Services en el front."""
    id_token: str
