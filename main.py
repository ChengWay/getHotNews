import requests
import os
import re

# ===================== 读取环境变量 =====================
ALAPI_TOKEN = os.getenv("ALAPI_TOKEN")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")

# 企业微信自建应用参数
WQ_CORP_ID = os.getenv("WQ_CORP_ID")
WQ_CORP_SECRET = os.getenv("WQ_CORP_SECRET")
WQ_AGENT_ID = os.getenv("WQ_AGENT_ID")
WQ_USER_ID = "WangChengWei"  # 固定你的成员账号，无需放入secrets

# ===================== 环境变量完整性校验 =====================
required_env = [
    ("ALAPI_TOKEN", ALAPI_TOKEN),
    ("ZHIPU_API_KEY", ZHIPU_API_KEY),
    ("WQ_CORP_ID", WQ_CORP_ID),
    ("WQ_CORP_SECRET", WQ_CORP_SECRET),
    ("WQ_AGENT_ID", WQ_AGENT_ID)
]
miss_list = []
for name, val in required_env:
    if not val or len(str(val).strip()) == 0:
        miss_list.append(name)

if miss_list:
    raise Exception(f"❌ 缺失环境变量密钥：{','.join(miss_list)}")

ZHIPU_API_KEY = ZHIPU_API_KEY.strip()


def get_daily_news():
    """获取ALAPI完整原始早报数据"""
    try:
        url = f"https://v3.alapi.cn/api/zaobao?token={ALAPI_TOKEN}&format=json"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        res = resp.json()
        print("ALAPI原始返回：", res)
        if res.get("code") != 200:
            raise Exception(f"早报接口异常 code !=200 {res}")
        data = res["data"]
        if "news" not in data or len(data["news"]) == 0:
            raise Exception("ALAPI新闻列表为空")
        return data
    except Exception as e:
        print(f"❌ 获取早报失败: {str(e)}")
        raise


def format_clean(text):
    """后置格式化清洗兜底：统一有序列表格式"""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    cleaned = []
    idx = 1
    for line in lines:
        # 清除所有旧序号、横线、圆点前缀
        line = re.sub(r"^(\d+[.、．]|[一二三四五六七八九十]+[、．]|[-*•●] )\s*", "", line)
        cleaned.append(f"{idx}. {line}")
        idx += 1
    return "\n".join(cleaned)


def ai_sort_news(raw_news_list):
    """调用智谱 glm-4-flash 永久免费模型整理新闻"""
    raw_text = "\n".join(raw_news_list)

    prompt = f"""
【角色】专业资讯编辑，仅标准化排版新闻内容
【硬性规则】
1. 完整保留所有新闻条目，严禁删减事实信息
2. 清除多余引号、分号、杂乱符号，语句通顺
3. 严格输出格式：1.  2.  3. 有序列表，每条独占一行
4. 禁止输出任何多余文字：无开场白、总结、注释、多余符号

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
            raise Exception("AI返回缺少choices字段")
        content = result["choices"][0]["message"]["content"].strip()
        content = format_clean(content)
        print("✅ AI整理完成")
        return content

    except Exception as e:
        print(f"⚠️ AI整理失败，自动降级原始新闻：{str(e)}")
        raw_content = "\n".join(raw_news_list)
        return format_clean(raw_content)


def get_wq_access_token():
    """获取企业微信接口临时access_token"""
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WQ_CORP_ID}&corpsecret={WQ_CORP_SECRET}"
    resp = requests.get(url, timeout=20)
    res = resp.json()
    if res.get("errcode") != 0:
        raise Exception(f"获取企微Token失败：{res}")
    return res["access_token"]


def send_workwechat_msg(news_content, date_str, weiyu):
    """企业微信 Markdown 消息推送"""
    access_token = get_wq_access_token()
    send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

    # 组装markdown内容
    markdown_text = f"""**📅 {date_str} | 每日早报资讯**

{news_content}

💡今日微语：{weiyu}
"""

    post_data = {
        "touser": WQ_USER_ID,
        "msgtype": "markdown",
        "agentid": int(WQ_AGENT_ID),
        "markdown": {
            "content": markdown_text
        }
    }
    print("=== 准备推送到企微的完整内容 ===")
    print(markdown_text)
    print("==============================")

    resp = requests.post(send_url, json=post_data, timeout=30)
    result = resp.json()
    print("企业微信推送返回结果：", result)
    if result.get("errcode") != 0:
        raise Exception(f"企微推送异常 {result}")


if __name__ == "__main__":
    print("====== 开始执行每日早报任务 ======")
    news_data = get_daily_news()
    raw_news = news_data["news"]
    tidy_news = ai_sort_news(raw_news)
    send_workwechat_msg(
        news_content=tidy_news,
        date_str=news_data["date"],
        weiyu=news_data["weiyu"]
    )
    print("✅======全部流程执行完成！======")
