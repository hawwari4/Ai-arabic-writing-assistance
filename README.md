<div align="center">

# ✍️ مساعد التعبير الكتابي
### Arabic Essay Writing Assistant

A friendly AI writing coach for middle school students learning Arabic.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-Frontend-F7DF1E?logo=javascript&logoColor=black)
![Fanar](https://img.shields.io/badge/AI-Fanar%20API-1F6F6B)

</div>

---

## About

This is a web app that helps students in grades 7–9 practice writing Arabic
essays. A student picks their grade, semester, and a writing task, then writes
their essay right in the browser.

Once they submit it, an AI model reads the essay and gives real feedback: a
score for each rubric criterion, spelling and grammar corrections, tips on
stronger word choices, and even a small improved version of one of their
paragraphs. It's meant to feel like having a patient Arabic teacher on call,
available any time a student wants to practice.

## ✨ What It Does

- 📝 **Grades essays against a rubric**: not just a single score, but a
  breakdown per criterion, so students know exactly where they're strong.
- 🔤 **Catches spelling and grammar mistakes**: with a plain explanation for
  each one, not just "this is wrong."
- 💬 **Suggests better vocabulary**: flags weak or repeated words and offers
  stronger Arabic alternatives.
- 📊 **Keeps a history**: students can see how their scores improve over time.

## 🛠️ Built With

- **Python** + **FastAPI**: the backend server
- **Vanilla JavaScript, HTML, CSS**: the frontend, no framework needed
- **[Fanar API](https://fanar.qa)**: the AI model that reads and grades essays

## 📁 Folder Structure

```
essay-assistant/
├── backend/
│   ├── server.py          # FastAPI backend
│   ├── fanar.py           # Talks to the Fanar AI model
│   ├── content.json       # All writing tasks and rubrics
│   └── requirements.txt   # Python dependencies
└── frontend/
    ├── index.html         # The app's pages/screens
    ├── script.js          # Frontend logic
    ├── style.css          # All styling (incl. dark mode)
    └── favicon.svg        # Browser tab icon
```

## 🚀 Getting Started

**1. Set up a Python environment** (keeps things clean and isolated):

```bash
python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
```

**2. Install the dependencies:**

```bash
pip install -r backend/requirements.txt
```

**3. Add your Fanar API key:**

Don't have one yet? Request one here: https://api.fanar.qa/request/en

```bash
export FANAR_API_KEY="your_key_here"
```

**4. Run the backend:**

```bash
cd backend
python server.py
```

**5. Open the app:**

Just open `frontend/index.html` in your browser. That's it, you're ready to write!