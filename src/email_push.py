"""
邮件推送：生成简洁的 HTML 邮件，发送每日论文摘要。
使用 SMTP 发送，支持 Gmail / QQ 邮箱 / 清华邮箱等。
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta


def _render_html(papers: list[dict]) -> str:
    """生成邮件 HTML 内容"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y-%m-%d")

    rows = []
    for i, p in enumerate(papers, 1):
        score = p.get("score", 0)
        # 高分标记
        star = "🔥" if score >= 8 else ""
        # 已确认顶会/顶刊接收的徽章
        venue = p.get("confirmed_venue")
        venue_badge = (
            f'<span style="background: #fbc02d; color: #333; padding: 1px 6px; '
            f'border-radius: 3px; font-size: 12px; margin-left: 4px;">🏆 {venue}</span>'
            if venue else ""
        )
        # 作者列表，最多显示 3 个
        authors = p.get("authors", [])
        if len(authors) > 3:
            author_str = ", ".join(authors[:3]) + f" et al. ({len(authors)}人)"
        else:
            author_str = ", ".join(authors)

        rows.append(f"""
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 12px 8px; vertical-align: top; color: #666; font-size: 14px; width: 30px;">
                {i}
            </td>
            <td style="padding: 12px 8px;">
                <div style="margin-bottom: 4px;">
                    <a href="{p['url']}" style="color: #1a73e8; text-decoration: none; font-size: 15px; font-weight: 600;">
                        {p['title']}
                    </a>
                    <span style="background: {'#d32f2f' if score >= 8 else '#1976d2' if score >= 6 else '#757575'};
                                  color: white; padding: 1px 6px; border-radius: 3px; font-size: 12px; margin-left: 6px;">
                        {score}/10 {star}
                    </span>{venue_badge}
                </div>
                <div style="color: #555; font-size: 13px; margin-bottom: 3px;">
                    {p.get('summary_zh', '')}
                </div>
                <div style="color: #999; font-size: 12px;">
                    {author_str} · {p['arxiv_id']}
                </div>
            </td>
        </tr>""")

    return f"""
    <html>
    <body style="font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; max-width: 680px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="border-bottom: 2px solid #1a73e8; padding-bottom: 12px; margin-bottom: 20px;">
            <h2 style="margin: 0; color: #1a73e8; font-size: 20px;">
                📄 arxiv-daily · {today}
            </h2>
            <p style="margin: 4px 0 0; color: #888; font-size: 13px;">
                World Models + RL for Autonomous Driving · Top {len(papers)} papers
            </p>
        </div>

        <table style="width: 100%; border-collapse: collapse;">
            {''.join(rows)}
        </table>

        <div style="margin-top: 24px; padding-top: 12px; border-top: 1px solid #eee; color: #aaa; font-size: 12px;">
            由 <a href="https://github.com" style="color: #aaa;">arxiv-daily</a> 自动生成 ·
            评分基于 DeepSeek ·
            <a href="https://arxiv.org" style="color: #aaa;">arXiv.org</a>
        </div>
    </body>
    </html>"""


def send_digest(papers: list[dict], config: dict):
    """发送邮件"""
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")
    to_email = os.environ.get("TO_EMAIL", "")

    if not all([smtp_user, smtp_password, to_email]):
        print("      [警告] 邮件配置不完整，跳过发送。")
        print("      请设置 SMTP_USER, SMTP_PASSWORD, TO_EMAIL 环境变量")
        return

    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📄 arxiv-daily | {today} | {len(papers)} papers"
    msg["From"] = smtp_user
    msg["To"] = to_email

    html = _render_html(papers)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, msg.as_string())
        print(f"      邮件已发送至 {to_email}")
    except Exception as e:
        print(f"      [错误] 邮件发送失败: {e}")
        raise
