from pydantic import BaseModel, EmailStr, model_validator


class LoginRequest(BaseModel):
    """Accepts either email+password (office) or username+pin (production)."""

    email: EmailStr | None = None
    password: str | None = None
    username: str | None = None
    pin: str | None = None

    @model_validator(mode="after")
    def validate_login_mode(self):
        has_email = bool(self.email)
        has_username = bool(self.username)
        if has_email and has_username:
            raise ValueError("Provide either email+password or username+pin, not both")
        if not has_email and not has_username:
            raise ValueError("Provide either email+password or username+pin")
        if has_email and not self.password:
            raise ValueError("Password is required for email login")
        if has_username and not self.pin:
            raise ValueError("PIN is required for username login")
        return self


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
