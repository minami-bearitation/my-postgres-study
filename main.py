from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

import models
from database import engine, get_db

# DBテーブルの自動作成
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="完全版 タスク管理API")

# ------------------------------------------------------------------
# HTML / JavaScript フロントエンド画面
# ------------------------------------------------------------------
html_content = """
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>高機能 タスク管理アプリ</title>
  <style>
    body { font-family: sans-serif; max-width: 700px; margin: 30px auto; padding: 0 20px; }
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 5px; font-weight: bold; }
    input, textarea, select { width: 100%; padding: 8px; box-sizing: border-box; }
    button { padding: 8px 12px; background: #007bff; color: white; border: none; cursor: pointer; border-radius: 4px; }
    button:disabled { background: #ccc; cursor: not-allowed; }
    .btn-danger { background: #dc3545; }
    .btn-success { background: #28a745; }
    .btn-secondary { background: #6c757d; }
    .error { color: #721c24; background: #f8d7da; border: 1px solid #f5c6cb; padding: 10px; border-radius: 4px; margin-bottom: 15px; display: none; }
    .loading { color: #055160; background: #cff4fc; padding: 10px; border-radius: 4px; display: none; margin-bottom: 15px; }
    .task-card { border: 1px solid #ddd; padding: 15px; margin-bottom: 10px; border-radius: 6px; background: #fdfdfd; }
    .task-header { display: flex; justify-content: space-between; align-items: center; }
    .task-actions { margin-top: 10px; display: flex; gap: 8px; }
    .badge { padding: 3px 8px; border-radius: 12px; font-size: 0.8em; color: white; }
    .bg-todo { background: #6c757d; }
    .bg-doing { background: #ffc107; color: black; }
    .bg-done { background: #28a745; }
    .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); }
    .modal-content { background: white; margin: 10% auto; padding: 20px; max-width: 500px; border-radius: 8px; }
  </style>
</head>
<body>

  <h1>📝 タスク管理システム</h1>

  <div id="errorMessage" class="error"></div>
  <div id="loadingMessage" class="loading">⏳ 通信中...</div>

  <!-- タスク登録フォーム -->
  <h2>新規タスク登録</h2>
  <form id="createForm">
    <div class="form-group">
      <label>タイトル（必須）</label>
      <input type="text" id="titleInput" placeholder="例: システム要件の作成">
    </div>
    <div class="form-group">
      <label>詳細</label>
      <textarea id="descInput" placeholder="例: APIの仕様を整理する"></textarea>
    </div>
    <button type="submit" id="createBtn">タスクを追加</button>
  </form>

  <hr style="margin: 30px 0;">

  <!-- タスク一覧 -->
  <h2>タスク一覧</h2>
  <div id="taskList"></div>

  <!-- タスク詳細・編集モーダル（ポップアップ画面） -->
  <div id="detailModal" class="modal">
    <div class="modal-content">
      <h2 id="modalTitle">タスク詳細・編集</h2>
      <input type="hidden" id="modalTaskId">
      <div class="form-group">
        <label>タイトル（必須）</label>
        <input type="text" id="modalTitleInput">
      </div>
      <div class="form-group">
        <label>詳細</label>
        <textarea id="modalDescInput"></textarea>
      </div>
      <div class="task-actions">
        <button id="saveEditBtn" class="btn-success">変更を保存</button>
        <button id="closeModalBtn" class="btn-secondary">閉じる</button>
      </div>
    </div>
  </div>

  <script>
    const API_URL = '/tasks';

    function showError(msg) {
      const errEl = document.getElementById('errorMessage');
      errEl.textContent = msg;
      errEl.style.display = 'block';
    }

    function clearError() {
      document.getElementById('errorMessage').style.display = 'none';
    }

    function showLoading(show) {
      document.getElementById('loadingMessage').style.display = show ? 'block' : 'none';
    }

    // 1. タスク一覧取得
    async function loadTasks() {
      clearError();
      showLoading(true);

      try {
        const res = await fetch(API_URL);
        if (!res.ok) throw new Error('API接続エラー');
        
        const tasks = await res.json();
        const listEl = document.getElementById('taskList');
        listEl.innerHTML = '';

        if (tasks.length === 0) {
          listEl.innerHTML = '<p>タスクはありません。</p>';
          return;
        }

        tasks.forEach(task => {
          const card = document.createElement('div');
          card.className = 'task-card';
          
          let badgeClass = 'bg-todo';
          if (task.status === 'in_progress') badgeClass = 'bg-doing';
          if (task.status === 'done') badgeClass = 'bg-done';

          card.innerHTML = `
            <div class="task-header">
              <strong>${escapeHtml(task.title)}</strong>
              <span class="badge ${badgeClass}">${task.status}</span>
            </div>
            <p>${escapeHtml(task.description || '詳細なし')}</p>
            <div class="task-actions">
              <button onclick="openDetail(${task.id})">詳細/編集</button>
              <button onclick="changeStatus(${task.id}, 'todo')" class="btn-secondary">未着手</button>
              <button onclick="changeStatus(${task.id}, 'in_progress')" class="btn-secondary">進行中</button>
              <button onclick="changeStatus(${task.id}, 'done')" class="btn-success">完了</button>
              <button onclick="deleteTask(${task.id})" class="btn-danger">削除</button>
            </div>
          `;
          listEl.appendChild(card);
        });
      } catch (err) {
        showError('⚠️ APIに接続できませんでした。サーバーが起動しているか確認してください。');
      } finally {
        showLoading(false);
      }
    }

    // HTMLエスケープ処理（安全対策）
    function escapeHtml(str) {
      return str.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
    }

    // 2. タスク登録（必須チェック & 連打防止付き）
    document.getElementById('createForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      clearError();

      const title = document.getElementById('titleInput').value.trim();
      const description = document.getElementById('descInput').value.trim();

      // [確認事項] 必須項目チェック
      if (!title) {
        showError('❌ タイトルは必須項目です。');
        return;
      }

      const btn = document.getElementById('createBtn');
      btn.disabled = true; // [確認事項] 同じ操作の連打防止

      try {
        const res = await fetch(API_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, description })
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || '登録失敗');
        }

        document.getElementById('titleInput').value = '';
        document.getElementById('descInput').value = '';
        await loadTasks();
      } catch (err) {
        showError('⚠️ DBへの登録に失敗しました: ' + err.message);
      } finally {
        btn.disabled = false;
      }
    });

    // 3. タスク詳細表示（存在しないデータ判定）
    async function openDetail(id) {
      clearError();
      showLoading(true);

      try {
        const res = await fetch(`${API_URL}/${id}`);
        if (res.status === 404) {
          throw new Error('指定されたタスクは存在しません（既に削除された可能性があります）。');
        }
        if (!res.ok) throw new Error('通信エラー');

        const task = await res.json();
        document.getElementById('modalTaskId').value = task.id;
        document.getElementById('modalTitleInput').value = task.title;
        document.getElementById('modalDescInput').value = task.description || '';
        document.getElementById('detailModal').style.display = 'block';
      } catch (err) {
        showError('⚠️ ' + err.message);
      } finally {
        showLoading(false);
      }
    }

    // モーダルを閉じる
    document.getElementById('closeModalBtn').onclick = () => {
      document.getElementById('detailModal').style.display = 'none';
    };

    // 4. タスク更新（編集）
    document.getElementById('saveEditBtn').onclick = async () => {
      clearError();
      const id = document.getElementById('modalTaskId').value;
      const title = document.getElementById('modalTitleInput').value.trim();
      const description = document.getElementById('modalDescInput').value.trim();

      if (!title) {
        showError('❌ タイトルを入力してください。');
        return;
      }

      const btn = document.getElementById('saveEditBtn');
      btn.disabled = true;

      try {
        const res = await fetch(`${API_URL}/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title, description })
        });

        if (res.status === 404) throw new Error('対象のタスクが見つかりませんでした。');
        if (!res.ok) throw new Error('更新失敗');

        document.getElementById('detailModal').style.display = 'none';
        await loadTasks();
      } catch (err) {
        showError('⚠️ ' + err.message);
      } finally {
        btn.disabled = false;
      }
    };

    // 5. ステータス変更
    async function changeStatus(id, newStatus) {
      clearError();
      try {
        const res = await fetch(`${API_URL}/${id}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: newStatus })
        });

        if (res.status === 404) throw new Error('対象のタスクが存在しません。');
        if (!res.ok) throw new Error('ステータス変更失敗');

        await loadTasks();
      } catch (err) {
        showError('⚠️ ' + err.message);
      }
    }

    // 6. タスク削除（存在しない/連打チェック対応）
    async function deleteTask(id) {
      if (!confirm('本当に削除しますか？')) return;
      clearError();

      try {
        const res = await fetch(`${API_URL}/${id}`, { method: 'DELETE' });

        if (res.status === 404) {
          throw new Error('すでに削除されているか、存在しないデータです。');
        }
        if (!res.ok) throw new Error('削除に失敗しました');

        await loadTasks();
      } catch (err) {
        showError('⚠️ ' + err.message);
      }
    }

    // 初期ロード
    loadTasks();
  </script>
</body>
</html>
"""

