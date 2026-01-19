# 旅程規劃網站

提供三個視覺版本的旅程規劃網站，具備以下功能：

- 建立旅程並輸入遊玩天數
- 記錄已建立旅程並可進入行程安排畫面（滑動切換天數）
- 新增、編輯、刪除旅程
- 新增每日行程，包含地圖連結與消費紀錄
- 顯示每日與全旅程總消費

## 啟動方式

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

瀏覽：
- `http://localhost:5000/` 版本選擇
- `http://localhost:5000/v1` 版本一
- `http://localhost:5000/v2` 版本二
- `http://localhost:5000/v3` 版本三
