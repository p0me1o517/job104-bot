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

# 建立主選單快速回覆按鈕
def create_main_menu():
    return QuickReply(items=[
        QuickReplyButton(
            action=MessageAction(label="🔍 搜尋職缺", text="show_search_options")
        ),
        QuickReplyButton(
            action=MessageAction(label="⭐ 我的收藏", text="show_favorites")
        ),
        QuickReplyButton(
            action=URIAction(label="🌐 網站版", uri="https://your-website.com")
        ),
        QuickReplyButton(
            action=MessageAction(label="ℹ️ 使用說明", text="show_help")
        )
    ])

# 建立搜尋選項按鈕
def create_search_options():
    return QuickReply(items=[
        QuickReplyButton(
            action=MessageAction(label="🏙️ 台北職缺", text="search:台北")
        ),
        QuickReplyButton(
            action=MessageAction(label="🏙️ 台中職缺", text="search:台中")
        ),
        QuickReplyButton(
            action=MessageAction(label="💰 高薪職缺", text="search:高薪")
        ),
        QuickReplyButton(
            action=MessageAction(label="🆕 最新職缺", text="search:最新")
        ),
        QuickReplyButton(
            action=MessageAction(label="🔙 返回主選單", text="main_menu")
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

    # 主選單控制
    if user_msg == "main_menu":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="請選擇功能：",
                quick_reply=create_main_menu()
            )
        )
        return

    # 搜尋選單
    if user_msg == "show_search_options":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="請選擇搜尋條件：",
                quick_reply=create_search_options()
            )
        )
        return

    # 使用說明
    if user_msg == "show_help":
        help_text = """
🤖 使用說明：
完全不用打字！只需：
1. 點擊「🔍 搜尋職缺」
2. 選擇篩選條件
3. 查看系統推薦職缺

📌 按鈕功能：
🏙️ 地區篩選 - 台北/台中
💰 高薪職缺 - 月薪5萬+
🆕 最新職缺 - 24小時內更新
"""
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=help_text,
                quick_reply=create_main_menu()
            )
        )
        return

    # 搜尋功能
    if user_msg.startswith("search:"):
        search_type = user_msg.split(":")[1]
        
        conn = sqlite3.connect('jobNs.db')
        cursor = conn.cursor()
        
        if search_type == "高薪":
            cursor.execute("""
            SELECT name, company_name, salary, job_url 
            FROM jobs 
            WHERE salary_high >= 50000
            ORDER BY salary_high DESC 
            LIMIT 5
            """)
        elif search_type == "最新":
            cursor.execute("""
            SELECT name, company_name, salary, job_url 
            FROM jobs 
            ORDER BY appear_date DESC 
            LIMIT 5
            """)
        else:  # 地區搜尋
            cursor.execute("""
            SELECT name, company_name, salary, job_url 
            FROM jobs 
            WHERE company_addr LIKE ? 
            ORDER BY appear_date DESC 
            LIMIT 5
            """, (f'%{search_type}%',))
        
        results = cursor.fetchall()
        conn.close()

        if results:
            reply = f"【{search_type}推薦職缺】\n\n" + "\n\n".join([
                f"🏢 {name}\n"
                f"🏭 公司：{company}\n"
                f"💰 薪資：{salary}\n"
                f"🔗 {url}"
                for name, company, salary, url in results
            ])
        else:
            reply = f"目前沒有{search_type}的職缺，請稍後再試"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=reply + "\n\n請選擇下一步操作：",
                quick_reply=create_search_options()
            )
        )
        return

    # 初始歡迎訊息
    welcome_msg = """
🎉 歡迎使用職缺搜尋機器人！
完全不用打字，只需點擊下方按鈕即可開始
"""
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=welcome_msg,
            quick_reply=create_main_menu()
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
