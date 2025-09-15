from fastapi import FastAPI

from .routes.recommend import router as recommend_router

app = FastAPI(title="HireBike Recommender (TfL MVP)")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(recommend_router)
