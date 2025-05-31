from flask import Flask, render_template, request,abort
from job104_spider import Job104Spider
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import sqlite3
import os

app = Flask(__name__, template_folder='templates')

# 替換成你自己的 Channel Access Token 和 Secret
line_bot_api = LineBotApi('klVqD2n+y6hl//EHFaIrC+/JTGfBJC9MdWuBnsDT4Y8/p6YKIJDABn2RkiiljY2+LTk1E7p2sd5ardMaqEzEcbrkbE+aBxZJKTjch+D9k+YZcwk5GLSixDQGXhKoVpr+wfnCYQ05XkwbjfMv6cDs4wdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('69154eb08d78b91e1d28aa1eb60f17a4')

# LINE Webhook 路徑
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# LINE 收到文字訊息時的處理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    conn = sqlite3.connect('jobNs.db')
    cursor = conn.cursor()
    
    if user_msg == "#職缺查詢":
        reply = "請輸入職缺關鍵字（例如：工程師、行銷）："
    
    elif user_msg == "#地區查詢":
        reply = "請輸入地區（例如：台北、台中）："
    
    elif user_msg == "#薪水查詢":
        reply = "請輸入薪資範圍（例如：30000~50000）："
    
    else:
        # 根據用戶輸入的關鍵字進行查詢（原有邏輯）
        cursor.execute("""
            SELECT name, company_name, salary, job_url 
            FROM jobs 
            WHERE name LIKE ? OR company_addr LIKE ? OR salary LIKE ?
            LIMIT 5
        """, (f'%{user_msg}%', f'%{user_msg}%', f'%{user_msg}%'))
        
        results = cursor.fetchall()
        if results:
            reply = "\n\n".join([
                f"{name}\n公司：{company}\n薪資：{salary}\n🔗 {url}"
                for name, company, salary, url in results
            ])
        else:
            reply = "找不到相關職缺，請換個關鍵字試試！"
    
    conn.close()
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

class PaginationHelper:
    @staticmethod
    def get_page_range(current_page, total_pages, display_pages=10):
        half = display_pages // 2
        start = max(1, current_page - half)
        end = min(total_pages, start + display_pages - 1)
        if end - start + 1 < display_pages:
            start = max(1, end - display_pages + 1)
        return range(start, end + 1)
def initialize_rich_menu():
    """安全的 Rich Menu 初始化函數"""
    try:
        # 檢查是否已有同名 Rich Menu
        existing_menus = line_bot_api.get_rich_menu_list()
        for menu in existing_menus:
            if menu.name == "Job Search Menu":
                line_bot_api.delete_rich_menu(menu.rich_menu_id)
        
        # 創建新 Rich Menu
        image_path = os.path.join(app.root_path, 'static', 'job.png')
        if not os.path.exists(image_path):
            print(f"警告: Rich Menu 圖片不存在於 {image_path}")
            return False
            
        rich_menu = {
            "size": {"width": 2500, "height": 843},
            "selected": False,
            "name": "Job Search Menu",
            "chatBarText": "點我查職缺",
            "areas": [
                {"bounds": {"x": 0, "y": 0, "width": 833, "height": 843}, "action": {"type": "message", "text": "#職缺查詢"}},
                {"bounds": {"x": 833, "y": 0, "width": 833, "height": 843}, "action": {"type": "message", "text": "#地區查詢"}},
                {"bounds": {"x": 1666, "y": 0, "width": 834, "height": 843}, "action": {"type": "message", "text": "#薪水查詢"}}
            ]
        }
        
        rich_menu_id = line_bot_api.create_rich_menu(rich_menu=rich_menu)
        with open(image_path, "rb") as f:
            line_bot_api.set_rich_menu_image(rich_menu_id, "image/png", f)
        line_bot_api.set_default_rich_menu(rich_menu_id)
        return True
    except Exception as e:
        print(f"Rich Menu 初始化錯誤: {str(e)}")
        return False
def normalize_area(area):
    """統一地區名稱格式"""
    area = area.replace('臺', '台').strip()
    if area.endswith(('市', '縣')):
        area = area[:-1]
    return area

@app.route('/')
def show_jobs():
    # 獲取搜尋參數
    keyword = request.args.get('keyword', '').strip()
    area = request.args.get('area', '').strip()
    salary_min = request.args.get('salary_min', type=int)
    salary_max = request.args.get('salary_max', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    spider = Job104Spider()
    query = "SELECT * FROM jobs"
    params = []
    conditions = []
    
    # 關鍵字搜尋
    if keyword:
        conditions.append("(name LIKE ? OR company_name LIKE ?)")
        params.extend([f'%{keyword}%', f'%{keyword}%'])
    
    # 精確地區搜尋
    if area:
        normalized_area = normalize_area(area)
        conditions.append("""
            (company_addr LIKE ? OR 
             company_addr LIKE ? OR 
             company_addr LIKE ? OR 
             company_addr LIKE ?)
        """)
        params.extend([
            f'{normalized_area}市%',
            f'{normalized_area}縣%',
            f'{normalized_area}%',
            f'臺{normalized_area[1:]}市%' if normalized_area.startswith('台') else ''
        ])
    
    # 薪資範圍搜尋
    if salary_min is not None and salary_max is not None:
        conditions.append("(salary_low <= ? AND salary_high >= ?)")
        params.extend([salary_max, salary_min])
    elif salary_min is not None:
        conditions.append("salary_high >= ?")
        params.append(salary_min)
    elif salary_max is not None:
        conditions.append("salary_low <= ?")
        params.append(salary_max)
    
    # 組合查詢條件
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # 分頁處理
    count_query = "SELECT COUNT(*) FROM jobs" + (" WHERE " + " AND ".join(conditions) if conditions else "")
    spider.cursor.execute(count_query, params)
    total = spider.cursor.fetchone()[0]
    
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    
    query += " ORDER BY appear_date DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page-1)*per_page])
    spider.cursor.execute(query, params)
    jobs = spider.cursor.fetchall()
    
    return render_template(
        'index.html',
        jobs=jobs,
        page=page,
        total=total,
        keyword=keyword,
        area=area,
        salary_min=salary_min,
        salary_max=salary_max,
        total_pages=total_pages,
        page_range=PaginationHelper.get_page_range(page, total_pages)
    )

@app.route('/refresh')
def refresh_jobs():
    spider = Job104Spider()
    spider.run(max_pages=None, clear_old=True)
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>資料更新完成</title>
        <meta http-equiv="refresh" content="3;url=/" />
        <style>
            body { font-family: Arial; text-align: center; padding: 50px; }
            a { color: #06c; }
        </style>
    </head>
    <body>
        <h1>職缺資料已更新完成！</h1>
        <p>3秒後自動返回首頁，或<a href="/">點此立即返回</a></p>
    </body>
    </html>
    """

if __name__ == '__main__':
    # 本地開發模式
    setup_rich_menu()
    app.run(debug=True, port=5000)
else:
    # Render 部署模式
    # 改用應用上下文和手動初始化
    with app.app_context():
        try:
            setup_rich_menu()
        except Exception as e:
            print(f"Rich Menu 初始化失敗: {str(e)}")
            # 可以選擇記錄日誌或忽略錯誤繼續運行
