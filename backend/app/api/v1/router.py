from fastapi import APIRouter
from app.api.v1.endpoints import auth, jobs, review, publish, library, brand, health

api_router = APIRouter()

# Health (no prefix)
api_router.include_router(health.router, tags=["Health"])

# Auth
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# Jobs (AI generation)
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])

# Review (approve/regenerate)
api_router.include_router(review.router, prefix="/review", tags=["Review"])

# Publish (Buffer)
api_router.include_router(publish.router, prefix="/publish", tags=["Publish"])

# Image Library
api_router.include_router(library.router, prefix="/library", tags=["Library"])

# Brand Kit
api_router.include_router(brand.router, prefix="/brand", tags=["Brand"])