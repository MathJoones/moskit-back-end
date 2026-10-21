import argparse
import sys
import uuid

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User


def create_admin(email: str, full_name: str, password: str) -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"[ERRO] Usuário '{email}' já existe.")
            sys.exit(1)

        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role="admin",
            status="active",
        )
        db.add(user)
        db.commit()
        print(f"[OK] Admin criado: {email}")
        print(f"     ID: {user.id}")
    except Exception as e:
        db.rollback()
        print(f"[ERRO] {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cria usuário admin inicial")
    parser.add_argument("--email",    default="admin@moskit.com")
    parser.add_argument("--name",     default="Administrador")
    parser.add_argument("--password", default="Admin@12345")
    args = parser.parse_args()

    print(f"Criando admin: {args.email}")
    create_admin(args.email, args.name, args.password)
