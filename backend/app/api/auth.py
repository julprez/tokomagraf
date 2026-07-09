# =============================================================
# api/auth.py — Endpoints de autenticación
# =============================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.models import User
from app.schemas.schemas import UserCreate, UserLogin, Token, UserOut, UserUpdate, SeedPhraseLogin, SeedPhraseResponse
from app.auth.auth import hash_password, verify_password, create_access_token, get_current_user
from app.auth.seeds import generate_seed_phrase, hash_seed_phrase, verify_seed_phrase, validate_words

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email ya registrado")

    user = User(
        name=data.name,
        email=data.email,
        password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/generate-seed", response_model=SeedPhraseResponse)
async def generate_seed(db: AsyncSession = Depends(get_db)):
    """Genera una seed phrase de 6 palabras y crea una cuenta nueva."""
    words = generate_seed_phrase()
    hashed = hash_seed_phrase(words)

    user = User(
        name="Usuario",
        seed_phrase_hash=hashed,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return SeedPhraseResponse(
        words=words,
        access_token=token,
        is_new=True,
    )


@router.post("/login-seed", response_model=SeedPhraseResponse)
async def login_seed(data: SeedPhraseLogin, db: AsyncSession = Depends(get_db)):
    """Inicia sesión con seed phrase de 6 palabras."""
    # Validar palabras
    err = validate_words(data.words)
    if err:
        raise HTTPException(status_code=400, detail=err)

    # Buscar usuario por seed phrase
    result = await db.execute(select(User).where(User.seed_phrase_hash.isnot(None)))
    users = result.scalars().all()

    user = None
    for u in users:
        if u.seed_phrase_hash and verify_seed_phrase(data.words, u.seed_phrase_hash):
            user = u
            break

    if not user:
        raise HTTPException(status_code=401, detail="Seed phrase inválida")

    token = create_access_token({"sub": str(user.id)})
    return SeedPhraseResponse(
        words=data.words,
        access_token=token,
        is_new=False,
    )


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.put("/me", response_model=UserOut)
async def update_profile(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza perfil y/o contraseña."""
    if data.name:
        user.name = data.name

    if data.current_password and data.new_password:
        if not user.password:
            raise HTTPException(status_code=400, detail="Esta cuenta no tiene contraseña (usa seed phrase)")
        if not verify_password(data.current_password, user.password):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        user.password = hash_password(data.new_password)

    await db.commit()
    await db.refresh(user)
    return user
