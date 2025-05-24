from job104_spider import Job104Spider

if __name__ == "__main__":
    spider = Job104Spider()
    spider.run(max_pages=None, clear_old=True)
