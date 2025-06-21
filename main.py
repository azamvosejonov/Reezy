from fastapi import FastAPI, Request, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.routing import APIRoute, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, OAuth2
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from fastapi.openapi.models import OAuthFlow as OAuthFlowModel, OAuthFlows as OAuthFlowsModel
from typing import Optional, List, Dict, Any, Union, Callable
import os
from dotenv import load_dotenv
from requests import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session as DBSession

from models import User

# Load environment variables
load_dotenv()

# Initialize database models
from database import init_models, get_db

# JWT Configuration
SECRET_KEY = "supersecret"  # Move to environment variable in production
ALGORITHM = "HS256"

init_models()

# Security
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DBSession = Depends(get_db)
):
    """
    Get the current authenticated user from the JWT token.
    
    Args:
        credentials: HTTP Authorization credentials containing the token
        db: Database session
        
    Returns:
        User: The authenticated user
        
    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
        
    # Check if token matches the user's current token
    if user.current_token != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

# Custom router class to require auth for POST methods
class AuthRouter(APIRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def add_api_route(self, path: str, endpoint: Callable, **kwargs):
        # Add auth dependency for all HTTP methods (GET, POST, DELETE)
        if kwargs.get('methods') is None or any(method in kwargs['methods'] for method in ['GET', 'POST', 'DELETE']):
            if 'dependencies' not in kwargs:
                kwargs['dependencies'] = []
            kwargs['dependencies'].append(Depends(get_current_user))
        return super().add_api_route(path, endpoint, **kwargs)

# Routers
from routers import auth, accounts, posts, notifications, messages, stories, groups, advertisements, relationships, group_messages, channels, blocks, livestreams, ai, calls, stickers, post_actions
from routers.ai_router import router as ai_router
from routers.social_auth import router as social_auth_router
from api import router as api_router
from startup import create_tables

# Create FastAPI app with OAuth2 configuration
app = FastAPI(router_class=AuthRouter,
    title="Growstems API",
    description="Barcha zamonaviy ijtimoiy tarmoq funksiyalari uchun API.",
    version="1.0.0",
    openapi_version="3.0.3",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": "swagger-ui",
        "scopes": ["api"],
        "appName": "Growstems API",
        "useBasicAuthenticationWithAccessCodeGrant": True,
    },
    openapi_tags=[
        {"name": "Authentication", "description": "Login va register endpointlari"},
        {"name": "User Management", "description": "Foydalanuvchi boshqaruvi"},
        {"name": "Post Management", "description": "Postlar bilan ishlash"},
        {"name": "Notifications", "description": "Xabarlar va bildirishnomalar"},
        {"name": "Messages", "description": "Xabarlar bilan ishlash"},
        {"name": "Stories", "description": "Stories bilan ishlash"},
        {"name": "Groups", "description": "Guruhlarga kirish va chiqish"},
        {"name": "Advertisements", "description": "Reklamalar bilan ishlash"},
        {"name": "Relationships", "description": "Muloqotlar bilan ishlash"},
        {"name": "Group Messages", "description": "Guruh xabarlar"},
        {"name": "Channels", "description": "Kanallar bilan ishlash"},
        {"name": "Blocks", "description": "Foydalanuvchilarni bloklash"},
        {"name": "Livestreams", "description": "Direkt yordamchi"},
        {"name": "AI Services", "description": "AI xizmatlari"},
        {"name": "Social Auth", "description": "Tashqi tizimlar orqali login"},
        {"name": "Calls", "description": "Qo'ng'iroqlar"},
        {"name": "Stickers", "description": "Stikerlar"},
        {"name": "Post Actions", "description": "Postlarga reaksiya"}
    ]
)

# Security scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token",
    scheme_name="OAuth2PasswordBearer",
    auto_error=False,
    scopes={
        "api": "Access to the API"
    }
)

# Add security requirements to all endpoints except auth endpoints
def add_security_requirements(openapi_schema):
    for path, path_item in openapi_schema.get("paths", {}).items():
        # Skip auth endpoints and static files
        if path.startswith("/auth") or path.startswith("/static"):
            continue

        for method_name, method in path_item.items():
            if method_name.lower() in ["get", "post", "put", "delete", "patch", "head", "options"]:
                method["security"] = [{"OAuth2PasswordBearer": []}]

    return openapi_schema

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    # Filter out default routes
    routes = [
        route for route in app.routes 
        if not (isinstance(route, APIRoute) and route.path in ['/', '/health', '/auth/test'])
    ]
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=routes,
        openapi_version="3.0.3"
    )
    
    # Set the OpenAPI version explicitly
    openapi_schema["openapi"] = "3.0.3"
    
    # Ensure components exist
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "schemas" not in openapi_schema["components"]:
        openapi_schema["components"]["schemas"] = {}
    
    # Add TokenResponse schema if not exists
    if "TokenResponse" not in openapi_schema["components"]["schemas"]:
        openapi_schema["components"]["schemas"]["TokenResponse"] = {
            "type": "object",
            "properties": {
                "access_token": {"type": "string"},
                "token_type": {"type": "string", "default": "bearer"},
                "scope": {"type": "string", "default": "api"},
                "success": {"type": "boolean", "default": True},
                "message": {"type": "string"},
                "user": {
                    "$ref": "#/components/schemas/UserInfo"
                }
            },
            "required": ["access_token", "user", "message"]
        }
    
    # Add UserInfo schema if not exists
    if "UserInfo" not in openapi_schema["components"]["schemas"]:
        openapi_schema["components"]["schemas"]["UserInfo"] = {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "format": "int64"},
                "username": {"type": "string"},
                "email": {"type": "string", "format": "email"}
            },
            "required": ["id", "username", "email"]
        }
    
    # Add security schemes
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}
        
    # Add OAuth2 security scheme
    openapi_schema["components"]["securitySchemes"]["OAuth2PasswordBearer"] = {
        "type": "oauth2",
        "description": "OAuth2 with password flow and JWT tokens",
        "flows": {
            "password": {
                "tokenUrl": "/api/v1/auth/token",
                "scopes": {
                    "api": "Access to the API"
                }
            }
        },
        "description": "OAuth2 password flow with JWT tokens"
    }

    # Add common schemas
    openapi_schema["components"]["schemas"]["ValidationError"] = {
        "title": "ValidationError",
        "type": "object",
        "properties": {
            "loc": {
                "title": "Location",
                "type": "array",
                "items": {
                    "title": "Location",
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "msg": {
                    "title": "Message",
                    "type": "string"
                },
                "type": {
                    "title": "Error Type",
                    "type": "string"
                }
            }
        },
        "HTTPValidationError": {
            "title": "HTTPValidationError",
            "type": "object",
            "properties": {
                "detail": {
                    "title": "Detail",
                    "type": "array",
                    "items": {
                        "$ref": "#/components/schemas/ValidationError"
                    }
                }
            }
        },
        "PublicUserResponse": {
            "title": "PublicUserResponse",
            "type": "object",
            "properties": {
                "id": {
                    "title": "Id",
                    "type": "integer"
                },
                "username": {
                    "title": "Username",
                    "type": "string"
                },
                "full_name": {
                    "title": "Full Name",
                    "type": "string"
                },
                "bio": {
                    "title": "Bio",
                    "type": "string"
                },
                "profile_picture": {
                    "title": "Profile Picture",
                    "type": "string"
                },
                "is_private": {
                    "title": "Is Private",
                    "type": "boolean"
                },
                "is_verified": {
                    "title": "Is Verified",
                    "type": "boolean"
                },
                "created_at": {
                    "title": "Created At",
                    "type": "string",
                    "format": "date-time"
                }
            },
            "required": ["id", "username", "created_at", "is_verified"]
        }
    }

    # Add security requirements to all endpoints that need authentication
    for route in app.routes:
        if isinstance(route, APIRoute):
            if route.operation_id and "auth" not in route.operation_id.lower():
                # Add security to operation if it doesn't have it already
                if hasattr(route, 'endpoint') and hasattr(route.endpoint, '__annotations__'):
                    if 'security' not in route.endpoint.__annotations__:
                        route.endpoint.__annotations__['security'] = [{"OAuth2PasswordBearer": ["api"]}]

    # Add security to all paths in the OpenAPI schema
    if "paths" in openapi_schema:
        for path_item in openapi_schema["paths"].values():
            for operation in path_item.values():
                if isinstance(operation, dict) and "security" not in operation:
                    # Skip auth endpoints
                    if any(auth_path in operation.get('tags', []) for auth_path in ["Authentication"]):
                        continue
                    operation["security"] = [{"OAuth2PasswordBearer": ["api"]}]

    # Add security requirements to endpoints
    openapi_schema = add_security_requirements(openapi_schema)

    app.openapi_schema = openapi_schema
    return openapi_schema

app.openapi = custom_openapi

# Serve static files for media uploads
app.mount("/media", StaticFiles(directory="media"), name="media")

# Serve static files for Swagger UI
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

# Custom Swagger UI
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        swagger_favicon_url="/static/favicon.png",
        init_oauth={
            "usePkceWithAuthorizationCodeGrant": True,
            "clientId": "swagger-ui",
            "scopes": ["api"],
            "appName": "Growstems API",
            "useBasicAuthenticationWithAccessCodeGrant": True,
        },
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "filter": True,
            "displayRequestDuration": True,
            "persistAuthorization": True,
            "withCredentials": True,
            "requestSnippetsEnabled": True,
            "showCommonExtensions": True,
            "showExtensions": True,
            "deepLinking": True,
            "defaultModelExpandDepth": 10,
            "defaultModelRendering": "example",
            "defaultModelExpandDepth": 5,
            "defaultModelsExpandDepth": 1,
            "displayOperationId": False,
            "showMutatedRequest": True,
            "showRequestDuration": True,
            "showUrl": True,
            "tryItOutEnabled": True,
            "validatorUrl": None,
            "oauth2RedirectUrl": "/docs/oauth2-redirect",
        },
    )

# Custom ReDoc
@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Reezy API - ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
        with_google_fonts=False,
    )

# Add CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],

)

create_tables()

# Include routers
# Include the versioned API router first to take precedence
app.include_router(api_router, prefix="/api")

# Include legacy routers
# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(accounts.router, prefix="/users", tags=["User Management"])
app.include_router(posts.router, prefix="/posts", tags=["Post Management"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(messages.router, prefix="/messages", tags=["Messages"])
app.include_router(stories.router, prefix="/stories", tags=["Stories"])
app.include_router(groups.router, prefix="/groups", tags=["Groups"])
app.include_router(advertisements.router, prefix="/ads", tags=["Advertisements"])
app.include_router(relationships.router, prefix="/relationships", tags=["Relationships"])
app.include_router(group_messages.router, prefix="/group-messages", tags=["Group Messages"])
app.include_router(channels.router, prefix="/channels", tags=["Channels"])
app.include_router(blocks.router, prefix="/blocks", tags=["Blocks"])
app.include_router(livestreams.router, prefix="/livestreams", tags=["Livestreams"])
app.include_router(ai_router, prefix="/ai", tags=["AI Services"])
app.include_router(social_auth_router, prefix="/social-auth", tags=["Social Auth"])
app.include_router(calls.router, prefix="/calls", tags=["Calls"])
app.include_router(stickers.router, prefix="/stickers", tags=["Stickers"])
app.include_router(post_actions.router, prefix="/posts", tags=["Post Actions"])

# OAuth2 token endpoint for Swagger UI
@app.post("/api/v1/auth/token", response_model=dict, tags=["Authentication"])
async def token_endpoint(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Get OAuth2 access token"""
    return await auth.login_for_access_token(form_data, db)

@app.get("/", summary="Root endpoint", description="API ishlayotganini tekshirish uchun oddiy endpoint.")
def root():
    return {"message": "Welcome to Reezy API. Use /docs for Swagger UI or /auth-test for authentication testing."}

@app.get("/health")
async def health_check():

    return JSONResponse(
        status_code=200,
        content={"status": "ok", "message": "Service is running"}
    )

@app.get("/auth-test", include_in_schema=False)
async def auth_test():
    return FileResponse("static/auth_test.html")
