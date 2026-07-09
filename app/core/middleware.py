from fastapi import Depends,HTTPException 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt,JWTError
from app.core.config import config


security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM],options={"verify_aud": False})
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")