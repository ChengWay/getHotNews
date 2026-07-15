import requests
import os
import re

# ============ 读取环境变量 ============
ALAPI_TOKEN = os.getenv("ALAPI_TOKEN")
WX_APPID = os.getenv("WX_APPID")
WX_APPSECRET = os.getenv("WX_APPSECRET")
WX_OPENID = os.getenv("WX_OPENID")
WX_TEMPLATE_ID = os.getenv("WX_TEMPLATE_ID")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")

# 环境变量完整性校验
required_env = [
    ("ALAPI_TOKEN", ALAPI_TOKEN),
    ("WX_APPID", WX_APPID),
    ("WX_APPSECRET", WX_APPSECRET),
    ("WX_OPENID", WX_OPENID),
    ("WX_TEMPLATE_ID", WX_TEMPLATE_ID),
    ("ZHIPU_API_KEY", ZHIPU_API_KEY)
]
miss_list = []
for name, val in required_env:
    if not val or len(val.strip()) == 0:
        miss_list.append(name)

if miss_list:
    raise Exception(f"❌ 缺失环境变量密钥：{','.join(miss_list)}")

print(f"✅ ZHIPU_API_KEY 读取成功，字符长度：{len(ZHIPU_API_KEY.strip())}")
ZHIPU_API_KEY = ZHIPU_API_KEY.strip()


def get_daily_news():
    """获取ALAPI原始早报（仅作为AI输入素材，不直接推送）"""
    try:
        url = f"https://v3.alapi.cn/api/zaobao?token={ALAPI_TOKEN}&format=json"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        res = resp.json()
        if res.get("code") != 200:
            raise Exception(f"早报接口异常 {res}")
        data = res["data"]
        if "news" not in data or len(data["news"]) == 0:
            raise Exception("ALAPI新闻列表为空")
        return data
    except Exception as e:
        print(f"❌ 获取早报失败: {str(e)}")
        raise


def format_clean(text):
    """统一格式化：标准有序列表，清理杂乱符号"""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    cleaned = []
    idx = 1
    for line in lines:
        line = re.sub(r"^(\d+[.、．]|[一二三四五六七八九十]+[、．]|[-*•●] )\s*", "", line)
        cleaned.append(f"{idx}. {line}")
        idx += 1
    return "\n".join(cleaned)


def ai_sort_news(raw_news_list):
    """AI整理新闻，返回最终可直接推送的规整文本"""
    raw_text = "\n".join(raw_news_list)

    prompt = f"""
【角色】专业资讯编辑，仅做新闻标准化排版
【规则】
1. 完整保留全部新闻条目，不得删减事实
2. 去除多余引号、分号、杂乱符号，语句通顺
3. 严格使用 1. 2. 3. 有序列表，每条独占一行
4. 禁止输出开场白、总结、评论、多余注释

【原始资讯】
{raw_text}
"""

    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4-flash",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 2000
    }

    try:
        resp = requests.post(
            "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            headers=headers,
            json=payload,
            timeout=90
        )
        result = resp.json()
        print("智谱AI原始返回：", result)

        if "choices" not in result or len(result["choices"]) == 0:
            raise Exception("AI返回结构异常")

        content = result["choices"][0]["message"]["content"].strip()
        content = format_clean(content)
        print("✅ AI整理完成")
        return content

    except Exception as e:
        print(f"⚠️ AI调用失败，降级使用原始内容：{str(e)}")
        # 兜底：AI失败时才用原始内容，保证推送不中断
        return format_clean("\n".join(raw_news_list))


def get_wechat_access_token():
    """获取公众号access_token"""
    try:
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WX_APPID}&secret={WX_APPSECRET}"
        resp = requests.get(url, timeout=20)
        data = resp.json()
        if "access_token" not in data:
            raise Exception(f"获取微信token失败 {data}")
        return data["access_token"]
    except Exception as e:
        print(f"❌ 获取微信AccessToken异常：{str(e)}")
        raise


def send_wx_template(date_str, ai_content, weiyu):
    """
    微信推送：news字段直接传入AI整理后的内容
    原始新闻不会出现在推送消息中
    """
    access_token = get_wechat_access_token()
    send_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={access_token}"
    post_body = {
        "touser": WX_OPENID,
        "template_id": WX_TEMPLATE_ID,
        "data": {
            "date": {"value": date_str},
            "summary": {"value": "📰AI整理今日热点资讯"},
            "news": {"value": ai_content},  # 这里传入的就是AI整理后的最终文本
            "tip": {"value": weiyu}
        }
    }

    # 调试日志：确认推送的就是AI整理后的内容
    print("=== 最终推送到微信的新闻内容 ===")
    print(ai_content)
    print("================================")

    try:
        resp = requests.post(send_url, json=post_body, timeout=30)
        result = resp.json()
        print("微信推送结果：", result)
        if result["errcode"] != 0:
            raise Exception(f"推送失败 {result}")
    except Exception as e:
        print(f"❌ 微信推送异常：{str(e)}")
        raise


if __name__ == "__main__":
    print("====== 开始执行每日早报任务 ======")
    # 1. 拉取原始早报（仅作为AI输入）
    news_data = get_daily_news()
    raw_news = news_data["news"]
    # 2. AI整理，得到最终推送文本
    final_news = ai_sort_news(raw_news)
    # 3. 直接推送AI整理后的内容
    send_wx_template(
        date_str=news_data["date"],
        ai_content=final_news,
        weiyu=news_data["weiyu"]
    )
    print("✅======全部流程执行完成！======")
