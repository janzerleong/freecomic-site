import subprocess

def run_crawler_once():
    print("启动爬虫任务...")
    result = subprocess.run(["python3", "crawler.py"], capture_output=True, text=True)

    print("运行状态码:", result.returncode)
    print("输出：\n", result.stdout)
    if result.stderr:
        print("错误信息：\n", result.stderr)
    print("爬虫任务已完成，脚本结束。")

if _name_ == "_main_":
    run_crawler_once()
