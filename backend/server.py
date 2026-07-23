import os
import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

import fanar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

CONTENT_PATH = os.path.join(os.path.dirname(__file__), "content.json")

def load_content() -> dict:
    with open(CONTENT_PATH, encoding="utf-8") as f:
        return json.load(f)

def find_task(content: dict, grade: str, semester: str, task_id: str) -> dict:
    try:
        tasks = content["grades"][grade]["semesters"][semester]["tasks"]
    except KeyError:
        raise HTTPException(status_code=404, detail="الصف أو الفصل غير موجود")
    for t in tasks:
        if t["id"] == task_id:
            return t
    raise HTTPException(status_code=404, detail="المهمة غير موجودة")

class EvaluationRequest(BaseModel):
    grade: str = Field(..., description="e.g. '7'")
    semester: str = Field(..., description="e.g. '1'")
    task_id: str = Field(..., description="task id from content.json")
    student_text: str = Field(..., min_length=1, description="Student's essay text")

app = FastAPI(
    title="Essay Evaluation API",
    description="Serves the content tree and evaluates essays with Fanar",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/content")
async def get_content():
    return load_content()

@app.post("/evaluate")
async def evaluate(request_data: EvaluationRequest):
    logger.info(f"Received evaluation request | grade={request_data.grade} semester={request_data.semester} task_id={request_data.task_id}")
    content = load_content()
    try:
        task = find_task(content, request_data.grade, request_data.semester, request_data.task_id)
        logger.info(f"Found task: {task.get('title')}")
    except HTTPException as e:
        logger.error(f"Task lookup failed: {e.detail}")
        raise

    try:
        result = fanar.evaluate_essay(task, request_data.student_text)
        logger.info("Evaluation completed successfully.")
        return result
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)