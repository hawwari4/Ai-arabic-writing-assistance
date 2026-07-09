const API_BASE = "http://localhost:5000";

const state = { content: null, grade: null, semester: null, task: null };
const history = ['grade'];
const MIN_WORDS_DEFAULT = 100;

// ---------- tiny Markdown renderer ----------
function renderMarkdown(md) {
  if (!md) return '';
  const lines = md.split('\n');
  let html = '';
  let inList = false;
  for (let raw of lines) {
    const line = raw.trim();
    if (line === '') { if (inList) { html += '</ul>'; inList = false; } continue; }
    if (line === '---') { if (inList) { html += '</ul>'; inList = false; } html += '<hr>'; continue; }
    const h = line.match(/^(#{1,3})\s+(.*)/);
    if (h) {
      if (inList) { html += '</ul>'; inList = false; }
      const level = h[1].length + 2; 
      html += `<h${level}>${inlineMd(h[2])}</h${level}>`;
      continue;
    }
    if (/^-\s+/.test(line)) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += `<li>${inlineMd(line.replace(/^-\s+/, ''))}</li>`;
      continue;
    }
    if (inList) { html += '</ul>'; inList = false; }
    html += `<p>${inlineMd(line)}</p>`;
  }
  if (inList) html += '</ul>';
  return html;
}
function inlineMd(text) {
  return text.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
}

// ---------- API Calls ----------
async function loadContent() {
  const res = await fetch(`${API_BASE}/content`);
  if (!res.ok) throw new Error('تعذّر تحميل بيانات المهام');
  state.content = await res.json();
}

async function callEvaluationAPI(grade, semester, taskId, studentText) {
  console.log(`Calling evaluation API for task ${taskId}...`);
  const response = await fetch(`${API_BASE}/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grade: grade,
      semester: semester,
      task_id: taskId,
      student_text: studentText
    })
  });
  
  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}));
    const errorMsg = errBody.detail || `Server responded with ${response.status}`;
    console.error("API Error:", errorMsg);
    throw new Error(errorMsg);
  }
  
  const data = await response.json();
  console.log("Evaluation API response:", data);
  return data;
}

// ---------- UI Logic ----------
function scoreBand(total, max) {
  if (max === 0) return { label: 'لا توجد معايير', pct: 0 };
  const pct = total / max;
  if (pct >= 0.85) return { label: 'ممتاز', pct: Math.round(pct * 100) };
  if (pct >= 0.7) return { label: 'جيد جدًا', pct: Math.round(pct * 100) };
  if (pct >= 0.5) return { label: 'جيد', pct: Math.round(pct * 100) };
  return { label: 'بحاجة إلى تحسين', pct: Math.round(pct * 100) };
}

function renderDots(screen) {
  const dotsIdx = { grade: 0, semester: 1, units: 2, task: 3, writing: 4, results: 4 }[screen];
  document.querySelectorAll('#dots span').forEach((d, i) => d.classList.toggle('active', i <= dotsIdx));
}

function goto(screen, push = true) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelector(`[data-screen="${screen}"]`).classList.add('active');
  renderDots(screen);
  document.getElementById('backBtn').style.visibility = screen === 'grade' ? 'hidden' : 'visible';
  if (push) history.push(screen);

  if (screen === 'writing') {
    document.getElementById('introStage').style.display = 'flex';
    document.getElementById('writingArea').style.display = 'none';
    setTimeout(() => {
      document.getElementById('introStage').style.display = 'none';
      document.getElementById('writingArea').style.display = 'block';
    }, 2000);
  }
  window.scrollTo(0, 0);
}

function goBack() {
  if (history.length > 1) {
    history.pop();
    goto(history[history.length - 1], false);
  }
}

function renderGrades() {
  const grid = document.getElementById('gradeGrid');
  grid.innerHTML = '';
  const arabicNum = { '7': '٧', '8': '٨', '9': '٩' };
  Object.entries(state.content.grades).forEach(([gradeKey, grade]) => {
    grid.innerHTML += `
      <div class="pick-card" onclick="pickGrade('${gradeKey}')">
        <span class="num">${arabicNum[gradeKey] || gradeKey}</span>
        <div class="label">${grade.label}</div>
        <div class="sub">المرحلة الإعدادية</div>
      </div>`;
  });
}

function pickGrade(gradeKey) {
  state.grade = gradeKey;
  document.getElementById('gradeLabel').textContent = state.content.grades[gradeKey].label;
  renderSemesters();
  goto('semester');
}

function renderSemesters() {
  const grid = document.getElementById('semesterGrid');
  grid.innerHTML = '';
  const arabicNum = { '1': '١', '2': '٢' };
  const semesters = state.content.grades[state.grade].semesters;
  Object.entries(semesters).forEach(([semKey, sem]) => {
    grid.innerHTML += `
      <div class="pick-card" onclick="pickSemester('${semKey}')">
        <span class="num">${arabicNum[semKey] || semKey}</span>
        <div class="label">${sem.label}</div>
      </div>`;
  });
}

function pickSemester(semKey) {
  state.semester = semKey;
  renderUnits();
  goto('units');
}

function renderUnits() {
  const list = document.getElementById('unitList');
  list.innerHTML = '';
  const tasks = state.content.grades[state.grade].semesters[state.semester].tasks;
  if (tasks.length === 0) {
    list.innerHTML = `
      <div class="unit-row locked">
        <div class="unit-badge">--</div>
        <div><div class="unit-title">لا توجد مهام بعد</div><div class="unit-note">سيتم إضافة الوحدات قريبًا</div></div>
        <span class="chip">قريبًا</span>
      </div>`;
    return;
  }
  tasks.forEach((task, i) => {
    list.innerHTML += `
      <div class="unit-row" onclick="pickTask('${task.id}')">
        <div class="unit-badge">${i + 1}</div>
        <div><div class="unit-title">${task.title}</div><div class="unit-note">${task.type || ''}</div></div>
        <span class="chip">ابدأ الآن</span>
      </div>`;
  });
}

function pickTask(taskId) {
  const tasks = state.content.grades[state.grade].semesters[state.semester].tasks;
  state.task = tasks.find(t => t.id === taskId);
  renderTaskScreen();
  renderBrief();
  goto('task');
}

function renderBrief() {
  const task = state.task;
  document.getElementById('briefBody').innerHTML = `
    <b>التخطيط للكتابة:</b>
    ${renderMarkdown(task.planning)}
    <b>الإرشادات:</b>
    ${renderMarkdown(task.guidelines)}`;
  document.getElementById('minWordsHint').textContent = `الحد الأدنى المقترح: ${minWords()} كلمة`;
}

function renderTaskScreen() {
  const task = state.task;
  document.getElementById('taskUnitLabel').textContent = task.title;
  document.getElementById('taskCard').innerHTML = `
    <span class="tag">${task.type || 'مهمة كتابية'}</span>
    <h2>${task.title}</h2>
    ${renderMarkdown(task.text)}
    <div class="meta-row">
      <div><b>${task.min_words || MIN_WORDS_DEFAULT}+ كلمة</b>الحد الأدنى المقترح</div>
      <div><b>${task.rubric.length} معايير</b>تقييم آلي فوري</div>
    </div>`;
}

function minWords() { return (state.task && state.task.min_words) || MIN_WORDS_DEFAULT; }

function countWords(text) {
  return (text.trim().match(/[\u0600-\u06FF\w]+/g) || []).length;
}

function updateCount() {
  const textarea = document.getElementById('essay');
  const words = countWords(textarea.value);
  const min = minWords();
  const wordCountEl = document.getElementById('wordCount');
  const submitBtn = document.getElementById('submitBtn');
  const hintMsg = document.getElementById('hintMsg');
  wordCountEl.textContent = words.toLocaleString('ar-EG') + ' كلمة';
  wordCountEl.className = words >= min ? 'count ok' : '';
  submitBtn.disabled = words < min;
  hintMsg.textContent = words < min
    ? `أضف ${min - words} كلمة أخرى على الأقل لإتمام المقال`
    : 'مقالك جاهز للإرسال ✓';
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('essay').addEventListener('input', updateCount);
  init();
});

function restartWriting() {
  document.getElementById('essay').value = '';
  updateCount();
  goto('writing');
}

async function submitEssay() {
  const essayText = document.getElementById('essay').value;
  const errorMsg = document.getElementById('errorMsg');
  errorMsg.style.display = 'none';
  
  // FIX: Use style.display instead of .hidden to override inline style="display:none;"
  const loadingOverlay = document.getElementById('loadingOverlay');
  loadingOverlay.style.display = 'flex';

  try {
    const result = await callEvaluationAPI(state.grade, state.semester, state.task.id, essayText);
    renderResults(result);
    loadingOverlay.style.display = 'none';
    goto('results');
  } catch (err) {
    loadingOverlay.style.display = 'none';
    
    let userMsg = 'تعذّر الاتصال بخدمة التقييم. تأكد من تشغيل الخادم (server.py) ثم حاول مرة أخرى.';
    if (err.message.includes('JSON') || err.message.includes('لم يتم العثور')) {
      userMsg = 'حدث خطأ في معالجة المقال بواسطة النموذج. يرجى إعادة المحاولة أو تغيير صياغة المقال.';
    } else if (err.message.includes('502') || err.message.includes('500')) {
      userMsg = 'حدث خطأ في الخادم. يرجى المحاولة لاحقًا.';
    }
    
    errorMsg.textContent = userMsg;
    errorMsg.style.display = 'block';
    console.error('Evaluation request failed:', err);
  }
}

function renderResults(data) {
  const scores = data.scores || {};
  const keys = Object.keys(scores);
  const total = keys.reduce((sum, k) => sum + (scores[k] || 0), 0);
  const max = keys.length * 3;
  const band = scoreBand(total, max);

  document.getElementById('scoreBadge').textContent = band.pct + '%';
  document.getElementById('scoreBand').textContent = 'التقييم العام: ' + band.label;
  document.getElementById('overallComment').textContent = data.overall_comment || 'لا يوجد تعليق عام.';

  const grid = document.getElementById('criteriaGrid');
  grid.innerHTML = '';
  keys.forEach(name => {
    const score = scores[name] || 0;
    const dots = [1, 2, 3].map(i => `<span class="${i <= score ? 'filled' : ''}"></span>`).join('');
    const fb = (data.feedback && data.feedback[name]) || 'لا يوجد تعليق';
    grid.innerHTML += `<div class="criterion"><div class="criterion-top"><span class="criterion-name">${name}</span><div class="dots">${dots}</div></div><div class="criterion-fb">${fb}</div></div>`;
  });

  const mistakes = data.mistakes || [];
  const spelling = mistakes.filter(m => m.type === 'إملائي');
  const grammar = mistakes.filter(m => m.type === 'نحوي');
  document.getElementById('mistakeGroups').innerHTML = `<div class="mistake-count">إملائي: ${spelling.length}</div><div class="mistake-count">نحوي: ${grammar.length}</div>`;

  const list = document.getElementById('mistakesList');
  list.innerHTML = '';
  mistakes.forEach(m => {
    list.innerHTML += `<div class="mistake-item"><span class="mistake-tag">${m.type}</span><br><span class="orig">${m.original}</span> ← <span class="fix">${m.correction}</span><div class="expl">${m.explanation}</div></div>`;
  });

  document.getElementById('improvedParagraph').textContent = data.improved_paragraph || 'لم يتم تقديم نسخة محسّنة.';
}

async function init() {
  try {
    await loadContent();
    renderGrades();
  } catch (err) {
    document.getElementById('gradeGrid').innerHTML =
      `<p class="hint" style="color:#C24B4B">تعذّر تحميل بيانات المهام. تأكد من تشغيل الخادم (server.py) على المنفذ 5000.</p>`;
    console.error(err);
  }
  renderDots('grade');
}