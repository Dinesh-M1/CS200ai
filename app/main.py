from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import Base, engine
# Import ALL four routers now
from app.routers import browse, selection, ingest, generation  

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CT200 Document Intelligence System API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register ALL of them
app.include_router(ingest.router, prefix="/api", tags=["Ingest"])
app.include_router(browse.router, prefix="/api", tags=["Browse"])
app.include_router(selection.router, prefix="/api", tags=["Selection"])
app.include_router(generation.router, prefix="/api", tags=["Generation"])

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "healthy"}