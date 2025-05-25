from flask import Flask, render_template, request,abort
from job104_spider import Job104Spider
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import sqlite3

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
    cursor.execute("""
    SELECT name, company_name, salary, job_url 
    FROM jobs 
    WHERE name LIKE ? OR company_addr LIKE ?
    """, (f'%{user_msg}%', f'%{user_msg}%'))
    results = cursor.fetchall()
    conn.close()

    if results:
        reply = '\n\n'.join([
            f"{name}\n公司：{company}\n薪資：{salary}\n🔗 {url}"
            for name, company, salary, url in results[:5]
        ])
    else:
        reply = "找不到相關職缺，請換個關鍵字試試！"

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
    app.run(debug=True, port=5000)
