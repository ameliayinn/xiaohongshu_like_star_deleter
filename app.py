"""
小红书点赞收藏批量管理 - Web 可视化界面
Flask 后端：提供 API 接口给前端调用
"""
import os
import time
import random
import threading
import sys
from flask import Flask, render_template, jsonify, request
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import load_env

app = Flask(__name__)

# 全局状态
xhs = XHS_Apis()
cookies_str = load_env()
NO_PROXY = {"http": None, "https": None}

# 任务进度追踪
task_status = {
    "running": False,
    "type": "",        # "unlike" or "uncollect"
    "total": 0,
    "done": 0,
    "success": 0,
    "failed": 0,
    "log": [],
}

# 加载进度追踪
load_status = {
    "running": False,
    "count": 0,
    "error": "",
    "notes": []
}


def reset_task():
    task_status["running"] = False
    task_status["type"] = ""
    task_status["total"] = 0
    task_status["done"] = 0
    task_status["success"] = 0
    task_status["failed"] = 0
    task_status["log"] = []


def get_user_id():
    """获取当前登录用户 ID"""
    success, msg, info = xhs.get_user_self_info2(cookies_str, proxies=NO_PROXY)
    if success:
        return info.get("data", {}).get("user_id")
    success, msg, info = xhs.get_user_self_info(cookies_str, proxies=NO_PROXY)
    if success:
        return info.get("data", {}).get("basic_info", {}).get("red_id")
    return None


# ============ 页面路由 ============

@app.route("/")
def index():
    return render_template("index.html")


# ============ API 路由 ============

@app.route("/api/check-cookie")
def check_cookie():
    """检查 Cookie 是否有效"""
    global cookies_str
    # 强制从磁盘重新读取 .env，确保 auto_login 写入的新 cookie 能被读到
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    load_dotenv(dotenv_path=env_path, override=True)
    cookies_str = os.getenv('COOKIES', '')
    if not cookies_str:
        return jsonify({"ok": False, "msg": "未在 .env 中找到 COOKIES 配置"})
    user_id = get_user_id()
    if user_id:
        return jsonify({"ok": True, "user_id": user_id})
    return jsonify({"ok": False, "msg": "Cookie 无效或已过期"})


@app.route("/api/load-likes", methods=["POST"])
def start_load_likes():
    user_id = get_user_id()
    if not user_id: return jsonify({"ok": False, "msg": "无法获取用户ID"})
    if load_status["running"]: return jsonify({"ok": False, "msg": "正在拉取中..."})
    
    load_status["running"] = True
    load_status["count"] = 0
    load_status["error"] = ""
    load_status["notes"] = []
    
    def run():
        cursor = ""
        while True:
            success, msg, res = xhs.get_user_like_note_info(user_id, cursor, cookies_str, proxies=NO_PROXY)
            if not success:
                load_status["error"] = msg
                break
            notes = res.get("data", {}).get("notes", [])
            for n in notes:
                load_status["notes"].append({
                    "note_id": n.get("note_id", ""),
                    "title": n.get("display_title") or n.get("title", "无标题"),
                    "cover": n.get("cover", {}).get("url_default", "") if isinstance(n.get("cover"), dict) else "",
                    "author": n.get("user", {}).get("nickname", "未知") if isinstance(n.get("user"), dict) else "未知",
                    "author_id": n.get("user", {}).get("user_id", "") if isinstance(n.get("user"), dict) else "",
                    "liked_count": n.get("liked_count", n.get("interact_info", {}).get("liked_count", "")),
                    "type": n.get("type", ""),
                })
            load_status["count"] += len(notes)
            cursor = res.get("data", {}).get("cursor", "")
            has_more = res.get("data", {}).get("has_more", False)
            if not has_more or not cursor:
                break
            time.sleep(1) # 稍作停顿，避免请求过快
        load_status["running"] = False
        
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/load-collects", methods=["POST"])
def start_load_collects():
    user_id = get_user_id()
    if not user_id: return jsonify({"ok": False, "msg": "无法获取用户ID"})
    if load_status["running"]: return jsonify({"ok": False, "msg": "正在拉取中..."})
    
    load_status["running"] = True
    load_status["count"] = 0
    load_status["error"] = ""
    load_status["notes"] = []
    
    def run():
        cursor = ""
        while True:
            success, msg, res = xhs.get_user_collect_note_info(user_id, cursor, cookies_str, proxies=NO_PROXY)
            if not success:
                load_status["error"] = msg
                break
            notes = res.get("data", {}).get("notes", [])
            for n in notes:
                load_status["notes"].append({
                    "note_id": n.get("note_id", ""),
                    "title": n.get("display_title") or n.get("title", "无标题"),
                    "cover": n.get("cover", {}).get("url_default", "") if isinstance(n.get("cover"), dict) else "",
                    "author": n.get("user", {}).get("nickname", "未知") if isinstance(n.get("user"), dict) else "未知",
                    "author_id": n.get("user", {}).get("user_id", "") if isinstance(n.get("user"), dict) else "",
                    "liked_count": n.get("liked_count", n.get("interact_info", {}).get("liked_count", "")),
                    "type": n.get("type", ""),
                })
            load_status["count"] += len(notes)
            cursor = res.get("data", {}).get("cursor", "")
            has_more = res.get("data", {}).get("has_more", False)
            if not has_more or not cursor:
                break
            time.sleep(1)
        load_status["running"] = False
        
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/load-status")
def get_load_status():
    st = {
        "running": load_status["running"],
        "count": load_status["count"],
        "error": load_status["error"],
    }
    # 只有当停止时才返回列表，减少传输开销
    if not load_status["running"]:
        st["notes"] = load_status["notes"]
    return jsonify(st)


