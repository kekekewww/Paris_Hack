"""Bounded read-only routes over the verified official document catalog."""
from fastapi import APIRouter, Path, Query

router = APIRouter(prefix="/api/v1")


@router.get("/library")
def library(query: str = Query(default="", max_length=200),
            category: str = Query(default="all", max_length=80)):
    from .library import get_library

    return get_library(query=query, category=category)


@router.get("/faq")
def faq():
    from .library import get_faq

    return get_faq()


@router.get("/products/{code}")
def product(code: str = Path(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")):
    from .library import lookup_product

    return lookup_product(code)
