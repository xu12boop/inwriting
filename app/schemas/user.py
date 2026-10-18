from pydantic import BaseModel

# 注册和登录时前端传过来的格式
class UserCreate(BaseModel):
    username: str
    password: str

# 登录成功后返回的 Token 格式
class Token(BaseModel):
    access_token: str
    token_type: str

# 返回给前端的用户信息（不包含密码）
class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True