@app.route("/api/unlike", methods=["POST"])
def unlike_notes():
    """批量取消点赞（后台异步执行）"""
    data = request.json
    note_ids = data.get("note_ids", [])
    if not note_ids:
        return jsonify({"ok": False, "msg": "未选择任何笔记"})
    if task_status["running"]:
        return jsonify({"ok": False, "msg": "已有任务正在执行"})

    reset_task()
    task_status["running"] = True
    task_status["type"] = "unlike"
    task_status["total"] = len(note_ids)

    def run():
        for nid in note_ids:
            success, msg, res = xhs.unlike_note(nid, cookies_str, proxies=NO_PROXY)
            task_status["done"] += 1
            if success:
                task_status["success"] += 1
                task_status["log"].append(f"✅ {nid}")
            else:
                task_status["failed"] += 1
                task_status["log"].append(f"❌ {nid}: {msg}")
            time.sleep(random.uniform(2.5, 5.0))
        task_status["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "msg": f"开始取消点赞 {len(note_ids)} 篇"})


@app.route("/api/uncollect", methods=["POST"])
def uncollect_notes():
    """批量取消收藏（后台异步执行）"""
    data = request.json
    note_ids = data.get("note_ids", [])
    if not note_ids:
        return jsonify({"ok": False, "msg": "未选择任何笔记"})
    if task_status["running"]:
        return jsonify({"ok": False, "msg": "已有任务正在执行"})

    reset_task()
    task_status["running"] = True
    task_status["type"] = "uncollect"
    task_status["total"] = len(note_ids)

    def run():
        for nid in note_ids:
            success, msg, res = xhs.uncollect_note(nid, cookies_str, proxies=NO_PROXY)
            task_status["done"] += 1
            if success:
                task_status["success"] += 1
                task_status["log"].append(f"✅ {nid}")
            else:
                task_status["failed"] += 1
                task_status["log"].append(f"❌ {nid}: {msg}")
            time.sleep(random.uniform(2.5, 5.0))
        task_status["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "msg": f"开始取消收藏 {len(note_ids)} 篇"})


@app.route("/api/task-status")
def get_task_status():
    """查询任务进度"""
    return jsonify(task_status)


@app.route("/api/trigger-login", methods=["POST"])
def trigger_login():
    """启动 Playwright 弹窗登录（始终使用 WebKit 引擎）"""
    import subprocess, os
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_login.py")
    subprocess.Popen([sys.executable, script_path])
    return jsonify({"ok": True})

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    print("\n\n👋 网页端已关闭被检测到，正在自动停止并退出后台服务...\n")
    import os
    os._exit(0)
    return jsonify({"ok": True})


if __name__ == "__main__":
    import sys
    import subprocess
    import webbrowser

    print()
    print("=" * 50)
    print("  小红书点赞收藏批量管理工具")
    print("=" * 50)
    print()
    
    print("请选择要调起的浏览器：")
    print("  1. 系统默认浏览器")
    print("  2. Google Chrome")
    print("  3. Safari")
    print("  4. Microsoft Edge")
    print("  5. 不自动打开，手动输入链接")
    
    try:
        choice = input("\n请选择序号 (默认 1): ").strip()
    except EOFError:
        choice = "1"
    if not choice:
        choice = "1"
        
    app.config['BROWSER_CHOICE'] = choice
        
    def open_browser():
        import urllib.request
        url = "http://127.0.0.1:5000"
        
        # 轮询等待 Flask 完全启动，避免打开太快导致浏览器白屏
        for _ in range(10):
            try:
                urllib.request.urlopen(url)
                break
            except Exception:
                time.sleep(0.5)
                
        time.sleep(0.5) # 稳妥起见再多等半秒
        try:
            if choice == "2":
                subprocess.run(['open', '-a', 'Google Chrome', url])
            elif choice == "3":
                subprocess.run(['open', '-a', 'Safari', url])
            elif choice == "4":
                subprocess.run(['open', '-a', 'Microsoft Edge', url])
            elif choice == "5":
                print(f"\n✨ 服务已启动，请在浏览器中手动打开: {url} \n")
            else:
                webbrowser.open(url)
        except Exception as e:
            print(f"打开浏览器跳出异常: {e}\n请手动打开: {url}")

    if choice != "5":
        print(f"\n✨ 服务即将启动，浏览器会自动打开 http://127.0.0.1:5000 \n")
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(debug=False, port=5000)
