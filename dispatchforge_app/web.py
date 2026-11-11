"""Public site, authentication pages, and warehouse dashboard."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware
from .api import router as api_router
from .auth import (actor_from_session, authenticate, check_csrf, csrf_token,
                   register_business)
from .database import Database
from .demo import seed_demo
from .errors import DomainError
from .models import Business
from .settings import Settings, load_settings

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))


def create_app(db: Database | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    db = db or Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        seed_demo(db)
        yield

    app = FastAPI(title="DispatchForge Warehouse Cloud", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    app.add_middleware(SessionMiddleware, secret_key=settings.secret,
                       same_site="lax", https_only=settings.production,
                       max_age=60 * 60 * 8)
    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    app.include_router(api_router)

    @app.middleware("http")
    async def set_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.exception_handler(DomainError)
    async def on_domain_error(request: Request, error: DomainError):
        return JSONResponse({"error": error.message}, status_code=error.status)

    def render(request, template, **context):
        return TEMPLATES.TemplateResponse(request, template, {"csrf": csrf_token(request), **context})

    @app.get("/", response_class=HTMLResponse)
    def landing(request: Request):
        return render(request, "landing.html", title="DispatchForge | Warehouse Cloud")

    @app.get("/demo", response_class=HTMLResponse)
    def demo(request: Request):
        return render(request, "dashboard.html", title="Sample Warehouse | DispatchForge",
                      is_demo=True, workspace="Denton Sample Distribution")

    @app.get("/register", response_class=HTMLResponse)
    def registration(request: Request):
        return render(request, "auth.html", title="Create Workspace | DispatchForge",
                      mode="register", error=None)

    @app.post("/register")
    async def create_account(request: Request):
        form = await request.form()
        try:
            check_csrf(request, str(form.get("csrf", "")))
            with db.SessionLocal() as session:
                business, user = register_business(session, str(form.get("business_name", "")),
                                                   str(form.get("email", "")), str(form.get("password", "")))
                session.commit()
                request.session.clear()
                request.session["uid"] = user.id
                request.session["bid"] = business.id
                csrf_token(request)
            return RedirectResponse("/app", status_code=303)
        except DomainError as exc:
            return TEMPLATES.TemplateResponse(request, "auth.html",
                       {"title": "Create Workspace", "csrf": csrf_token(request),
                        "mode": "register", "error": exc.message}, status_code=exc.status)

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return render(request, "auth.html", title="Sign In | DispatchForge",
                      mode="login", error=None)

    @app.post("/login")
    async def login(request: Request):
        form = await request.form()
        try:
            check_csrf(request, str(form.get("csrf", "")))
        except DomainError as exc:
            return TEMPLATES.TemplateResponse(request, "auth.html",
                       {"title": "Sign In", "csrf": csrf_token(request),
                        "mode": "login", "error": exc.message}, status_code=403)
        with db.SessionLocal() as session:
            user = authenticate(session, str(form.get("workspace", "")),
                                str(form.get("email", "")), str(form.get("password", "")))
        if user is None:
            return TEMPLATES.TemplateResponse(request, "auth.html",
                       {"title": "Sign In", "csrf": csrf_token(request),
                        "mode": "login", "error": "Workspace, email, or password is incorrect"},
                       status_code=401)
        request.session.clear()
        request.session["uid"] = user.id
        request.session["bid"] = user.business_id
        csrf_token(request)
        return RedirectResponse("/app", status_code=303)

    @app.get("/app", response_class=HTMLResponse)
    def workspace(request: Request):
        with db.SessionLocal() as session:
            user = actor_from_session(session, request.session)
            if user is None:
                return RedirectResponse("/login", status_code=303)
            business = session.scalar(select(Business).where(Business.id == user.business_id))
            return render(request, "dashboard.html", title=f"{business.name} | DispatchForge",
                          is_demo=False, workspace=business.name, slug=business.slug,
                          role=user.role)

    @app.post("/logout")
    async def logout(request: Request):
        form = await request.form()
        check_csrf(request, str(form.get("csrf", "")))
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    return app


app = create_app()
