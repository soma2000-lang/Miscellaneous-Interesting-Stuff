# Centralized IAM Service with RBAC and Maker-Checker Pattern

## 1. IAM Core Service

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta

app = FastAPI()
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Database models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    roles = relationship("Role", secondary="user_roles")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    permissions = relationship("Permission", secondary="role_permissions")

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id"), primary_key=True)

# Database setup
engine = create_engine("sqlite:///./iam.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Helper functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, "SECRET_KEY", algorithm="HS256")
    return encoded_jwt

# Authentication endpoints
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# RBAC endpoints
@app.post("/users/")
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(username=user.username, hashed_password=get_password_hash(user.password))
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/roles/")
async def create_role(role: RoleCreate, db: Session = Depends(get_db)):
    db_role = Role(name=role.name)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return db_role

@app.post("/permissions/")
async def create_permission(permission: PermissionCreate, db: Session = Depends(get_db)):
    db_permission = Permission(name=permission.name)
    db.add(db_permission)
    db.commit()
    db.refresh(db_permission)
    return db_permission

@app.post("/assign_role/")
async def assign_role_to_user(user_id: int, role_id: int, db: Session = Depends(get_db)):
    user_role = UserRole(user_id=user_id, role_id=role_id)
    db.add(user_role)
    db.commit()
    return {"message": "Role assigned successfully"}

@app.post("/assign_permission/")
async def assign_permission_to_role(role_id: int, permission_id: int, db: Session = Depends(get_db)):
    role_permission = RolePermission(role_id=role_id, permission_id=permission_id)
    db.add(role_permission)
    db.commit()
    return {"message": "Permission assigned successfully"}

# Maker-Checker Pattern
class PendingAction(Base):
    __tablename__ = "pending_actions"
    id = Column(Integer, primary_key=True, index=True)
    action_type = Column(String, index=True)
    action_data = Column(String)
    maker_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")

@app.post("/create_pending_action/")
async def create_pending_action(action: PendingActionCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_action = PendingAction(**action.dict(), maker_id=current_user.id)
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action

@app.post("/approve_action/{action_id}")
async def approve_action(action_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    action = db.query(PendingAction).filter(PendingAction.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.maker_id == current_user.id:
        raise HTTPException(status_code=400, detail="Maker cannot be the checker")
    
    # Perform the action based on action_type and action_data
    # This is where you'd implement the actual logic for different types of actions
    
    action.status = "approved"
    db.commit()
    return {"message": "Action approved successfully"}

# API Security Middleware
async def check_api_permission(permission: str, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, "SECRET_KEY", algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    user_permissions = set()
    for role in user.roles:
        for perm in role.permissions:
            user_permissions.add(perm.name)
    
    if permission not in user_permissions:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return user

# Example of a protected API endpoint
@app.get("/protected_api")
async def protected_api(current_user: User = Depends(check_api_permission("read_protected"))):
    return {"message": "This is a protected API", "user": current_user.username}

```

## 2. RBAC Testing Framework

```python
import pytest
from fastapi.testclient import TestClient
from main import app, get_db, User, Role, Permission, UserRole, RolePermission

client = TestClient(app)

@pytest.fixture
def test_db():
    # Setup test database
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_create_user(test_db):
    response = client.post("/users/", json={"username": "testuser", "password": "testpass"})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"

def test_create_role(test_db):
    response = client.post("/roles/", json={"name": "admin"})
    assert response.status_code == 200
    assert response.json()["name"] == "admin"

def test_create_permission(test_db):
    response = client.post("/permissions/", json={"name": "read_data"})
    assert response.status_code == 200
    assert response.json()["name"] == "read_data"

def test_assign_role_to_user(test_db):
    user_response = client.post("/users/", json={"username": "testuser", "password": "testpass"})
    role_response = client.post("/roles/", json={"name": "admin"})
    user_id = user_response.json()["id"]
    role_id = role_response.json()["id"]
    
    response = client.post(f"/assign_role/?user_id={user_id}&role_id={role_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Role assigned successfully"

def test_assign_permission_to_role(test_db):
    role_response = client.post("/roles/", json={"name": "admin"})
    perm_response = client.post("/permissions/", json={"name": "read_data"})
    role_id = role_response.json()["id"]
    perm_id = perm_response.json()["id"]
    
    response = client.post(f"/assign_permission/?role_id={role_id}&permission_id={perm_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Permission assigned successfully"

def test_protected_api_access(test_db):
    # Create user, role, and permission
    user_response = client.post("/users/", json={"username": "testuser", "password": "testpass"})
    role_response = client.post("/roles/", json={"name": "admin"})
    perm_response = client.post("/permissions/", json={"name": "read_protected"})
    
    user_id = user_response.json()["id"]
    role_id = role_response.json()["id"]
    perm_id = perm_response.json()["id"]
    
    # Assign role to user and permission to role
    client.post(f"/assign_role/?user_id={user_id}&role_id={role_id}")
    client.post(f"/assign_permission/?role_id={role_id}&permission_id={perm_id}")
    
    # Login to get token
    login_response = client.post("/token", data={"username": "testuser", "password": "testpass"})
    token = login_response.json()["access_token"]
    
    # Access protected API
    response = client.get("/protected_api", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["message"] == "This is a protected API"
    assert response.json()["user"] == "testuser"

def test_maker_checker_pattern(test_db):
    # Create two users: maker and checker
    maker = client.post("/users/", json={"username": "maker", "password": "makerpass"})
    checker = client.post("/users/", json={"username": "checker", "password": "checkerpass"})
    
    # Login as maker
    maker_login = client.post("/token", data={"username": "maker", "password": "makerpass"})
    maker_token = maker_login.json()["access_token"]
    
    # Create a pending action
    pending_action = client.post("/create_pending_action/", 
                                 json={"action_type": "create_user", "action_data": '{"username": "newuser", "password": "newpass"}'},
                                 headers={"Authorization": f"Bearer {maker_token}"})
    action_id = pending_action.json()["id"]
    
    # Login as checker
  