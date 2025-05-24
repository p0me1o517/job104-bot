import requests
import sqlite3
import time
import random
from urllib.parse import quote

class Job104Spider:
    def __init__(self, db_path='jobNs.db'):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._create_table()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://www.104.com.tw/jobs/search/'
        })

    def _create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                name TEXT,
                company_name TEXT,
                company_addr TEXT,
                salary TEXT,
                salary_low INTEGER,
                salary_high INTEGER,
                education TEXT,
                period TEXT,
                appear_date TEXT,
                apply_num INTEGER,
                lon REAL,
                lat REAL,
                tags TEXT,
                job_url TEXT,
                job_company_url TEXT,
                job_analyze_url TEXT
            )
        ''')
        self.conn.commit()

    def _clear_table(self):
        self.cursor.execute("DELETE FROM jobs")
        self.conn.commit()

    def normalize_address(self, addr):
        """統一地址格式"""
        replacements = {
            '臺北': '台北',
            '臺中': '台中',
            '臺南': '台南',
            '臺東': '台東',
            '台北縣': '新北市',
            '桃園縣': '桃園市'
        }
        for old, new in replacements.items():
            addr = addr.replace(old, new)
        return addr.strip()

    def search_all_jobs(self, max_pages=3):
        base_url = 'https://www.104.com.tw/jobs/search/list'
        params = {
            'ro': '0',
            'kwop': '7',
            'expansionType': 'area,spec,com,job,wf,wktm',
            'mode': 's',
            'jobsource': '2018indexpoc'
        }
        
        jobs = []
        page = 1
        while True:
            print(f"正在爬取第 {page} 頁...")
            params['page'] = page
            try:
                response = self.session.get(base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data.get('data', {}).get('list'):
                    break
                
                for job in data['data']['list']:
                    try:
                        transformed = self._transform_job(job)
                        jobs.append(transformed)
                    except Exception as e:
                        print(f"轉換職缺失敗: {e}")
                
                if page >= data['data']['totalPage'] or (max_pages and page >= max_pages):
                    break
                    
                page += 1
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"爬取失敗: {e}")
                break
                
        return jobs

    def _transform_job(self, job_data):
        """轉換職缺資料格式"""
        job_url = f"https:{job_data['link']['job']}"
        job_id = job_url.split('/job/')[-1].split('?')[0]
        
        return {
            'job_id': job_id,
            'name': job_data['jobName'],
            'company_name': job_data['custName'],
            'company_addr': self.normalize_address(f"{job_data.get('jobAddrNoDesc', '')} {job_data.get('jobAddress', '')}"),
            'salary': job_data['salaryDesc'],
            'salary_low': int(job_data['salaryLow']) if job_data['salaryLow'] else 0,
            'salary_high': int(job_data['salaryHigh']) if job_data['salaryHigh'] else 0,
            'education': job_data['optionEdu'],
            'period': job_data['periodDesc'],
            'appear_date': job_data['appearDate'],
            'apply_num': int(job_data['applyCnt']),
            'lon': float(job_data['lon']),
            'lat': float(job_data['lat']),
            'tags': ', '.join(job_data.get('tags', [])),
            'job_url': job_url,
            'job_company_url': f"https:{job_data['link']['cust']}",
            'job_analyze_url': f"https:{job_data['link']['applyAnalyze']}"
        }

    def save_job_to_db(self, job):
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO jobs VALUES (
                    :job_id, :name, :company_name, :company_addr, :salary,
                    :salary_low, :salary_high, :education, :period,
                    :appear_date, :apply_num, :lon, :lat, :tags,
                    :job_url, :job_company_url, :job_analyze_url
                )
            ''', job)
            self.conn.commit()
        except Exception as e:
            print(f"儲存失敗: {e}")

    def run(self, max_pages=None, clear_old=False):
        if clear_old:
            self._clear_table()
            print("已清空舊資料")
            
        jobs = self.search_all_jobs(max_pages=max_pages)
        for job in jobs:
            self.save_job_to_db(job)
        print(f"總共儲存 {len(jobs)} 筆職缺資料")

if __name__ == "__main__":
    spider = Job104Spider()
    spider.run(max_pages=None, clear_old=True)