"""
小红书 Web 端 - 浏览器扫码自动登录
统一使用 Playwright WebKit 引擎（与 Safari 同内核）
"""
import asyncio
import os
import sys
from playwright.async_api import async_playwright


async def auto_login():
    print("\n" + "=" * 50)
    print("  小红书 Web 端 - 浏览器扫码自动登录")
    print("=" * 50)
    print("✨ 即将弹出小红书登录页面，请在弹出的窗口中完成登录")
    print("   （支持扫码、手机号验证码等方式）")
    print()

    try:
        async with async_playwright() as p:
            # 统一使用 WebKit 引擎（与 Safari 同内核），避免被反爬检测
            browser = await p.webkit.launch(headless=False)

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            # 打开小红书首页
            await page.goto("https://www.xiaohongshu.com/explore", wait_until="domcontentloaded")
            print("✅ 浏览器已启动，请在弹出的窗口中登录...")
            print("   ⏳ 最多等待 3 分钟，登录成功后窗口将自动关闭。")
            print()

            # 轮询检测登录态
            max_wait = 180
            elapsed = 0
            logged_in = False
            cookies_str = ""

            while elapsed < max_wait:
                await asyncio.sleep(3)
                elapsed += 3

                # 获取当前所有 cookie
                all_cookies = await context.cookies()
                cookie_names = {c['name'] for c in all_cookies}

                # 登录成功的标志：同时存在 web_session 和 a1 这两个关键 cookie
                has_web_session = 'web_session' in cookie_names
                has_a1 = 'a1' in cookie_names

                if has_web_session and has_a1:
                    # 双重验证：用页面内 JS 调用 API 确认登录态
                    try:
                        result = await page.evaluate("""
                            async () => {
                                try {
                                    const r = await fetch('/api/sns/web/v2/user/me');
                                    const d = await r.json();
                                    return d.success === true;
                                } catch(e) {
                                    return false;
                                }
                            }
                        """)
                        if result:
                            logged_in = True
                            cookies_str = "; ".join(
                                [f"{c['name']}={c['value']}" for c in all_cookies]
                            )
                            break
                    except Exception:
                        # JS 执行失败也没关系，cookie 同时存在就够了
                        logged_in = True
                        cookies_str = "; ".join(
                            [f"{c['name']}={c['value']}" for c in all_cookies]
                        )
                        break

                if elapsed % 15 == 0:
                    print(f"   ⏳ 等待登录中... ({elapsed}s / {max_wait}s)")

            if not logged_in:
                print("❌ 登录超时（3分钟），请重新运行。")
                await browser.close()
                return

            print("✅ 检测到登录成功！正在提取并保存 Cookie...")

            # 关闭浏览器窗口
            await browser.close()
            print("✅ 登录窗口已自动关闭。")

            # 写入 .env 文件更新 COOKIES 字段
            env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
            lines = []
            cookie_found = False

            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('COOKIES='):
                            lines.append(f"COOKIES='{cookies_str}'\n")
                            cookie_found = True
                        else:
                            lines.append(line)

            if not cookie_found:
                if lines and not lines[-1].endswith('\n'):
                    lines[-1] += '\n'
                lines.append(f"COOKIES='{cookies_str}'\n")

            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            print(f"✅ Cookie 已写入 .env（共 {len(cookies_str)} 字符）")
            print("✅ 注入完成！网页仪表盘将自动检测并启动拉取。\n")

    except Exception as e:
        print(f"❌ 自动登录脚本遇到异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(auto_login())
