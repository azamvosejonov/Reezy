from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize database models
from database import init_models
init_models()

from routers import accounts, posts, notifications, messages, stories, groups, auth, advertisements, relationships, group_messages, channels, blocks, livestreams, ai, calls, stickers
from routers.ai_router import router as ai_router
from routers.social_auth import router as social_auth_router
from api import router as api_router
from startup import create_tables

# Create FastAPI app
app = FastAPI(
    title="Growstems API",
    description="Barcha zamonaviy ijtimoiy tarmoq funksiyalari uchun API.",
    version="1.0.0",
    docs_url=None,  # We'll serve custom Swagger UI
    redoc_url=None,  # We'll serve custom ReDoc
    openapi_url="/openapi.json",
    swagger_ui_oauth2_redirect_url="/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": "swagger-ui",
    },
)

# Security scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scheme_name="OAuth2PasswordBearer",
    auto_error=False
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    # First get the base schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Ensure openapi version is set
    openapi_schema["openapi"] = "3.0.2"
    
    # Ensure components exist
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter JWT token (get it from /token endpoint)"
        },
        "OAuth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "/auth/google",
                    "tokenUrl": "/auth/callback/google",
                    "scopes": {
                        "openid": "OpenID Connect",
                        "profile": "User profile",
                        "email": "User email"
                    }
                }
            }
        },
        "GoogleOAuth2": {
            "type": "oauth2",
            "flows": {
                "implicit": {
                    "authorizationUrl": "/auth/google",
                    "scopes": {
                        "openid": "OpenID Connect",
                        "profile": "User profile",
                        "email": "User email"
                    }
                }
            }
        }
    }
    
    # Add security to all endpoints except login and register
    for path, path_item in openapi_schema.get("paths", {}).items():
        # Skip static files
        if path.startswith("/static"):
            continue
            
        for method_name, method in path_item.items():
            # Skip non-HTTP methods
            if method_name.lower() not in ["get", "post", "put", "delete", "patch", "head", "options"]:
                continue
                
            # Add security to all methods except login and register
            if path not in ["/token", "/register"]:
                method["security"] = [{"OAuth2PasswordBearer": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Set the custom OpenAPI schema
app.openapi = custom_openapi

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
        swagger_ui_parameters={
            "oauth2RedirectUrl": "/oauth2-redirect",
            "persistAuthorization": True,
            "syntaxHighlight.theme": "obsidian",
            "operationsSorter": "method",
            "showCommonExtensions": True,
            "showExtensions": True,
            "displayOperationId": True,
            "oauth2RedirectUrl": "/oauth2-redirect",
            "initOAuth": {
                "clientId": "swagger-ui",
                "appName": "Reezy API",
                "usePkceWithAuthorizationCodeGrant": True,
                "scopes": "openid profile email"
            },
            "security": [
                {
                    "OAuth2": [
                        "openid",
                        "profile",
                        "email"
                    ]
                }
            ]
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

create_tables()

# Include routers
# Include the versioned API router first to take precedence
app.include_router(api_router, prefix="/api")

# Include legacy routers
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(posts.router, prefix="/posts", tags=["posts"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(stories.router, prefix="/stories", tags=["stories"])
app.include_router(groups.router, prefix="/groups", tags=["groups"])
app.include_router(auth.router)
app.include_router(group_messages.router, tags=["group_messages"])
app.include_router(channels.router, tags=["channels"])
app.include_router(advertisements.router)
app.include_router(relationships.router)
app.include_router(blocks.router)
app.include_router(livestreams.router)
app.include_router(ai.router)
app.include_router(calls.router)
app.include_router(ai_router)
app.include_router(social_auth_router, prefix="/api/v1", tags=["Social Authentication"])
app.include_router(stickers.router, prefix="/api/v1", tags=["Stickers"])

@app.get("/", summary="Root endpoint", description="API ishlayotganini tekshirish uchun oddiy endpoint.")
def root():
    return {"message": "Welcome to Reezy API. Use /docs for Swagger UI or /auth-test for authentication testing."}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "message": "Service is running"}
    )

@app.get("/auth-test", include_in_schema=False)
async def auth_test():
    return FileResponse("static/auth_test.html")
