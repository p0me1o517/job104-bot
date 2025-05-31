from flask import Flask, render_template, request, abort
from job104_spider import Job104Spider
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, 
    TextMessage, 
    TextSendMessage,
    QuickReply,
    QuickReplyButton,
    MessageAction,
    PostbackAction,
    URIAction
)
import sqlite3
import os
from datetime import datetime

app = Flask(__name__, template_folder='templates')

# LINE Bot 設定
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'klVqD2n+y6hl//EHFaIrC+/JTGfBJC9MdWuBnsDT4Y8/p6YKIJDABn2RkiiljY2+LTk1E7p2sd5ardMaqEzEcbrkbE+aBxZJKTjch+D9k+YZcwk5GLSixDQGXhKoVpr+wfnCYQ05XkwbjfMv6cDs4wdB04t89/1O/w1cDnyilFU='))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET', '69154eb08d78b91e1d28aa1eb60f17a4'))

# 建立快速回覆按鈕
def create_quick_reply():
    return QuickReply(items=[
        QuickReplyButton(
            action=MessageAction(label="台北", text="地區:台北")
        ),
        QuickReplyButton(
            action=MessageAction(label="台中", text="地區:台中")
        ),
        QuickReplyButton(
            action=MessageAction(label="高薪", text="薪資:50000")
        ),
        QuickReplyButton(
            action=MessageAction(label="說明", text="幫助")
        )
    ])

# LINE Webhook
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_msg = event.message.text.strip()
    user_id = event.source.user_id

    # 幫助指令
    if user_msg == "幫助":
        help_text = """
📢 使用說明：
1. 直接輸入「職稱」搜尋
  範例：工程師
2. 進階搜尋格式：
  「搜尋 [地區] [職稱] [薪資]」
  範例：搜尋 台北 Python 50000
3. 快速按鈕：
  - 台北/台中：地區篩選
  - 高薪：5萬以上職缺
"""
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=help_text, quick_reply=create_quick_reply())
        )
        return

    # 解析搜尋指令
    search_params = {
        'keyword': '',
        'area': '',
        'min_salary': None,
        'max_salary': None
    }

    # 處理快速指令
    if user_msg.startswith("地區:"):
        search_params['area'] = user_msg.split(":")[1]
    elif user_msg.startswith("薪資:"):
        search_params['min_salary'] = int(user_msg.split(":")[1])
    elif user_msg.startswith("搜尋"):
        parts = user_msg.split()
        if len(parts) >= 2:
            for part in parts[1:]:
                if part.replace(',', '').isdigit():
                    if not search_params['min_salary']:
                        search_params['min_salary'] = int(part.replace(',', ''))
                    else:
                        search_params['max_salary'] = int(part.replace(',', ''))
                elif part in ["台北", "台中", "高雄"]:
                    search_params['area'] = part
                else:
                    search_params['keyword'] += part + ' '
            search_params['keyword'] = search_params['keyword'].strip()
    else:
        search_params['keyword'] = user_msg

    # 執行資料庫查詢
    conn = sqlite3.connect('jobNs.db')
    cursor = conn.cursor()
    
    query = """
    SELECT name, company_name, salary, job_url, company_addr 
    FROM jobs 
    WHERE 1=1
    """
    params = []

    if search_params['keyword']:
        query += " AND (name LIKE ? OR company_name LIKE ?)"
        params.extend([f'%{search_params["keyword"]}%', f'%{search_params["keyword"]}%'])
    
    if search_params['area']:
        normalized_area = search_params['area'].replace('臺', '台').strip()
        if normalized_area.endswith(('市', '縣')):
            normalized_area = normalized_area[:-1]
        query += " AND (company_addr LIKE ? OR company_addr LIKE ?)"
        params.extend([f'%{normalized_area}%', f'%{normalized_area}市%'])
    
    if search_params['min_salary']:
        query += " AND salary_high >= ?"
        params.append(search_params['min_salary'])
    
    if search_params['max_salary']:
        query += " AND salary_low <= ?"
        params.append(search_params['max_salary'])

    query += " ORDER BY appear_date DESC LIMIT 5"
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    # 組織回覆訊息
    if results:
        reply = "🔍 搜尋結果：\n\n" + "\n\n".join([
            f"🏢 {name}\n"
            f"🏭 公司：{company}\n"
            f"💰 薪資：{salary}\n"
            f"📍 地點：{addr.split()[0]}\n"
            f"🔗 {url}"
            for name, company, salary, url, addr in results
        ])
    else:
        reply = "找不到符合條件的職缺，請嘗試其他關鍵字或調整條件"

    # 回覆時附加快速按鈕
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=reply + "\n\n💡 試試下方快速按鈕",
            quick_reply=create_quick_reply()
        )
    )

# 以下保持原有網頁端功能不變
class PaginationHelper:
    @staticmethod
    def get_page_range(current_page, total_pages, display_pages=10):
        half = display_pages // 2
        start = max(1, current_page - half)
        end = min(total_pages, start + display_pages - 1)
        if end - start + 1 < display_pages:
            start = max(1, end - display_pages + 1)
        return range(start, end + 1)

@app.route('/')
def show_jobs():
    # [保持原有 show_jobs 函數內容完全不变]
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
    
    if keyword:
        conditions.append("(name LIKE ? OR company_name LIKE ?)")
        params.extend([f'%{keyword}%', f'%{keyword}%'])
    
    if area:
        normalized_area = area.replace('臺', '台').strip()
        if normalized_area.endswith(('市', '縣')):
            normalized_area = normalized_area[:-1]
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
    
    if salary_min is not None and salary_max is not None:
        conditions.append("(salary_low <= ? AND salary_high >= ?)")
        params.extend([salary_max, salary_min])
    elif salary_min is not None:
        conditions.append("salary_high >= ?")
        params.append(salary_min)
    elif salary_max is not None:
        conditions.append("salary_low <= ?")
        params.append(salary_max)
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