# ------------------------------------------------------------------
# Backend (FastAPI API エンドポイント & 例外処理)
# ------------------------------------------------------------------

# リクエストスキーマ（入力チェック定義）
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1) # 必須（1文字以上）
    description: Optional[str] = None

class TaskUpdate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str  # todo, in_progress, done

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str

    class Config:
        orm_mode = True

# トップページ
@app.get("/", response_class=HTMLResponse)
def read_index():
    return html_content

# 1. 一覧取得
@app.get("/tasks", response_model=List[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):
    return db.query(models.Task).all()

# 2. 単体詳細取得（404チェック）
@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="指定されたタスクが見つかりません。")
    return task

# 3. 新規登録
@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    try:
        db_task = models.Task(title=task.title, description=task.description, status="todo")
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="DBへの保存に失敗しました。")

# 4. 内容更新
@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task_data: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="更新対象のタスクが存在しません。")
    
    task.title = task_data.title
    task.description = task_data.description
    db.commit()
    db.refresh(task)
    return task

# 5. ステータス変更
@app.patch("/tasks/{task_id}/status", response_model=TaskResponse)
def update_task_status(task_id: int, status_data: StatusUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="対象のタスクが存在しません。")
    
    task.status = status_data.status
    db.commit()
    db.refresh(task)
    return task

# 6. 削除
@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="削除対象のタスクが存在しません。")
    
    db.delete(task)
    db.commit()
    return {"message": "正常に削除されました。"}